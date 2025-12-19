"""
Node: query_agent_node

Purpose
- Execute read-only database queries for resolved intents without invoking an LLM.

Contract
- Requires state.intent ∈ INTENT_TOOL_MAP and entities['id'] present.
- Calls the mapped tool with int(id). On success: state.last_result populated; next_action -> verify.
- On missing intent/tool: replies with AI message and ends.

Edge Cases
- If id is None -> last_result.status = error so verify/reflect surfaces message.
- Tool exceptions caught and converted to {status: 'error', message: str(e)}.

Non-Goals
- Does not perform name/plate resolution (handled by resolve_node).
- Does not summarize/format output (reflect_node handles that).
"""
from typing import Dict, Any
import os
from langchain_core.messages import AIMessage
from tools import (
    get_trip_details,
    get_vehicle_summary,
    get_owner_summary,
    get_load_details,
    get_user_expenses,
    get_trip_expenses,
    get_driver_details,
    get_user_details,
)
from ..authz import is_intent_allowed, deny_message, normalize_role
from ..state import CoreState  # type: ignore


INTENT_TOOL_MAP = {
    "trip_details": get_trip_details,
    "trip_expenses": get_trip_expenses,
    "vehicle_summary": get_vehicle_summary,
    "owner_summary": get_owner_summary,
    "load_details": get_load_details,
    "driver_details": get_driver_details,
    "user_details": get_user_details,
    "driver_expenses": get_user_expenses,
    "user_expenses": get_user_expenses,
}


def query_agent_node(state: CoreState) -> CoreState:
    intent = state.get("intent")
    actor_role = normalize_role(state.get("actor_role"))
    entities = state.get("entities", {})
    messages = state.get("messages", [])

    if not is_intent_allowed(actor_role, intent, entities):
        state["last_result"] = {"status": "error", "message": deny_message(actor_role, intent)}
        state["next_action"] = "verify"
        return state

    tool = INTENT_TOOL_MAP.get(intent)
    if not tool:
        messages.append(AIMessage(content="Unsupported query intent."))
        state.update({"messages": messages, "next_action": "end"})
        return state
    obj_id = entities.get("id")
    try:
        if os.getenv("LOG_TOOL_CALLS"):
            print(f"[query_agent] intent={intent} tool={tool.__name__} id={obj_id}")
        result = tool(int(obj_id)) if obj_id is not None else {"status": "error", "message": "No id provided"}
    except Exception as e:
        result = {"status": "error", "message": str(e)}
    state["last_result"] = result
    state["next_action"] = "verify"
    return state
