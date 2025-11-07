"""
Node: exec_mutation_node

Purpose
- Perform state-changing logistics mutations (register/create/add/assign/update) once required IDs and fields exist.

Workflow
1. Select function from MUTATION_MAP using state.intent.
2. Normalize incoming entities via _normalize_payload (synonym + schema alignment).
3. Validate REQUIRED_FIELDS after normalization (reject empty / None).
4. Execute mutation: positional for assign_load_to_trip, dict payload otherwise.
5. Store result in state.last_result and route to verify.

Error Handling
- Unsupported intent: AI message + end.
- Missing required fields: last_result.status = 'incomplete'.
- Exception during execution: last_result.status = 'error'.

Edge Cases
- Numeric conversions (capacity_kg, weight_kg, latitude/longitude) guard against empty strings.
- Temporary password hash created if none provided for register_user.

Non-Goals
- Does not resolve foreign keys (handled earlier by resolve_node).
- Does not format final output (reflect_node).

Future Enhancements
- Add partial validation feedback (which synonyms were used), audit logging, and idempotency checks.
"""
from typing import Any, Dict
import os
from langchain_core.messages import AIMessage
from tools import (
    register_owner,
    register_user,
    add_vehicle,
    add_trip,
    add_expense,
    create_load,
    assign_load_to_trip,
    add_location_update,
    nl_update,
)
from tools.database_tools import SessionLocal, Owner  # for owner auto-detection
from ..state import CoreState

MUTATION_MAP = {
    "register_owner": register_owner,
    "register_user": register_user,
    "add_vehicle": add_vehicle,
    "add_trip": add_trip,
    "add_expense": add_expense,
    "create_load": create_load,
    "assign_load_to_trip": assign_load_to_trip,
    "add_location_update": add_location_update,
    # special-cased in executor to pass raw user_input string
    "nl_update": nl_update,
}


def _coalesce(d: Dict[str, Any], *keys):
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return None


def _normalize_payload(intent: str, entities: Dict[str, Any]) -> Dict[str, Any]:
    # Map common synonyms to DB schema expected by tools.database_tools
    if intent == "register_owner":
        return {
            "company_name": _coalesce(entities, "company_name", "name", "owner_name"),
            "business_address": _coalesce(entities, "business_address", "address"),
            "contact_email": _coalesce(entities, "contact_email", "email"),
            "gst_number": entities.get("gst_number"),
        }
    if intent == "register_user":
        full_name = _coalesce(entities, "full_name", "name")
        email = _coalesce(entities, "email")
        phone = _coalesce(entities, "phone_number", "phone")
        role = _coalesce(entities, "role")
        # Heuristic: if role missing and user_input mentions 'customer' or 'driver'
        if not role:
            raw = (entities.get("_raw_user_input") or "").lower()
            if "customer" in raw:
                role = "customer"
            elif "driver" in raw:
                role = "driver"
        password_hash = entities.get("password_hash") or (f"temp_hash_{hash(full_name or 'user')}" if full_name else None)
        owner_id = entities.get("owner_id")
        if owner_id in (None, ""):
            # Auto-pick single owner if exactly one exists
            try:
                db = SessionLocal()
                owners = db.query(Owner).all()
                if len(owners) == 1:
                    owner_id = owners[0].owner_id
            except Exception:
                pass
            finally:
                try:
                    db.close()
                except Exception:
                    pass
        # Hard default per user requirement: if still missing, use owner_id=1
        if owner_id in (None, ""):
            owner_id = 1
        return {
            "owner_id": owner_id,
            "full_name": full_name,
            "email": email,
            "password_hash": password_hash,
            "phone_number": phone,
            "role": role,
        }
    if intent == "add_vehicle":
        plate = _coalesce(entities, "license_plate", "plate", "license", "license_no")
        capacity = _coalesce(entities, "capacity_kg", "capacity", "capacitykg")
        status = entities.get("status")
        return {
            "owner_id": entities.get("owner_id"),
            "license_plate": plate,
            "capacity_kg": float(capacity) if capacity not in (None, "") else None,
            "status": status,
        }
    if intent == "add_trip":
        return {
            "driver_id": entities.get("driver_id"),
            "vehicle_id": entities.get("vehicle_id"),
            "status": entities.get("status"),
            "start_time": entities.get("start_time"),
            "end_time": entities.get("end_time"),
        }
    if intent == "add_expense":
        # map category/type to expense_type; allow user_id as alias for driver_id
        expense_type = _coalesce(entities, "expense_type", "category", "type")
        driver_id = _coalesce(entities, "driver_id", "user_id")
        return {
            "driver_id": driver_id,
            "amount": entities.get("amount"),
            "expense_type": expense_type,
            "trip_id": entities.get("trip_id"),
            "description": entities.get("description"),
            "receipt_url": entities.get("receipt_url"),
        }
    if intent == "create_load":
        weight = _coalesce(entities, "weight_kg", "weight")
        return {
            "customer_id": entities.get("customer_id"),
            "pickup_address": _coalesce(entities, "pickup_address", "origin"),
            "destination_address": _coalesce(entities, "destination_address", "destination"),
            "weight_kg": float(weight) if weight not in (None, "") else None,
            "description": entities.get("description"),
            "status": entities.get("status"),
        }
    if intent == "assign_load_to_trip":
        return {
            "load_id": entities.get("load_id"),
            "trip_id": entities.get("trip_id"),
        }
    if intent == "add_location_update":
        lat = _coalesce(entities, "latitude", "lat")
        lng = _coalesce(entities, "longitude", "lng", "long")
        return {
            "trip_id": entities.get("trip_id"),
            "latitude": float(lat) if lat not in (None, "") else None,
            "longitude": float(lng) if lng not in (None, "") else None,
            "speed_kmh": entities.get("speed_kmh"),
            "address": entities.get("address"),
        }
    return entities


