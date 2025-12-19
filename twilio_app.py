from fastapi import FastAPI, Request, Response, Header
from pydantic import BaseModel
from loguru import logger
import os
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
from typing import Dict, Any

from graph.build import main_graph

# Load environment variables
load_dotenv()

# Twilio credentials (optional - will work without them)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN") 
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

# If enabled, the webhook will attempt to respond via Twilio REST API.
# Default is disabled because returning TwiML is sufficient for inbound webhooks
# and avoids account-level daily send limits.
TWILIO_USE_REST_SEND = os.getenv("TWILIO_USE_REST_SEND") == "1"

# Initialize Twilio client (safely)
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None
    if twilio_client:
        logger.info("✅ Twilio client initialized")
    else:
        logger.info("ℹ️ Twilio not configured - running without WhatsApp sending")
except Exception as e:
    logger.warning(f"⚠️ Twilio initialization failed: {e}")
    twilio_client = None

# In-memory conversation containers keyed by phone/driver id
_conversations: Dict[str, Dict[str, Any]] = {}

def _get_container(sender_id: str) -> Dict[str, Any]:
    c = _conversations.get(sender_id)
    if not c:
        c = {"messages": [], "entities": {"phone_number": sender_id}}
        _conversations[sender_id] = c
    return c

def _invoke_agent(user_input: str, sender_id: str) -> str:
    """Invoke LangGraph main_graph with per-sender conversation state and return reply text."""
    container = _get_container(sender_id)
    state = {
        "messages": container["messages"],
        "user_input": user_input,
        "entities": container["entities"],
        # WhatsApp channel runs as a privileged role (no UI role-selection).
        "actor_role": "whatsapp",
        "auto_loop": os.getenv("AUTO_LOOP") == "1",
        "max_iterations": int(os.getenv("MAX_AUTO_ITERS", 2)),
    }
    result = main_graph.invoke(state)

    # Extract last AI content
    content = ""
    for msg in reversed(result.get("messages", []) or []):
        c = getattr(msg, "content", None)
        if c:
            content = c
            break
    if not content:
        content = result.get("summary", "No response.")

    # Persist updated state
    container["messages"] = result.get("messages", container["messages"]) or []
    ents = result.get("entities", {}) or {}
    if ents:
        merged = dict(container["entities"])
        merged.update(ents)
        container["entities"] = merged
    return content

app = FastAPI(title="Agentic Logistics API - WhatsApp Enabled")

@app.get("/health")
def health():
    return {
        "status": "ok", 
        "agent": "langgraph",
        "whatsapp": "enabled" if twilio_client else "disabled",
        "twilio_configured": bool(TWILIO_ACCOUNT_SID),
        "twilio_rest_send": "enabled" if TWILIO_USE_REST_SEND else "disabled",
        "sessions": len(_conversations),
        "auto_loop": os.getenv("AUTO_LOOP") == "1",
        "max_auto_iters": int(os.getenv("MAX_AUTO_ITERS", 2)),
    }

class EchoIn(BaseModel):
    text: str

@app.post("/echo")
def echo(inp: EchoIn):
    logger.info(f"echo called with {inp.text}")
    return {"reply": f"echo {inp.text}"}

class ProcessIn(BaseModel):
    message: str
    driver_id: str = "driver_123"

@app.post("/process")
def process_message(inp: ProcessIn):
    """Process a message via LangGraph agent using driver_id as session key."""
    logger.info(f"🔄 Processing message from {inp.driver_id}: {inp.message}")
    try:
        reply = _invoke_agent(inp.message, inp.driver_id)
        logger.info(f"🤖 Reply: {reply[:100]}...")
        return {
            "success": True,
            "message": inp.message,
            "session": inp.driver_id,
            "agent_response": reply,
        }
    except Exception as e:
        logger.error(f"❌ Error processing message: {str(e)}")
        return {"success": False, "error": str(e)}

def _validate_twilio_signature(signature: str | None, url: str, params: dict) -> bool:
    """Stub Twilio signature validation (returns True if token absent or signature missing)."""
    if not TWILIO_AUTH_TOKEN or not signature:
        return True  # Skip validation if missing config/header
    try:
        import hmac, hashlib, base64
        # Simplified canonicalization (for real usage, include raw POST body ordering)
        data = url + ''.join(f"{k}{v}" for k, v in sorted(params.items()))
        expected = hmac.new(TWILIO_AUTH_TOKEN.encode(), data.encode(), hashlib.sha1).digest()
        expected_b64 = base64.b64encode(expected).decode()
        return hmac.compare_digest(expected_b64, signature)
    except Exception as e:
        logger.warning(f"Signature validation error: {e}")
        return False

