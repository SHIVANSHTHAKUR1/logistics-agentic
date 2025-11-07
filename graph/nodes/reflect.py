"""Node: reflect_node

Purpose
  Produce a user-facing reply from `state.last_result` and end the turn WITHOUT calling an LLM.

Enhancements
  - Structured formatting for trip details (bulleted, English only).
  - Optional JSON output if user requests 'json' or env STRUCTURED_OUTPUT=json.

Non-Goals
  - No hallucination, no additional queries.
  - Avoid verbose prose; keep output skimmable.
"""
from langchain_core.messages import AIMessage
from ..state import CoreState
import os
from typing import Any, Dict, List


def _structured_trip(result: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append("Trip Details")
    lines.append("-------------")
    mapping = [
        ("trip_id", "Trip ID"),
        ("driver_id", "Driver ID"),
        ("vehicle_id", "Vehicle ID"),
        ("start_time", "Start Time"),
        ("end_time", "End Time"),
        ("total_expense", "Total Expense"),
        ("expense_count", "Expense Count"),
        ("load_count", "Load Count"),
        ("location_update_count", "Location Updates"),
    ]
    for key, en in mapping:
        val = result.get(key)
        if val in (None, "null"):
            val = "(not set)"
        lines.append(f"- {en}: {val}")
    lines.append("Next: ask 'trip <id> expenses' or 'trip <id> loads'")
    return lines


def _as_json(result: Dict[str, Any]) -> str:
    import json
    try:
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception:
        return str(result)


def reflect_node(state: CoreState) -> CoreState:
    messages = state.get("messages", [])
    result: Dict[str, Any] = state.get("last_result", {}) or {}
    intent = state.get("intent") or ""
    user_input = state.get("user_input") or ""

    force_json = os.getenv("STRUCTURED_OUTPUT", "").lower() == "json" or "json" in user_input.lower()

    # English-only formatting as per user request
    if force_json and isinstance(result, dict):
        content = _as_json(result)
    elif intent == "trip_details" and isinstance(result, dict):
        content = "\n".join(_structured_trip(result))
    elif isinstance(result, dict) and result.get("status") == "incomplete" and (result.get("questions") or result.get("optional_questions")):
        # Structured missing-fields guidance (required + optional)
        req_qs = result.get("questions", [])
        missing = result.get("missing_fields", [])
        opt_fields = result.get("optional_fields", [])
        opt_qs = result.get("optional_questions", [])
        if force_json:
            content = _as_json(result)
        else:
            lines = ["Missing information", "-------------------"]
            if missing:
                lines.append("Required fields: " + ", ".join(missing))
            if req_qs:
                lines.append("Please provide:")
                for q in req_qs:
                    lines.append(f"- {q}")
            if opt_fields:
                lines.append("")
                lines.append("Optional fields (nice to have): " + ", ".join(opt_fields))
            if opt_qs:
                lines.append("Optional suggestions:")
                for q in opt_qs:
                    lines.append(f"- {q}")
            content = "\n".join(lines)
    elif intent == "trip_expenses" and isinstance(result, dict):
        # Format key trip expense info first
        lines = [
            f"Trip {result.get('trip_id')} Expenses",
            "------------------------",
            f"Total: {result.get('total_expense', 0)} (count: {result.get('expense_count', 0)})"
        ]
        bd = result.get("expense_breakdown") or {}
        if bd:
            lines.append("Breakdown:")
            for k, v in bd.items():
                lines.append(f"- {k}: {v}")
        lines.append("Next: add 'add expense trip <id> fuel 500' or ask 'trip <id> loads'")
        content = "\n".join(lines)
    else:
        # Generic fallback: compact key:value
        lines: List[str] = []
        if isinstance(result, dict) and result:
            for k, v in result.items():
                # Only skip "status" when it's from verify_node (incomplete/complete)
                # Keep it when it's an entity field (maintenance, available, etc)
                if k == "status" and v in {"incomplete", "complete"}:
                    continue
                if isinstance(v, (dict, list)):
                    continue
                val = "(not set)" if v in (None, "null") else v
                lines.append(f"{k}: {val}")
        content = "\n".join(lines) if lines else (state.get("summary") or "No data")

    messages.append(AIMessage(content=content))
    state["messages"] = messages

    # Internal loop logic: continue only if auto_loop enabled AND criteria met
    auto = state.get("auto_loop") or os.getenv("AUTO_LOOP") == "1"
    iteration = int(state.get("iteration", 0))
    max_iters = int(state.get("max_iterations", int(os.getenv("MAX_AUTO_ITERS", 3))))
    lr = state.get("last_result", {}) or {}
    status = str(lr.get("status", "")).lower()

    continue_conditions = auto and iteration < max_iters and status in {"incomplete"}
    if continue_conditions:
        # Prepare for next planner pass
        state["iteration"] = iteration + 1
        # Clear user_input so planner can rely on accumulated entities
        state["user_input"] = ""
        state["next_action"] = "loop"
    else:
        state["next_action"] = "end"
    return state
