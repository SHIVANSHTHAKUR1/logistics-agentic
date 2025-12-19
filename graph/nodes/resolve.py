"""
Node: resolve_node

Purpose
- Fill in missing numeric IDs (owner_id, driver_id, vehicle_id, customer_id, load_id) based on fuzzy hints already
    extracted by router/planner (names, email, phone, license plate).

Strategy
- Uses direct SQLAlchemy queries (case-insensitive for names/plates) to avoid LLM cost.
- Only resolves what is necessary for the current intent; does not attempt multi-match disambiguation yet.

Routing Decisions
- For queries: if id resolved -> query_agent else mark incomplete and go to verify.
- For mutations: if required foreign keys still missing -> mark incomplete and verify else exec_mutation.
- Fallback: append an AI message instructing user to be more specific and end.

Edge Cases
- If user provided an id already (string or numeric) we trust it and coerce to int when possible.
- If resolution fails, we never invent ids—state.last_result.status = 'incomplete'.

Future Enhancements
- Add multi-candidate disambiguation step.
- Cache lookups per conversation.
"""
from typing import Dict, Any, Optional
from langchain_core.messages import AIMessage
from sqlalchemy import func
from tools.database_tools import SessionLocal, Owner, User, Vehicle, Load, UserRole
from ..state import CoreState


# Intents we may resolve for
MUTATION_INTENTS = {
    "register_owner",
    "register_user",
    "add_vehicle",
    "add_trip",
    "add_expense",
    "create_load",
    "assign_load_to_trip",
    "add_location_update",
}

QUERY_INTENTS = {
    "trip_details",
    "vehicle_summary",
    "owner_summary",
    "load_details",
    "driver_details",
    "user_expenses",
    "driver_expenses",
}


def _resolve_owner_id(db, entities: Dict[str, Any]) -> Optional[int]:
    if entities.get("owner_id"):
        return int(entities["owner_id"])  # already present
    name = entities.get("company_name") or entities.get("owner_name")
    if not name:
        return None
    row = db.query(Owner).filter(func.lower(Owner.company_name) == name.lower()).first()
    return row.owner_id if row else None


def _resolve_user_id(db, entities: Dict[str, Any], role: Optional[UserRole] = None) -> Optional[int]:
    """Resolve a customer/driver id from hints.

    Current schema stores people in the `users` table with a `role` column.
    When role is provided we filter by it; otherwise we try drivers first then customers.
    """
    uid = entities.get("user_id") or entities.get("driver_id") or entities.get("customer_id")
    if uid:
        try:
            return int(uid)
        except Exception:
            pass
    name = entities.get("full_name") or entities.get("name") or entities.get("driver_name") or entities.get("customer_name")
    email = entities.get("email")
    phone = entities.get("phone_number") or entities.get("phone")

    def query_driver() -> Optional[int]:
        q = db.query(User).filter(User.role == UserRole.DRIVER)
        if email:
            row = q.filter(func.lower(User.email) == email.lower()).first()
            if row:
                return row.user_id
        if phone:
            row = q.filter(User.phone_number == phone).first()
            if row:
                return row.user_id
        if name:
            row = q.filter(func.lower(User.full_name) == name.lower()).first()
            if row:
                return row.user_id
        return None

    def query_customer() -> Optional[int]:
        q = db.query(User).filter(User.role == UserRole.CUSTOMER)
        if email:
            row = q.filter(func.lower(User.email) == email.lower()).first()
            if row:
                return row.user_id
        if phone:
            row = q.filter(User.phone_number == phone).first()
            if row:
                return row.user_id
        if name:
            row = q.filter(func.lower(User.full_name) == name.lower()).first()
            if row:
                return row.user_id
        return None

    if role == UserRole.DRIVER:
        return query_driver()
    if role == UserRole.CUSTOMER:
        return query_customer()
    # role None: prefer driver resolution first
    return query_driver() or query_customer()


