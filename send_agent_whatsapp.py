import os
import json
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
from twilio.rest import Client
from loguru import logger
from graph.build import main_graph

STATE_FILE = Path("agent_sessions.json")

def load_state() -> Dict[str, Dict[str, Any]]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception as e:
            logger.warning(f"Failed to read state file: {e}")
    return {}

def save_state(state: Dict[str, Dict[str, Any]]):
    try:
        STATE_FILE.write_text(json.dumps(state))
    except Exception as e:
        logger.error(f"Failed to write state file: {e}")

def invoke_agent(phone: str, user_input: str, sessions: Dict[str, Dict[str, Any]]) -> str:
    container = sessions.get(phone)
    if not container:
        container = {"messages": [], "entities": {"phone_number": phone}}
        sessions[phone] = container
    state = {
        "messages": container["messages"],
        "user_input": user_input,
        "entities": container["entities"],
        "auto_loop": os.getenv("AUTO_LOOP") == "1",
        "max_iterations": int(os.getenv("MAX_AUTO_ITERS", 2)),
    }
    result = main_graph.invoke(state)
    # Extract last assistant message
    reply = "No response." 
    for msg in reversed(result.get("messages", []) or []):
        c = getattr(msg, "content", None)
        if c:
            reply = c
            break
    # Persist back
    container["messages"] = result.get("messages", container["messages"]) or []
    ents = result.get("entities", {}) or {}
    if ents:
        merged = dict(container["entities"])
        merged.update(ents)
        container["entities"] = merged
    return reply

def main():
    load_dotenv()
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    whatsapp_from = os.getenv("TWILIO_WHATSAPP_NUMBER")
    target = os.getenv("TARGET_WHATSAPP") or "+918968808710"

    if not (account_sid and auth_token and whatsapp_from):
        logger.error("Missing Twilio environment variables. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER")
        return

    client = Client(account_sid, auth_token)

    sessions = load_state()
    try:
        import argparse
        parser = argparse.ArgumentParser(description="Send agent reply to WhatsApp via Twilio")
        parser.add_argument("--loop", action="store_true", help="Run interactive loop until 'exit'")
        parser.add_argument("--to", dest="to", default=target, help="Target WhatsApp number (e.g., +918968808710)")
        args = parser.parse_args()

        def send_once(to_number: str):
            user_input = input("You: ")
            if not user_input.strip():
                logger.info("Empty input. Skipping.")
                return False
            if user_input.lower() == "exit":
                return True
            reply = invoke_agent(to_number, user_input, sessions)
            print(f"Agent: {reply}")
            message = client.messages.create(
                from_=f"whatsapp:{whatsapp_from}",
                to=f"whatsapp:{to_number}",
                body=reply
            )
            logger.info(f"Sent WhatsApp message SID: {message.sid}")
            return False

        if args.loop:
            print("Interactive mode. Type 'exit' to quit.")
            while True:
                should_exit = send_once(args.to)
                if should_exit:
                    logger.info("Exit requested.")
                    break
        else:
            print("One-shot mode. Enter a single message:")
            send_once(args.to)
    finally:
        save_state(sessions)

if __name__ == "__main__":
    main()
