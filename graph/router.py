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
    ("user_details", re.compile(r"\buser\s*(?:id\s*)?(\d+)\b.*\b(details?|profile)\b", re.I)),
]

# Simple NL mutation (fast) handled without LLM using tools.nl_update
NL_UPDATE_PATTERN = re.compile(r"\b(change|set|update)\b.*\b(driver|user|vehicle|trip|load)\s*(?:id\s*)?(\d+)\b", re.I)

# Direct assignment patterns
# 1) "assign load 5 to trip 12" or "attach load 7 with trip 3"
ASSIGN_LOAD_PATTERN = re.compile(r"\b(assign|attach)\b\s*load\s*(\d+)\s*(?:to|with)\s*trip\s*(\d+)", re.I)
# 2) Reversed order: "assign trip 12 to load 5"
ASSIGN_TRIP_PATTERN = re.compile(r"\b(assign|attach)\b\s*trip\s*(\d+)\s*(?:to|with)\s*load\s*(\d+)", re.I)

# Explicit trip creation (avoid planner misclassification)
ADD_TRIP_PATTERN = re.compile(
    r"\badd\s*trip\b.*\bdriver\s*(?:id\s*)?(\d+)\b.*\bvehicle\s*(?:id\s*)?(\d+)\b",
    re.I,
)

# Explicit location update (avoid planner parse failures for coordinates)
ADD_LOCATION_PATTERN = re.compile(
    r"\badd\s+location\b.*\btrip\s*(?:id\s*)?(\d+)\b.*\blat(?:itude)?\s*([+-]?\d+(?:\.\d+)?)\b.*\b(?:lon(?:gitude)?|lng)\s*([+-]?\d+(?:\.\d+)?)\b(?:.*\baddress\s+(.+))?",
    re.I,
)

# Explicit expense (avoid planner/parser dropping driver_id/amount)
ADD_EXPENSE_PATTERN = re.compile(
    r"\badd\s+expense\b.*\btrip\s*(?:id\s*)?(\d+)\b\s+([a-z_]+)\s+(\d+(?:\.\d+)?)\b.*\bdriver\s*(?:id\s*)?(\d+)\b",
    re.I,
)

# Explicit user registration (avoid planner variability)
REGISTER_USER_PATTERN = re.compile(
    r"\bregister\s+(user|driver|customer)\b",
    re.I,
)


def intent_router_node(state: CoreState) -> CoreState:
    text = (state.get("user_input") or "").strip()
    messages = state.get("messages", [])

    # Carry forward any existing entities (do not drop context)
    intent = "chat"
    prev_entities = state.get("entities", {}) or {}
    entities = dict(prev_entities)

    # Fast-path: explicit user profile/details query
    m_user_details = re.search(r"\buser\s*(?:id\s*)?(\d+)\b.*\b(details?|profile)\b", text, re.I)
    if m_user_details:
        try:
            entities["id"] = int(m_user_details.group(1))
        except Exception:
            entities["id"] = m_user_details.group(1)
        state.update({"intent": "user_details", "entities": entities, "next_action": "fastpath"})
        return state

    # Fast-path: explicit user registration
    if REGISTER_USER_PATTERN.search(text):
        # Extract role
        low = text.lower()
        role = None
        if re.search(r"\brole\s+(customer|driver|owner)\b", low):
            role = re.search(r"\brole\s+(customer|driver|owner)\b", low).group(1)
        elif "register driver" in low:
            role = "driver"
        elif "register customer" in low:
            role = "customer"

        # Extract owner_id if present
        m_owner = re.search(r"\bowner\s*(?:id\s*)?(\d+)\b", low)
        if m_owner:
            try:
                entities["owner_id"] = int(m_owner.group(1))
            except Exception:
                entities["owner_id"] = m_owner.group(1)

        # Extract email (required)
        m_email = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,})", text)
        if m_email:
            entities["email"] = m_email.group(1)

        # Extract phone (required)
        m_phone = re.search(r"\b(?:phone|mobile|contact)\b\D*(\+?\d{10,15})", low)
        if m_phone:
            entities["phone_number"] = m_phone.group(1)
        else:
            # fallback: any 10-15 digit sequence
            m_phone2 = re.search(r"(\+?\d{10,15})", low)
            if m_phone2:
                entities["phone_number"] = m_phone2.group(1)

        # Extract full name
        name = None
        m_full = re.search(r"\bfull\s+name\b\s+(.+)$", text, re.I)
        if m_full:
            name = m_full.group(1)
        else:
            # register driver/customer <name> ...
            m_reg = re.search(r"\bregister\s+(?:user|driver|customer)\b\s+(.+)$", text, re.I)
            if m_reg:
                name = m_reg.group(1)
        if name:
            # Trim at known field markers
            name = re.split(r"\b(role|email|phone|mobile|contact|owner)\b", name, flags=re.I)[0].strip(" -,:\t\n\r")
            if name:
                entities["full_name"] = name

        if role:
            entities["role"] = role

        state.update({"intent": "register_user", "entities": entities, "next_action": "exec_mutation"})
        return state

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

    # Fast-path: explicit add trip
    m_trip = ADD_TRIP_PATTERN.search(text)
    if m_trip:
        try:
            entities["driver_id"] = int(m_trip.group(1))
        except Exception:
            entities["driver_id"] = m_trip.group(1)
        try:
            entities["vehicle_id"] = int(m_trip.group(2))
        except Exception:
            entities["vehicle_id"] = m_trip.group(2)

        state.update({"intent": "add_trip", "entities": entities, "next_action": "exec_mutation"})
        return state

    # Fast-path: explicit location update
    m_loc = ADD_LOCATION_PATTERN.search(text)
    if m_loc:
        try:
            entities["trip_id"] = int(m_loc.group(1))
        except Exception:
            entities["trip_id"] = m_loc.group(1)
        try:
            entities["latitude"] = float(m_loc.group(2))
        except Exception:
            entities["latitude"] = m_loc.group(2)
        try:
            entities["longitude"] = float(m_loc.group(3))
        except Exception:
            entities["longitude"] = m_loc.group(3)
        addr = m_loc.group(4)
        if addr:
            entities["address"] = addr.strip()

        state.update({"intent": "add_location_update", "entities": entities, "next_action": "exec_mutation"})
        return state

    # Fast-path: explicit add expense
    m_exp = ADD_EXPENSE_PATTERN.search(text)
    if m_exp:
        try:
            entities["trip_id"] = int(m_exp.group(1))
        except Exception:
            entities["trip_id"] = m_exp.group(1)
        entities["expense_type"] = (m_exp.group(2) or "").strip().lower()
        try:
            entities["amount"] = float(m_exp.group(3))
        except Exception:
            entities["amount"] = m_exp.group(3)
        try:
            entities["driver_id"] = int(m_exp.group(4))
        except Exception:
            entities["driver_id"] = m_exp.group(4)

        state.update({"intent": "add_expense", "entities": entities, "next_action": "exec_mutation"})
        return state

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