def _resolve_vehicle_id(db, entities: Dict[str, Any]) -> Optional[int]:
    if entities.get("vehicle_id"):
        try:
            return int(entities["vehicle_id"])
        except Exception:
            pass
    plate = entities.get("license_plate") or entities.get("plate")
    if not plate:
        return None
    row = db.query(Vehicle).filter(func.lower(Vehicle.license_plate) == plate.lower()).first()
    return row.vehicle_id if row else None


def _resolve_load_id(db, entities: Dict[str, Any]) -> Optional[int]:
    if entities.get("load_id"):
        try:
            return int(entities["load_id"])
        except Exception:
            pass
    # Simple resolution left out for loads unless explicit id provided
    return None


def resolve_node(state: CoreState) -> CoreState:
    intent = state.get("intent", "")
    entities: Dict[str, Any] = state.get("entities", {})
    messages = state.get("messages", [])

    db = SessionLocal()
    try:
        if intent in {"owner_summary", "add_vehicle", "register_user"}:
            oid = _resolve_owner_id(db, entities)
            if oid:
                entities["owner_id"] = oid
                if intent == "owner_summary":
                    entities["id"] = oid

        if intent in {"add_trip", "add_expense", "user_expenses", "driver_expenses", "driver_details"}:
            # Expenses/trips are always attached to drivers.
            uid = _resolve_user_id(db, entities, UserRole.DRIVER)
            if uid:
                if intent in {"user_expenses", "driver_expenses", "driver_details"}:
                    entities["id"] = uid
                # For trips/expenses, fill driver_id
                if intent in {"add_trip", "add_expense"}:
                    entities["driver_id"] = uid

        if intent in {"add_trip", "vehicle_summary"}:
            vid = _resolve_vehicle_id(db, entities)
            if vid:
                if intent == "vehicle_summary":
                    entities["id"] = vid
                else:
                    entities["vehicle_id"] = vid

        if intent in {"create_load"}:
            # resolve customer
            cid = _resolve_user_id(db, entities, UserRole.CUSTOMER)
            if cid:
                entities["customer_id"] = cid

        if intent in {"assign_load_to_trip", "load_details"}:
            lid = _resolve_load_id(db, entities)
            if lid and intent == "load_details":
                entities["id"] = lid
            elif lid:
                entities["load_id"] = lid

        # Decide next path or signal incomplete if critical ids still missing
        # For queries: require entities['id']
        if intent in QUERY_INTENTS:
            if entities.get("id") is None:
                # Give verify_node a field name so it can ask a targeted question.
                if intent == "driver_details":
                    state["last_result"] = {"status": "incomplete", "message": "Missing fields: driver_id"}
                else:
                    state["last_result"] = {"status": "incomplete", "message": "Couldn't resolve target ID for query."}
                state["next_action"] = "verify"
            else:
                state["entities"] = entities
                state["next_action"] = "query_agent"
            return state

        # For mutations: validate common id dependencies
        if intent in MUTATION_INTENTS:
            missing = []
            if intent == "add_vehicle" and not entities.get("owner_id"):
                missing.append("owner_id")
            if intent == "add_trip":
                if not entities.get("driver_id"):
                    missing.append("driver_id")
                if not entities.get("vehicle_id"):
                    missing.append("vehicle_id")
            if intent == "add_expense" and not entities.get("driver_id"):
                missing.append("driver_id")
            if intent == "create_load" and not entities.get("customer_id"):
                missing.append("customer_id")
            if missing:
                state["last_result"] = {"status": "incomplete", "message": f"Missing fields: {', '.join(missing)}"}
                state["next_action"] = "verify"
            else:
                state["entities"] = entities
                state["next_action"] = "exec_mutation"
            return state

        # Fallback to chat
        messages.append(AIMessage(content="I couldn't determine what to resolve. Try a specific ID or name."))
        state["messages"] = messages
        state["next_action"] = "end"
        return state
    finally:
        db.close()
