from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from llms import DEFAULT_MODEL
from ..state import CoreState
from ..prompts import DETAILED_CHAT_SYSTEM
import re

CHAT_SYSTEM = DETAILED_CHAT_SYSTEM


def chat_node(state: CoreState) -> CoreState:
    messages = state.get("messages", [])
    user_input = state.get("user_input", "")
    sys = SystemMessage(content=CHAT_SYSTEM)
    convo = [sys, HumanMessage(content=user_input)]
    # Greeting / small-talk shortcut (avoid model cost)
    lower = user_input.lower()
    greeting_pattern = re.compile(r"\b(hi|hello|hey|namaste|namaskar|hola)\b|kaise ho|how are you", re.I)
    if greeting_pattern.search(lower):
        content = (
            "Hi! I'm ready to help with drivers, vehicles, trips, loads and expenses. "
            "Tell me what you'd like to do."
        )
        messages.append(AIMessage(content=content))
        state["messages"] = messages
        state["next_action"] = "end"
        return state

    content = "I can help with trips, vehicles, loads, and expenses."
    try:
        if DEFAULT_MODEL is None:
            raise RuntimeError("No default LLM configured")
        resp = DEFAULT_MODEL.invoke(convo)
        text = getattr(resp, "content", None)
        if text:
            content = text
    except Exception as e:
        content = f"Sorry, I couldn't process that right now. ({e})"
    messages.append(AIMessage(content=content))
    state["messages"] = messages
    state["next_action"] = "end"
    return state
