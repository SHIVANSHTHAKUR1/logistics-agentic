"""
Node: verify_node

Purpose
- Perform a lightweight sanity check on state.last_result before reflection.

Rules
- If status ∈ {error, failed} -> set summary to message and proceed to reflect.
- Otherwise mark as ok if either:
    - status == 'success', or
    - there exists at least one scalar field besides {status,message}.
- If not ok -> summary = message or 'No data found.' then reflect.

Note
- This node does not mutate the database; it only decides whether reflect should display content or an error/empty message.
"""
from langchain_core.messages import AIMessage
from ..state import CoreState
import re


def _extract_missing_from_message(message: str) -> list:
    """Extract missing field names from common error/incomplete messages.
    Supports:
    - "Missing fields: a, b, c"
    - "'field' is required"
    """
    if not message:
        return []
    m = re.search(r"Missing fields:\s*(.+)$", message, re.I)
    if m:
        parts = [p.strip() for p in m.group(1).split(',') if p.strip()]
        return parts
    req = re.findall(r"'([^']+)'\s+is\s+required", message, re.I)
    if req:
        return req
    return []

    
FIELD_QUESTIONS = {
        # Owner / Company
        "company_name": "Company name?",
        "business_address": "Business address?",
        "contact_email": "Contact email?",
        "gst_number": "GST number? (optional)",
        # User
        "owner_id": "Owner ID? (default 1 if unknown)",
        "full_name": "Full name?",
        "email": "Email address?",
        "password_hash": "Password? (leave empty for temporary)",
        "phone_number": "Phone number?",
        "role": "Role? (driver / customer / owner)",
        # Vehicle
        "license_plate": "Vehicle license plate?",
        "capacity_kg": "Cargo capacity (kg)?",
        "status": "Vehicle status? (available / in_use / maintenance / out_of_service) (optional)",
        # Trip
        "driver_id": "Driver ID? (or name/email/phone)",
        "vehicle_id": "Vehicle ID? (or license plate)",
        "start_time": "Start time (ISO)? (optional)",
        "end_time": "End time (ISO)? (optional)",
        # Expense
        "amount": "Expense amount?",
        "expense_type": "Expense type? (fuel / maintenance / toll / food / accommodation / other)",
        "trip_id": "Trip ID? (optional)",
        "description": "Short description? (optional)",
        "receipt_url": "Receipt URL? (optional)",
        # Load
        "customer_id": "Customer ID? (or name/email/phone)",
        "pickup_address": "Pickup address?",
        "destination_address": "Destination address?",
        "weight_kg": "Weight (kg)? (optional)",
        # Assign / Location
        "load_id": "Load ID?",
        "latitude": "Latitude?",
        "longitude": "Longitude?",
        "address": "Address? (optional)",
        # Context / Optional extras
        "speed_kmh": "Speed (km/h)? (optional)",
}

INTENT_OPTIONAL_FIELDS = {
    "create_load": ["weight_kg", "description", "trip_id"],
    "add_expense": ["trip_id", "description", "receipt_url"],
    "add_vehicle": ["status"],
    "add_trip": ["start_time", "end_time"],
    "add_location_update": ["speed_kmh", "address"],
}


def verify_node(state: CoreState) -> CoreState:
    result = state.get("last_result", {}) or {}
    intent = state.get("intent") or ""
    # Minimal verification: success flag or presence of key fields
    status = str(result.get("status", "")).lower()
    if status in {"error", "failed"}:
        message = str(result.get("message", "Operation failed."))
        # If error is about missing required field, turn it into a question
        missing = _extract_missing_from_message(message)
        if missing:
            questions = []
            for f in missing:
                q = FIELD_QUESTIONS.get(f, f"I need '{f}'. Please provide it.")
                questions.append(q)
            # Suggest optional fields not yet provided
            ents = state.get("entities", {}) or {}
            optional = []
            optional_qs = []
            for opt in INTENT_OPTIONAL_FIELDS.get(intent, []):
                if ents.get(opt) in (None, ""):
                    optional.append(opt)
                    optional_qs.append(FIELD_QUESTIONS.get(opt, f"(Optional) Provide {opt} if available."))
            state["last_result"] = {
                "status": "incomplete",
                "missing_fields": missing,
                "questions": questions,
                "optional_fields": optional,
                "optional_questions": optional_qs,
            }
            state["summary"] = questions[0]
        else:
            state["summary"] = message
        state["next_action"] = "reflect"
        return state

    # Consider queries successful if we have some scalar fields or explicit success
    ok = status == "success" or any(
        k for k, v in result.items() if k not in {"status", "message"} and not isinstance(v, (dict, list))
    )
    if not ok:
        # Handle incomplete path (e.g., from resolve/exec with explicit missing fields)
        message = str(result.get("message", "No data found."))
        missing = _extract_missing_from_message(message)
        if missing:
            questions = []
            for f in missing:
                q = FIELD_QUESTIONS.get(f, f"I need '{f}'. Please provide it.")
                questions.append(q)
            ents = state.get("entities", {}) or {}
            optional = []
            optional_qs = []
            for opt in INTENT_OPTIONAL_FIELDS.get(intent, []):
                if ents.get(opt) in (None, ""):
                    optional.append(opt)
                    optional_qs.append(FIELD_QUESTIONS.get(opt, f"(Optional) Provide {opt} if available."))
            state["last_result"] = {
                "status": "incomplete",
                "missing_fields": missing,
                "questions": questions,
                "optional_fields": optional,
                "optional_questions": optional_qs,
            }
            state["summary"] = questions[0]
        else:
            state["summary"] = message
        state["next_action"] = "reflect"
        return state

    state["next_action"] = "reflect"
    return state
