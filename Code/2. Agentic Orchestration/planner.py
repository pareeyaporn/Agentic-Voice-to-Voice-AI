"""
Planner node (§2.3): rule-based, no LLM call. use_rag is always True; use_web
comes from a keyword rule, not a model call -- the decision is a single
binary and the backlog's own framing of the rule was already keyword-based
("skip web.search unless query implies current/latest/now"), so an LLM call
here wasn't worth the added cost/latency.

Rule + rationale: Code/6. Prompts & Documentation/planner_rules.md (the
backlog's CP2 "planner rules" deliverable -- not an LLM prompt, see that file).
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