REQUIRED_FIELDS = {
    "register_owner": ["company_name", "business_address", "contact_email"],
    "register_user": ["owner_id", "full_name", "email", "phone_number", "role"],
    "add_vehicle": ["owner_id", "license_plate", "capacity_kg"],
    "add_trip": ["driver_id", "vehicle_id"],
    "add_expense": ["driver_id", "amount", "expense_type"],
    "create_load": ["customer_id", "pickup_address", "destination_address"],
    "assign_load_to_trip": ["load_id", "trip_id"],
    "add_location_update": ["trip_id", "latitude", "longitude"],
}


def exec_mutation_node(state: CoreState) -> CoreState:
    intent = state.get("intent", "")
    entities: Dict[str, Any] = state.get("entities", {})
    messages = state.get("messages", [])
    fn = MUTATION_MAP.get(intent)
    if fn is None:
        messages.append(AIMessage(content=f"Unsupported mutation intent: {intent}"))
        state.update({"messages": messages, "next_action": "end"})
        return state

    # Normalize entity keys before validation
    payload = _normalize_payload(intent, dict(entities))

    # Validate required fields (skip for nl_update which parses raw text)
    if intent != "nl_update":
        missing = [f for f in REQUIRED_FIELDS.get(intent, []) if payload.get(f) in (None, "")]
        if missing:
            state["last_result"] = {"status": "incomplete", "message": f"Missing fields: {', '.join(missing)}"}
            state["next_action"] = "verify"
            return state

    # Execute
    try:
        # assign_load_to_trip expects positional args
        if intent == "assign_load_to_trip":
            if os.getenv("LOG_TOOL_CALLS"):
                print(f"[exec_mutation] intent={intent} fn={fn.__name__} load_id={payload['load_id']} trip_id={payload['trip_id']}")
            result = fn(int(payload["load_id"]), int(payload["trip_id"]))
        elif intent == "nl_update":
            # pass the original user_input to the tool for inline parsing
            text = state.get("user_input", "")
            if os.getenv("LOG_TOOL_CALLS"):
                print(f"[exec_mutation] intent={intent} fn={fn.__name__} text='{text[:80]}'...")
            result = fn(text)
        else:
            if os.getenv("LOG_TOOL_CALLS"):
                preview_keys = ",".join(sorted(payload.keys()))
                print(f"[exec_mutation] intent={intent} fn={fn.__name__} keys={preview_keys}")
            result = fn(payload)
    except Exception as e:
        result = {"status": "error", "message": str(e)}
    state["last_result"] = result
    state["next_action"] = "verify"
    return state
