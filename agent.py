"""Unified Agent Entrypoint

This file now serves ONLY as a thin compatibility layer re-exporting the new
modular LangGraph pipeline defined under `graph/` (planner, resolve, query,
mutation executor, verify, reflect, chat). The previous monolithic tool-bound
LLM workflow has been deprecated in favor of deterministic routing + targeted
Gemini calls.

Public export: `main_agent` (compiled graph) imported by web_app and any
external integration. For direct programmatic use, call:

    from agent import invoke_agent
    result_state = invoke_agent("vehicle MH01AB1234")
    print(result_state["messages"][-1].content)

Key behaviors:
 - Fast-path ID queries skip the LLM entirely.
 - Planner uses Gemini to derive intent + entities only when needed.
 - Resolve node maps names/plates/emails/phones to IDs before execution.
 - Single mutation or query per turn; reflection produces concise output.
 - Turn ends immediately after reflect/chat. No looping tool calls.

If you need the old agent logic, check previous commits/history; keeping it
here increases maintenance cost and token usage.
"""

from graph.build import main_graph as main_agent

__all__ = ["main_agent", "invoke_agent"]

def invoke_agent(user_input: str, messages=None, entities=None, actor_role: str = "owner"):
    """Convenience helper to invoke the modular graph.

    Args:
        user_input: Raw user string.
        messages: Optional prior LangChain message list for continuity.
    Returns:
        Final state dict produced by the graph (includes messages, intent, entities, etc.).
    """
    state = {
        "messages": messages or [],
        "user_input": user_input,
        "actor_role": actor_role,
    }
    if entities:
        # Allow caller to supply previous partial entities for multi-turn completion
        state["entities"] = dict(entities)
    return main_agent.invoke(state)
