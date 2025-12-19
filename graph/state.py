from typing import Any, Dict, List, TypedDict, Optional


class CoreState(TypedDict, total=False):
    messages: List[Any]
    user_input: str
    actor_role: str  # customer | driver | owner (UI/session selected mode)
    intent: str
    entities: Dict[str, Any]
    focus: Dict[str, Any]  # Track focused entity (e.g., trip_id) for context carryover
    next_action: str
    last_result: Dict[str, Any]
    summary: str
    error: str
    # Internal loop support
    iteration: int
    max_iterations: int
    auto_loop: bool
