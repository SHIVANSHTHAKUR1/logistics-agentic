"""Role-based authorization for agent intents.

This repo doesn't implement authentication yet; "role" is a session-selected mode
(customer/driver/owner). We enforce a strict allowlist to prevent customer/driver
sessions from invoking owner-only tools.

Enforcement points:
- planner_node: blocks disallowed intents early (no tool call)
- query_agent_node / exec_mutation_node: defensive enforcement
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set


def normalize_role(role: Optional[str]) -> str:
    r = (role or "").strip().lower()
    if r in {"customer", "driver", "owner", "whatsapp"}:
        return r
    return "owner"  # backward compatible default


ROLE_ALLOWED_INTENTS: Dict[str, Set[str]] = {
    # Customers can create loads and check their load status/details.
    "customer": {
        "chat",
        "greeting",
        "create_load",
        "nl_update",
        "load_details",
        "user_details",
        # Customer self-registration
        "register_user",
    },
    # Drivers can manage their operational updates.
    "driver": {
        "chat",
        "greeting",
        "register_user",
        "driver_details",
        "user_details",
        "trip_details",
        "trip_expenses",
        "driver_expenses",
        "user_expenses",
        "add_expense",
        "nl_update",
        "add_location_update",
        "load_details",
    },
    # Owners can do everything.
    "owner": {
        "chat",
        "greeting",
        "register_owner",
        "register_user",
        "add_vehicle",
        "add_trip",
        "add_expense",
        "create_load",
        "assign_load_to_trip",
        "add_location_update",
        "nl_update",
        "trip_details",
        "trip_expenses",
        "vehicle_summary",
        "owner_summary",
        "load_details",
        "driver_details",
        "user_details",
        "driver_expenses",
        "user_expenses",
    },

    # WhatsApp channel runs without per-user role selection; treat as a privileged channel.
    # This role has full access to all tools/agents (same as owner).
    "whatsapp": {
        "chat",
        "greeting",
        "register_owner",
        "register_user",
        "add_vehicle",
        "add_trip",
        "add_expense",
        "create_load",
        "assign_load_to_trip",
        "add_location_update",
        "nl_update",
        "trip_details",
        "trip_expenses",
        "vehicle_summary",
        "owner_summary",
        "load_details",
        "driver_details",
        "user_details",
        "driver_expenses",
        "user_expenses",
    },
}


def is_intent_allowed(role: Optional[str], intent: Optional[str], payload: Optional[Dict[str, Any]] = None) -> bool:
    r = normalize_role(role)
    i = (intent or "").strip()
    if not i:
        return True

    allowed = ROLE_ALLOWED_INTENTS.get(r, ROLE_ALLOWED_INTENTS["owner"])
    if i not in allowed:
        return False

    # Additional safety rules
    if r not in {"owner", "whatsapp"} and i == "register_user":
        # Customers may only register as customers; drivers may only register drivers.
        if payload is not None:
            requested_role = str(payload.get("role") or "").strip().lower()
            if r == "customer":
                return (requested_role or "customer") == "customer"
            if r == "driver":
                # If role is not provided yet (multi-turn), allow and let the executor
                # infer from the raw text; otherwise require driver.
                return (requested_role == "" or requested_role == "driver")

    return True


def deny_message(role: Optional[str], intent: Optional[str]) -> str:
    r = normalize_role(role)
    i = (intent or "").strip() or "(unknown)"
    if i == "register_user":
        if r == "driver":
            return "Access denied: drivers can only register users with role=driver."
        if r == "customer":
            return "Access denied: customers can only register users with role=customer."
    return f"Access denied: '{i}' is not available in {r} mode."
