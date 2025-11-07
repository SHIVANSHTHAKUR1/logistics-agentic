# Twilio Workflows Guide (Owner • Driver • Customer)

This guide explains how to run the same agentic logistics workflow over SMS/WhatsApp with Twilio, including role-based flows, message patterns, missing-field prompts, and wiring the inbound webhook to your existing LangGraph agent.

- Audience: product/dev teams integrating the current agent into Twilio
- Channels: SMS and WhatsApp (Twilio Sandbox or approved WhatsApp sender)
- Style: short, skimmable messages; deterministic tool calls chosen by the Planner node

---

## Overview

Your agent is a modular LangGraph pipeline:
- router → planner → resolve → query/exec_mutation → verify → reflect → (optional loop back to planner)
- Deterministic tools live in `tools/database_tools.py` (SQLite + SQLAlchemy)
- The Planner decides which tool to call. Reflect returns a concise, SMS-friendly response.

For Twilio, you’ll receive inbound messages, hand them to the graph as `user_input`, and reply with the last AIMessage content.

---

## Prerequisites

- Twilio account with an SMS number and/or WhatsApp sender
- Web server reachable by Twilio (public HTTPS; can be via ngrok for dev)
- Python env with your project installed and DB (`logistics.db`) accessible
- Recommended env flags:
  - `AUTO_LOOP=1` to let the graph auto-continue for incomplete inputs
  - `MAX_AUTO_ITERS=2` to keep interactions tight over SMS
  - `STRUCTURED_OUTPUT=` (leave empty to return SMS-friendly text)

---

## Identity & Sessions over SMS/WhatsApp

- Identify users by their phone number (`From` in Twilio webhook). Map it to `users.phone_number`.
- If unknown number:
  - Start a lightweight registration flow: ask for role (customer/driver/owner) + basics
  - For customers/drivers, we prefer that an owner pre-registers them, but on-the-fly creation is supported (see Owner flow).
- Keep a lightweight session store (Flask session/Redis) to preserve `state.entities` between turns.
- For multi-tenant use, associate phone numbers with `owner_id` once known to avoid ambiguity.

---

## Message Formatting Guidelines

- Keep messages < 600 characters; reflect already returns compact bullets
- Avoid long JSON in SMS; the graph returns JSON only if `STRUCTURED_OUTPUT=json`
- Use clear prompts for missing fields (verify/reflect already do this)
- Use 1 question per line; users can reply with the needed field

---

## Role-based Workflows

Below are suggested commands and how the agent responds. All are free text—the Planner chooses the right tool.

### Customer

Primary tasks: Create loads, check status, add optional details.

- Create a load
  - Message: `create load pickup 221B Baker St, dest 10 Downing St for me`
  - Missing fields prompts (if any): pickup_address, destination_address, optionally weight_kg/description
  - After complete: returns load_id and summary; you can ask “load 42 details” later

- Track a load
  - Message: `load 42` or `load id 42`
  - Response: status, pickup/destination, optional assigned trip info

- Optional updates (owner/driver usually do this, but supported via NL update if authorized)
  - Message: `set load 42 status in_transit`

Notes:
- Customers typically don’t assign loads to trips; owners dispatch. The agent will ask for missing fields or deny if not authorized.

### Driver

Primary tasks: Trips, expenses, optional location updates.

- Start a trip
  - Message: `start trip vehicle MH12AB1234`
  - Agent resolves vehicle_id from plate, maps your phone to driver_id, and creates trip

- Add expense
  - Message: `expense 500 fuel for trip 7 note diesel`
  - Missing prompts: expense_type/amount/trip_id (trip optional; expense can be standalone but driver_id is required)

- Location update
  - Message: `loc 12.976,77.603 for trip 7`
  - Stored via `add_location_update`

- Complete trip
  - Message: `mark trip 7 completed`

- Driver expenses summary
  - Message: `my expenses` or `driver 3 expenses`

### Owner

Primary tasks: Register users, add vehicles, dispatch loads to trips, query summaries.

- Register a customer/driver (owner defaults to id 1 if missing)
  - Message: `add customer name John Doe email john@example.com number 9876543210`
  - Internally calls `register_user` with `role=customer`; `owner_id` defaults to 1 if unspecified

- Add vehicle
  - Message: `add vehicle plate MH12AB1234 capacity 8000`

- Assign load to trip
  - Message: `assign load 9 to trip 5` or `assign trip 5 to load 9`

- Owner summary
  - Message: `owner 1` → counts of users, trips, loads, expenses

- Vehicle/trip details
  - Message: `vehicle 3` or `trip 5`

- Natural-language update
  - Message: `set vehicle 5 status maintenance` or `change user 2 name to Mahesh Kumar`

---

## Missing Fields & Guidance

When required fields are missing, the agent replies with:
- “Missing information” header
- Required fields: `owner_id`, `driver_id`, `vehicle_id`, etc.
- Specific questions (one per line) you can respond to directly
- Optional suggestions (e.g., `weight_kg`, `description` for loads)

These prompts are already optimized for SMS readability.

---

## Twilio Webhook Wiring (Flask example)

