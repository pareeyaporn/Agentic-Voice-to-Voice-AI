"""
Graph state schema (§2.1). The original 8-field list agreed on in design --
transcript, query, constraints, safety_flag, plan, tool_results, citations,
final_answer -- plus `intent`, added later so out-of-scope queries can
short-circuit at the Router instead of flowing through the full pipeline
(closing §2.2's known gap). tool_results is one nested dict rather than three
top-level fields.

`context_note`, added later still, is a deliberately small memory feature --
carries only the immediately preceding turn's query+answer forward (not a
full conversation history, no persistence across sessions), so a vague
follow-up like "what about something cheaper" can resolve against real prior
context instead of running standalone. Built by the UI layer from its own
in-memory last-turn state (session_state / React state -- never localStorage,
lost on refresh) and read only by the Router; it's not itself a graph field
any node other than Router touches.
"""

from typing import Any, Dict, List, Optional, TypedDict


class Plan(TypedDict):
    """Written by the Planner node. Pure data -- no tool calls happen here."""

    use_rag: bool
    use_web: bool


class ToolResults(TypedDict):
    """Written by the Retriever node after calling MCP tools (rag.search / web.search)."""

    products: List[Dict[str, Any]]
    conflicts: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]


class GraphState(TypedDict):
    """Shared state passed between every node in the graph. See
    Architecture/graph_state_flow.mermaid for which node reads/writes what."""

    transcript: str  # raw ASR output (input) -- never mutated with injected context, stays clean for display/editing
    context_note: Optional[str]  # (input, optional) previous turn's query+answer, read only by Router
    intent: str  # Router: product_search | comparison | follow_up | out_of_scope
    query: str  # Router: normalized search query
    constraints: Dict[str, Any]  # Router: budget/brand/category/etc.
    safety_flag: Optional[str]  # Router: reason string, or None
    plan: Plan  # Planner: sourcing decision
    tool_results: ToolResults  # Retriever: reconciled MCP results
    citations: List[Dict[str, Any]]  # Answerer: {source, doc_id, url, title} per claim -- doc_id/url are exclusive per source (rag/web)
    final_answer: Optional[str]  # Answerer: spoken-summary text


EMPTY_STATE: GraphState = {
    "transcript": "",
    "context_note": None,
    "intent": "",
    "query": "",
    "constraints": {},
    "safety_flag": None,
    "plan": {"use_rag": None, "use_web": None},
    "tool_results": {"products": [], "conflicts": [], "errors": []},
    "citations": [],
    "final_answer": None,
}