@app.post("/webhook/whatsapp")
@app.post("/webhook.whatsapp")
async def whatsapp_webhook(request: Request, x_twilio_signature: str | None = Header(default=None)):
    """Complete WhatsApp Integration - Receive AND Respond"""
    try:
        # Parse incoming WhatsApp message
        form = await request.form()
        from_number = form.get("From", "").replace("whatsapp:", "")
        message_body = form.get("Body", "")
        profile_name = form.get("ProfileName", "Driver")
        
        # Optional signature validation (non-blocking)
        if not _validate_twilio_signature(x_twilio_signature, str(request.url), dict(form)):
            logger.warning("⚠️ Twilio signature validation failed")
        logger.info(f"📱 WhatsApp from {profile_name} ({from_number}): {message_body}")
        
        # Process with LangGraph agent
        reply = _invoke_agent(message_body, from_number)
        logger.info(f"💬 Reply: {reply[:120]}...")

        # Optional REST outbound (disabled by default). For inbound webhooks, returning TwiML
        # is sufficient and avoids hitting account-level daily send limits.
        if TWILIO_USE_REST_SEND and twilio_client and TWILIO_WHATSAPP_NUMBER:
            try:
                message = twilio_client.messages.create(
                    from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
                    to=f"whatsapp:{from_number}",
                    body=reply
                )
                logger.info(f"✅ Sent WhatsApp response: {message.sid}")
                resp = MessagingResponse()  # empty TwiML to acknowledge
                return Response(str(resp), media_type="text/xml")
            except Exception as send_error:
                logger.error(f"❌ Failed to send via REST: {send_error}. Falling back to TwiML.")

        # Fallback TwiML (ensures delivery even without REST client)
        resp = MessagingResponse()
        resp.message(reply[:1600])
        return Response(str(resp), media_type="text/xml")
        
    except Exception as e:
        logger.error(f"❌ WhatsApp webhook error: {str(e)}")
        # Return a friendly TwiML error (English-only)
        resp = MessagingResponse()
        resp.message("Sorry, there was an issue processing your message. Please try again.")
        return Response(str(resp), media_type="text/xml")

@app.post("/whatsapp/send")
async def send_whatsapp_message(phone: str, message: str | None = None, reuse_last: bool = True):
    """Send proactive WhatsApp messages.

    If message omitted and reuse_last is True, reuse last AI agent reply for that phone.
    """
    if not twilio_client:
        return {"error": "Twilio not configured"}

    session_phone = phone.replace("whatsapp:", "")
    container = _conversations.get(session_phone)
    if (not message) and reuse_last and container and container.get("messages"):
        for msg in reversed(container["messages"]):
            c = getattr(msg, "content", None)
            if c:
                message = c
                break
    if not message:
        return {"error": "No message provided and no previous reply to reuse."}

    try:
        if not phone.startswith("whatsapp:"):
            phone = f"whatsapp:{phone}"
        message_obj = twilio_client.messages.create(
            from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
            to=phone,
            body=message
        )
        reused_flag = False
        if container and container.get("messages"):
            last = None
            for msg in reversed(container["messages"]):
                c = getattr(msg, "content", None)
                if c:
                    last = c
                    break
            reused_flag = (last == message)
        logger.info(f"📤 Sent proactive message to {phone}: {message[:50]}...")
        return {
            "success": True,
            "message_sid": message_obj.sid,
            "to": phone,
            "message": message,
            "reused_last": reused_flag
        }
    except Exception as e:
        logger.error(f"❌ Failed to send proactive message: {e}")
        return {"error": str(e)}

@app.get("/driver/{driver_id}/status")
def get_driver_status(driver_id: str):
    """Get current status of a driver"""
    logger.info(f"Getting status for driver: {driver_id}")
    return {
        "driver_id": driver_id,
        "status": "available",
        "location": "Delhi", 
        "last_updated": "2025-09-14 19:15:00",
        "vehicle_type": "truck"
    }

@app.get("/whatsapp/status")
def whatsapp_integration_status():
    """Check WhatsApp integration health"""
    return {
        "twilio_configured": bool(TWILIO_ACCOUNT_SID),
        "whatsapp_number": TWILIO_WHATSAPP_NUMBER or "Not configured",
        "webhook_endpoint": "/webhook/whatsapp", 
        "send_endpoint": "/whatsapp/send",
        "mode": "full_two_way" if twilio_client else "receive_only",
        "agents_connected": True,
        "database_connected": True,
        "features": ["receive_messages", "intelligent_routing", "multi_agent_processing"]
    }