Below is a minimal inbound webhook. It maps From → user phone, invokes the graph, and returns a TwiML reply. Adjust paths to your app.

```python
# web_twilio.py
from flask import Flask, request, Response
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
import os

from graph.build import main_graph

app = Flask(__name__)

# Optional: Verify Twilio signature
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
validator = RequestValidator(TWILIO_AUTH_TOKEN) if TWILIO_AUTH_TOKEN else None

@app.route("/twilio/inbound", methods=["POST"])
def inbound():
    if validator:
        # Validate Twilio signature
        signature = request.headers.get("X-Twilio-Signature", "")
        url = request.url
        params = request.form.to_dict()
        if not validator.validate(url, params, signature):
            return Response("Forbidden", status=403)

    from_number = request.form.get("From", "")
    body = request.form.get("Body", "").strip()

    # Prepare initial graph state
    state = {
        "messages": [],
        "user_input": body,
        # Persist across turns in your session store (e.g., Flask session/Redis)
        "entities": {"phone_number": from_number},
        # Enable internal loop for follow-up prompts on SMS
        "auto_loop": True,
        "max_iterations": int(os.getenv("MAX_AUTO_ITERS", 2)),
    }

    result = main_graph.invoke(state)
    # Take the last AI message content (reflect or chat)
    content = ""
    msgs = result.get("messages", [])
    if msgs:
        content = getattr(msgs[-1], "content", "") or ""
    if not content:
        content = result.get("summary", "I didn’t find anything to respond with.")

    # Build TwiML response
    twiml = MessagingResponse()
    twiml.message(content[:1600])  # protect against overly long messages
    return Response(str(twiml), mimetype="application/xml")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
```

Expose this endpoint publicly and configure Twilio:
- SMS: Console → Phone Numbers → Your Number → A Messaging webhook → `https://<your-host>/twilio/inbound`
- WhatsApp: Console → Messaging → WhatsApp Senders → Configure Webhook

---

## Try it locally (no Twilio signature)

1) Start the inbound server (keep TWILIO_AUTH_TOKEN unset for local tests):

```powershell
# Windows PowerShell
$env:AUTO_LOOP = "1"
$env:MAX_AUTO_ITERS = "2"
C:/Users/shiva/OneDrive/Desktop/logistics/venv/Scripts/python.exe c:/Users/shiva/OneDrive/Desktop/logistics/twilio_app.py
```

2) In another terminal, send a test message using the included client:

```powershell
# Trip details
C:/Users/shiva/OneDrive/Desktop/logistics/venv/Scripts/python.exe c:/Users/shiva/OneDrive/Desktop/logistics/twilio_test_client.py --body "trip 5"

# Assign load to trip
C:/Users/shiva/OneDrive/Desktop/logistics/venv/Scripts/python.exe c:/Users/shiva/OneDrive/Desktop/logistics/twilio_test_client.py --body "assign load 9 to trip 5"

# WhatsApp-style From number
C:/Users/shiva/OneDrive/Desktop/logistics/venv/Scripts/python.exe c:/Users/shiva/OneDrive/Desktop/logistics/twilio_test_client.py --body "create load pickup A, dest B" --whatsapp --from "+919999888877"
```

3) When moving to real Twilio, set `TWILIO_AUTH_TOKEN` and point the Messaging webhook to your public `/twilio/inbound` URL (e.g., via ngrok).

---

## WhatsApp Templates (Optional)

- For business-initiated messages, create and get WhatsApp templates approved
- For user-initiated inbound, free-form is allowed within the 24-hour window
- You can keep the agent response plain text; interactive buttons are optional

---

## Error Handling & Idempotency

- Validate Twilio signature to avoid spoofing
- Use `MessageSid` from Twilio to deduplicate if you retry processing
- Handle transient DB errors with safe retries; Reflect will surface concise error text

---

## Authorization Tips

- Restrict write operations by phone number → mapped `users.role` and `owner_id`
- Example: Only drivers can `add_expense`; only owners can `assign_load_to_trip`
- If role is unknown, agent asks clarifying questions before mutations

---

## Examples (Copy/Paste)

- Customer: `create load pickup Electronic City, dest Indiranagar`
- Customer: `load 42`
- Driver: `expense 350 toll for trip 7`
- Driver: `mark trip 7 completed`
- Owner: `add vehicle plate KA03MN1234 capacity 9000`
- Owner: `assign load 9 to trip 5`
- Owner: `add customer name Jane Doe email jane@x.com number 9998887776`
- Anyone: `trip 5`

---

## Troubleshooting

- Bot asks for `owner_id` when adding a user: default is now `owner_id=1` if not specified
- Agent keeps asking for fields: reply with exact values (e.g., `driver id 3`, `vehicle plate KA03MN1234`)
- Too chatty or long replies: reduce `MAX_AUTO_ITERS` and keep messages short

---

## Next Steps

- Add a phone-number → user bootstrap script to seed known drivers/customers
- Add a rate limiter (e.g., per From number) to prevent abuse
- Consider a Redis-backed session to persist entities between turns reliably in production
- Optionally add a small “menu” reply for unknown numbers with role selection shortcuts
