"""Scenario-based harness to exercise LangGraph tool selection.

Each scenario is a sequence of user inputs. We keep cumulative state (messages, entities, focus)
across turns inside a single scenario to test multi-turn behaviors like trip expense focus.

For every turn we record:
  - raw user_input
  - resulting intent
  - next_action (internal decision prior to END)
  - status (from last_result if available)
  - delta entities (new keys added/changed this turn)
  - short reply excerpt

Optional expectations:
  expected_intents: list parallel to inputs (None = ignore)
  expected_status: list parallel to inputs (None = ignore)

Run:
  One-shot console output:
    python test_tool_scenarios.py

  JSON summary:
    python test_tool_scenarios.py --json > scenarios_output.json

Add new scenarios by appending to SCENARIOS with name, inputs, and optional expected lists.
"""
from __future__ import annotations
import argparse
import json
from typing import List, Dict, Any, Optional
from graph.build import main_graph


SCENARIOS: List[Dict[str, Any]] = [
    {
        "name": "Trip details then total expenses (focus heuristic)",
        "inputs": ["trip 1 details", "total expenses"],
        "expected_intents": ["trip_details", "trip_expenses"],
    },
    {
        "name": "Create load missing destination (incomplete verify)",
        "inputs": ["create load customer 3 pickup Chandni Chowk weight 500"],
        "expected_intents": ["create_load"],
        "expected_status": ["incomplete"],  # verify should flag missing destination_address
    },
    {
        "name": "Add expense to trip",  # simple mutation
        "inputs": ["add expense trip 1 fuel 500 driver 1"],
        "expected_intents": ["add_expense"],
    },
    {
        "name": "Driver expense summary",  # user-level expense query
        "inputs": ["driver 1 expenses"],
        "expected_intents": ["driver_expenses"],
    },
    {
        "name": "Vehicle summary",  # query by id
        "inputs": ["vehicle 1 summary"],
        "expected_intents": ["vehicle_summary"],
    },
    {
        "name": "Assign load to trip",  # mutation with two IDs
        "inputs": ["assign load 1 to trip 2"],
        "expected_intents": ["assign_load_to_trip"],
    },
    {
        "name": "Register user with auto owner_id detection",  # mutation with fallback owner_id=1
        "inputs": ["register driver Bob Smith email bob@test.com phone 9988776655"],
        "expected_intents": ["register_user"],
    },
    {
        "name": "NL update driver phone",  # nl_update path
        "inputs": ["change driver 1 phone 1234567890"],
        "expected_intents": ["nl_update"],
    },
    {
        "name": "Resolution: vehicle by plate",  # resolve vehicle_id from license_plate
        "inputs": ["vehicle TN02CD5678 summary"],
        "expected_intents": ["vehicle_summary"],
    },
    {
        "name": "Greeting shortcut",  # fast path chat
        "inputs": ["hello"],
        "expected_intents": ["greeting"],
    },
    {
        "name": "Load details query",
        "inputs": ["load 1 details"],
        "expected_intents": ["load_details"],
    },
    {
        "name": "Owner summary",
        "inputs": ["owner 1 summary"],
        "expected_intents": ["owner_summary"],
    },
]


def run_turn(state: Dict[str, Any], user_input: str) -> Dict[str, Any]:
    # Build minimal state for this turn including prior messages/entities
    turn_state = {
        "messages": state.get("messages", []),
        "entities": state.get("entities", {}),
        "focus": state.get("focus", {}),
        "user_input": user_input,
        "auto_loop": False,
        "max_iterations": 0,
    }
    result_state = main_graph.invoke(turn_state)
    # Derive delta entities
    prev_entities = state.get("entities", {}) or {}
    new_entities = result_state.get("entities", {}) or {}
    delta = {}
    for k, v in new_entities.items():
        if k not in prev_entities or prev_entities.get(k) != v:
            delta[k] = v
    # Extract reply excerpt
    reply = ""
    for msg in reversed(result_state.get("messages", []) or []):
        c = getattr(msg, "content", None)
        if c:
            reply = c
            break
    lr = result_state.get("last_result", {}) or {}
    return {
        "intent": result_state.get("intent"),
        "next_action": result_state.get("next_action"),
        "status": lr.get("status"),
        "entities_delta": delta,
        "reply_excerpt": reply[:180],
        "full_reply": reply,
        "raw_last_result": lr,
        "focus": result_state.get("focus", {}),
        "final_state": result_state,
    }


def run_scenario(s: Dict[str, Any]) -> Dict[str, Any]:
    accum: Dict[str, Any] = {"messages": [], "entities": {}, "focus": {}}
    turns = []
    for idx, inp in enumerate(s["inputs"]):
        out = run_turn(accum, inp)
        # propagate state for next turn
        accum["messages"] = out["final_state"].get("messages", [])
        accum["entities"] = out["final_state"].get("entities", {})
        accum["focus"] = out.get("focus", {})
        # expectation checks
        exp_intents = s.get("expected_intents") or []
        exp_status = s.get("expected_status") or []
        out["intent_match"] = (idx < len(exp_intents) and exp_intents[idx] == out["intent"]) if exp_intents else None
        out["status_match"] = (idx < len(exp_status) and exp_status[idx] == out["status"]) if exp_status else None
        out["input"] = inp
        turns.append(out)
    return {
        "name": s["name"],
        "turns": turns,
    }


def main():
    parser = argparse.ArgumentParser(description="Run predefined agent scenarios")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()
    results = [run_scenario(s) for s in SCENARIOS]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return
    for scenario in results:
        print(f"\n=== Scenario: {scenario['name']} ===")
        for i, turn in enumerate(scenario["turns"]):
            print(f"Turn {i+1} Input: {turn['input']}")
            print(f"  Intent: {turn['intent']} (match={turn['intent_match']})")
            print(f"  Next Action: {turn['next_action']}")
            print(f"  Status: {turn['status']} (match={turn['status_match']})")
            if turn['entities_delta']:
                print(f"  Entities Δ: {turn['entities_delta']}")
            if turn['focus']:
                print(f"  Focus: {turn['focus']}")
            print(f"  Reply: {turn['reply_excerpt']}")
    print("\nSummary: Use --json for machine-readable output. Add scenarios in SCENARIOS list.")


if __name__ == "__main__":
    main()
