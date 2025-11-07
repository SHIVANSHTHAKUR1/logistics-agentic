"""
Node: intent_router_node

Purpose
- Lightweight pre-processor. Extracts obvious IDs as hints, handles greetings, and defers ALL tool selection to the planner.

Inputs (from CoreState)
- user_input: str — the latest user message
- messages: list — conversation history (appended to if greeting)

Behavior
- If the text is a greeting, immediately replies with a short help message and ends.
- Otherwise, it may extract IDs (trip/load/vehicle/owner/user) as hints into state.entities but does NOT choose the tool.
- Always sets next_action='agent' so the planner LLM decides the intent and tool.

Notes
- We still keep simple regexes to lift IDs into entities for better resolution later, but intent/tool selection is planner-only.
"""
import re
from langchain_core.messages import HumanMessage, AIMessage
from .state import CoreState


QUERY_PATTERNS = [
    ("trip_details", re.compile(r"\btrip\s*(?:id\s*)?(\d+)", re.I)),
    ("vehicle_summary", re.compile(r"\bvehicle\s*(?:id\s*)?(\d+)", re.I)),
    ("owner_summary", re.compile(r"\bowner\s*(?:id\s*)?(\d+)", re.I)),
    ("load_details", re.compile(r"\bload\s*(?:id\s*)?(\d+)", re.I)),
    ("driver_expenses", re.compile(r"\bdriver\s*(?:id\s*)?(\d+).*\bexpenses?\b", re.I)),
    ("user_expenses", re.compile(r"\buser\s*(?:id\s*)?(\d+).*\bexpenses?\b", re.I)),
]

# Simple NL mutation (fast) handled without LLM using tools.nl_update
NL_UPDATE_PATTERN = re.compile(r"\b(change|set|update)\b.*\b(driver|user|vehicle|trip|load)\s*(?:id\s*)?(\d+)\b", re.I)

# Direct assignment patterns
# 1) "assign load 5 to trip 12" or "attach load 7 with trip 3"
ASSIGN_LOAD_PATTERN = re.compile(r"\b(assign|attach)\b\s*load\s*(\d+)\s*(?:to|with)\s*trip\s*(\d+)", re.I)
# 2) Reversed order: "assign trip 12 to load 5"
ASSIGN_TRIP_PATTERN = re.compile(r"\b(assign|attach)\b\s*trip\s*(\d+)\s*(?:to|with)\s*load\s*(\d+)", re.I)


def intent_router_node(state: CoreState) -> CoreState:
    text = (state.get("user_input") or "").strip()
    messages = state.get("messages", [])

    # Carry forward any existing entities (do not drop context)
    intent = "chat"
    prev_entities = state.get("entities", {}) or {}
    entities = dict(prev_entities)

    # Extract hint for NL updates (we no longer dispatch here; planner decides)
    m = NL_UPDATE_PATTERN.search(text)
    if m:
        try:
            entities["id"] = int(m.group(3))
        except Exception:
            entities["id"] = m.group(3)

    # Extract hints for assignment (load -> trip)
    m2 = ASSIGN_LOAD_PATTERN.search(text)
    if m2:
        try:
            entities["load_id"] = int(m2.group(2))
        except Exception:
            entities["load_id"] = m2.group(2)
        try:
            entities["trip_id"] = int(m2.group(3))
        except Exception:
            entities["trip_id"] = m2.group(3)

    # Extract hints for assignment (trip -> load)
    m3 = ASSIGN_TRIP_PATTERN.search(text)
    if m3:
        try:
            entities["trip_id"] = int(m3.group(2))
        except Exception:
            entities["trip_id"] = m3.group(2)
        try:
            entities["load_id"] = int(m3.group(3))
        except Exception:
            entities["load_id"] = m3.group(3)

    # Generic assign hints: if text mentions assign/attach and includes both a trip id and a load id
    if re.search(r"\b(assign|attach|map|link)\b", text, re.I):
        trip_match = re.search(r"\btrip\s*(?:id\s*)?(\d+)", text, re.I)
        load_match = re.search(r"\bload\s*(?:id\s*)?(\d+)", text, re.I)
        if trip_match and load_match:
            try:
                entities["trip_id"] = int(trip_match.group(1))
            except Exception:
                entities["trip_id"] = trip_match.group(1)
            try:
                entities["load_id"] = int(load_match.group(1))
            except Exception:
                entities["load_id"] = load_match.group(1)

    # Extract simple query id hints (planner will still decide intent/tool)
    for name, pattern in QUERY_PATTERNS:
        m = pattern.search(text)
        if m:
            # normalize id; merge into existing entities
            try:
                entities["id"] = int(m.group(1))
            except Exception:
                entities["id"] = m.group(1)
            break

    # Greetings shortcut
    if intent == "chat" and re.search(r"\b(hi|hello|hey|greetings)\b", text, re.I):
        state.update({
            "intent": "greeting",
            "entities": {},
            "next_action": "end",
        })
        messages.append(AIMessage(content="Hi! I can help with trips, vehicles, loads and expenses. What would you like to do?"))
        state["messages"] = messages
        return state

    # Always defer to planner for tool/intents
    state.update({"intent": intent, "entities": entities, "next_action": "agent"})
    return state
