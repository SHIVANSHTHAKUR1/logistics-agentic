# Logistics Agent (LangGraph Modular)

A modular, token-efficient logistics assistant built with LangGraph and Gemini (Google Generative AI). It supports deterministic fast-path queries, a Gemini-powered planner for natural-language tasks, an ID resolver for names/plates → IDs, safe mutation execution, and concise reflections.

## Quick start (web app)

PowerShell (Windows):

```powershell
# From project root
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python web_app.py
```

Open:
- Chat UI: http://localhost:5000
- Health:  http://localhost:5000/health
- Examples: http://localhost:5000/examples

Send messages like:
- "trip 1"
- "vehicle MH01AB1234"
- "owner ACME Logistics details"
- "driver John Doe expenses"
- "add trip for driver John Doe with vehicle MH01AB1234"

## Optional: LangGraph Dev UI

```powershell
langgraph dev
```

Open the playground at the printed URL (typically http://localhost:2024/dev). The graph ID is `agent` and is exported via `agent.py:main_agent`.

## Environment

Place keys in `.env` (referenced by `langgraph.json`). At least one Gemini key is required:

```
GOOGLE_API_KEY=your_key
# Optional rotations
GOOGLE_API_KEY_1=...
GOOGLE_API_KEY_2=...
```

## Graph topology

```
START → router ─┬─ fastpath → query_agent → verify → reflect → END
                └─ agent    → planner ─┬─ resolve → (exec_mutation | query_agent | verify) → ...
                                      ├─ exec_mutation → verify → reflect → END
                                      ├─ query_agent   → verify → reflect → END
                                      ├─ chat → END
                                      └─ end
```

- router: Deterministically detects ID-style queries (trip/vehicle/owner/load/user/driver) and routes fastpath; otherwise routes to planner.
- planner (Gemini): Parses natural language into `task_type` and `entities`. Normalizes intents and decides next step. If entity IDs are missing but hints (name/plate/email/phone/company) exist, routes to `resolve`.
- resolve: Looks up IDs via SQLAlchemy (exact-case-insensitive matching). Fills `entities` and routes to `query_agent` (for queries) or `exec_mutation` (for mutations). If still incomplete, sets `last_result={status:'incomplete', message:'...'}` and routes to `verify`.
- exec_mutation: Calls DB mutation tools (register_owner, register_user, add_vehicle, add_trip, add_expense, create_load, assign_load_to_trip, add_location_update) with required field checks.
- query_agent: Calls DB read tools (get_trip_details, get_vehicle_summary, get_owner_summary, get_load_details, get_user_expenses) for the given `id`.
- verify: Minimal checks; forwards the result.
- reflect: Formats a compact key:value answer and ends the turn.
- chat (Gemini): Concise reply for general chat or non-actionable asks.

## State contract

Input (to main_agent.invoke):
- `messages`: list of LangChain Message objects (optional; for chat continuity)
- `user_input`: string (required)

Internal state fields:
- `intent`: normalized intent string (e.g., `trip_details`, `add_trip`, `chat`)
- `entities`: dict of extracted fields (ids, names, plates, etc.)
- `next_action`: routing hint between nodes
- `last_result`: tool/mutation result dict for verify/reflect
- `messages`: updated message list with final AIMessage set by `reflect` or `chat`

Output:
- Updated state dict containing `messages` with the final AIMessage content.

## Examples (PowerShell API call)

```powershell
# Example: query vehicle by plate
$body = @{ input = @{ user_input = "vehicle MH01AB1234" } } | Convert-ToJson -Depth 5
Invoke-RestMethod -Method Post -Uri http://localhost:2024/graphs/agent/runs -Body $body -ContentType 'application/json'
```

## Troubleshooting

- No response/empty: Try a smaller ID that exists in `logistics.db`.
- Planner errors: Ensure `GOOGLE_API_KEY` is set; fallback is a friendly error.
- Resolution failed: The system returns `incomplete` with missing fields listed.
- Agent import: `agent.py` must export `main_agent` (currently re-exports `graph.build.main_graph`).

## Notes

- Reflection omits nested dict/list fields to keep answers compact.
- Fast-path queries avoid LLM calls entirely.
- All turns end immediately after reflect or chat, preventing tool/LLM loops.
