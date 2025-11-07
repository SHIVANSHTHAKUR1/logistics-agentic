"""
Node: planner_node

Role
Use the default LLM (Gemini/OpenAI/etc. via DEFAULT_MODEL) to convert free-form natural language logistics requests
into a controlled JSON intent + entities structure. This is the ONLY node allowed to interpret broad NL.

Strict Output Contract (MUST return ONLY JSON text – no prose):
{
    "task_type": string,  // one of mutation/query/chat canonical forms listed below
    "entities": {         // flat key:value map of extracted data
            // ids (owner_id, driver_id, vehicle_id, customer_id, load_id, trip_id ...)
            // names (company_name, full_name, driver_name, owner_name, customer_name)
            // contact fields (email, phone_number)
            // logistics fields (license_plate, capacity_kg, origin, destination, weight_kg, amount, expense_type)
            // timestamps (start_time, end_time)
    }
}

Accepted task_type values
- register_owner, register_user
- add_vehicle, add_trip, add_expense, create_load, assign_load_to_trip, add_location_update
- query_trip, query_vehicle, query_owner, query_load, query_user_expenses, query_driver_expenses
- chat (fallback when nothing matches)

Normalization
- task_type is mapped to internal state.intent via INTENT_NORMALIZE for queries
- Entities must be shallow (no nesting arrays/objects) to simplify downstream resolution.

Routing Logic After Parsing
- If intent (post-normalization) is a query but lacks an id and has name/plate/email hints -> next_action = resolve
- If a mutation missing required foreign key ids but hints exist -> next_action = resolve
- Otherwise:
    - mutation -> exec_mutation
    - query -> query_agent
    - chat/unknown -> chat

Failure Handling
- Any exception sets state.error and falls back to chat intent.

Edge Cases
- Model may wrap JSON in markdown fences; we strip them.
- Missing entities -> treat as empty dict.
"""
from typing import Dict, Any
import json
from langchain_core.messages import HumanMessage, SystemMessage
from llms import DEFAULT_MODEL
from ..state import CoreState
from ..prompts import DETAILED_PLANNER_SYSTEM

PLANNER_SYSTEM = DETAILED_PLANNER_SYSTEM

INTENT_NORMALIZE = {
    "query_trip": "trip_details",
    "trip_expenses": "trip_expenses",
    "query_vehicle": "vehicle_summary",
    "query_owner": "owner_summary",
    "query_load": "load_details",
    "query_user_expenses": "user_expenses",
    "query_driver_expenses": "driver_expenses",
}

MUTATION_INTENTS = {
    "register_owner",
    "register_user",
    "add_vehicle",
    "add_trip",
    "add_expense",
    "create_load",
    "assign_load_to_trip",
    "add_location_update",
    "nl_update",
}

QUERY_INTENTS = set(INTENT_NORMALIZE.values())


def _needs_resolution(intent: str, entities: Dict[str, Any]) -> bool:
    # Queries: if no id but hint present
    if intent in QUERY_INTENTS:
        if entities.get("id") is None and any(k in entities for k in [
            "license_plate", "plate", "company_name", "owner_name", "driver_name", "full_name", "email", "phone", "phone_number"
        ]):
            return True
        return False

    # Mutations: missing id fields but hints present
    if intent in {"register_user", "add_vehicle"}:
        if not entities.get("owner_id") and any(k in entities for k in ["company_name", "owner_name"]):
            return True
    if intent in {"add_trip", "add_expense"}:
        if not entities.get("driver_id") and any(k in entities for k in ["driver_name", "full_name", "email", "phone", "phone_number"]):
            return True
    if intent in {"add_trip"}:
        if not entities.get("vehicle_id") and any(k in entities for k in ["license_plate", "plate"]):
            return True
    if intent in {"create_load"}:
        if not entities.get("customer_id") and any(k in entities for k in ["customer_name", "full_name", "email", "phone", "phone_number"]):
            return True
    return False


def planner_node(state: CoreState) -> CoreState:
    messages = state.get("messages", [])
    user_input = state.get("user_input", "")
    # Focus heuristic: if recent turn requested a specific trip, store focus to bias next generic queries
    focus = state.get("focus", {}) or {}
    # Build prompt
    sys = SystemMessage(content=PLANNER_SYSTEM)
    msgs = [sys, HumanMessage(content=user_input)]
    intent = "chat"
    entities: Dict[str, Any] = {}
    try:
        if DEFAULT_MODEL is None:
            raise RuntimeError("No default LLM configured")
        resp = DEFAULT_MODEL.invoke(msgs)
        text = getattr(resp, "content", "{}") or "{}"
        # Model may wrap in code fences; strip if present
        text = text.strip()
        if text.startswith("```"):
            text = text.strip('`')
            # remove leading json label if any
            text = text.replace("json\n", "", 1)
        data = json.loads(text)
        intent = str(data.get("task_type") or "chat")
        if intent in INTENT_NORMALIZE:
            intent = INTENT_NORMALIZE[intent]
        ents = data.get("entities") or {}
        if isinstance(ents, dict):
            entities = ents
    except Exception as e:
        state["error"] = f"planner_error: {e}"
        intent = "chat"
        entities = {}

    # Merge with any prior entities carried in state to preserve multi-turn context
    prev_entities = state.get("entities", {}) or {}
    if prev_entities:
        merged = dict(prev_entities)
        merged.update(entities)
        entities = merged
    # Stash raw user input for downstream heuristics (e.g., role inference during register_user)
    if user_input:
        entities["_raw_user_input"] = user_input

    # Heuristic: if user asks generic 'expenses' and we have a focused trip id, reinterpret as trip_expenses
    low = (user_input or "").lower()
    if ("expense" in low or "expenses" in low) and ("trip" not in low) and focus.get("trip_id") and intent in {"chat", "user_expenses", "driver_expenses"}:
        intent = "trip_expenses"
        entities["id"] = focus["trip_id"]

    # Decide next (may insert a resolve step if ids need mapping)
    if _needs_resolution(intent, entities):
        next_action = "resolve"
    elif intent in MUTATION_INTENTS:
        next_action = "exec_mutation"
    elif intent in QUERY_INTENTS:
        next_action = "query_agent"
    elif intent == "chat":
        next_action = "chat"
    else:
        next_action = "chat"

    # Track focus when a trip is queried so next turn can refer to 'total expenses' implicitly
    if intent in {"trip_details", "trip_expenses"} and entities.get("id") is not None:
        focus["trip_id"] = int(entities.get("id"))

    state.update({
        "intent": intent,
        "entities": entities,
        "next_action": next_action,
        "focus": focus,
    })
    return state
