from langgraph.graph import StateGraph, START, END
from .state import CoreState
from .router import intent_router_node
from .agents.query_agent import query_agent_node
from .agents.planner import planner_node
from .agents.exec_mutation import exec_mutation_node
from .nodes.verify import verify_node
from .nodes.reflect import reflect_node
from .nodes.chat import chat_node
from .nodes.resolve import resolve_node


def build_graph():
    g = StateGraph(CoreState)
    g.add_node("router", intent_router_node)
    g.add_node("query_agent", query_agent_node)
    g.add_node("planner", planner_node)
    g.add_node("exec_mutation", exec_mutation_node)
    g.add_node("chat", chat_node)
    g.add_node("resolve", resolve_node)
    g.add_node("verify", verify_node)
    g.add_node("reflect", reflect_node)

    # Entry
    g.add_edge(START, "router")

    def decide(state: CoreState) -> str:
        return state.get("next_action", "end")

    # Router transitions
    g.add_conditional_edges(
        "router",
        decide,
        {
            "fastpath": "query_agent",
            # 'agent' now routes to planner for complex or mutation tasks
            "agent": "planner",
            # allow router to dispatch safe mutations directly (e.g., nl_update)
            "exec_mutation": "exec_mutation",
            "end": END,
        }
    )

    # Planner branching
    g.add_conditional_edges(
        "planner",
        decide,
        {
            "resolve": "resolve",
            "exec_mutation": "exec_mutation",
            "query_agent": "query_agent",
            "chat": "chat",
            "end": END,
        }
    )

    # Resolve branching
    g.add_conditional_edges(
        "resolve",
        decide,
        {
            "exec_mutation": "exec_mutation",
            "query_agent": "query_agent",
            "verify": "verify",  # if resolve sets incomplete / last_result
            "chat": "chat",
            "end": END,
        }
    )

    # Mutation → verify
    g.add_edge("exec_mutation", "verify")
    # Chat ends directly (chat node sets next_action=end)

    g.add_edge("query_agent", "verify")
    g.add_edge("verify", "reflect")

    # Reflect can either end or loop back to planner, controlled by reflect_node's next_action
    g.add_conditional_edges(
        "reflect",
        decide,
        {
            "loop": "planner",
            "end": END,
        }
    )

    return g.compile()


main_graph = build_graph()
