"""
Planner node (§2.3): rule-based, no LLM call. use_rag is always True;
use_web comes from a keyword rule -- a simple binary decision, not worth
the added cost/latency of a model call.

Rule + rationale: Code/6. Prompts & Documentation/planner_rules.md
(not an LLM prompt -- see that file).
"""

from state import GraphState

WEB_SIGNAL_KEYWORDS = [
    "current", "latest", "now", "today", "right now", "currently",
    "in stock", "available", "still available", "on sale",
]


def decide_use_web(query: str) -> bool:
    """Case-insensitive substring match against WEB_SIGNAL_KEYWORDS."""
    q = query.lower()
    return any(kw in q for kw in WEB_SIGNAL_KEYWORDS)


def planner_node(state: GraphState) -> GraphState:
    state["plan"] = {"use_rag": True, "use_web": decide_use_web(state["query"])}
    return state
