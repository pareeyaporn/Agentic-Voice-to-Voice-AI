"""
Graph state schema (§2.1). Matches the 8-field list agreed on in design --
transcript, query, constraints, safety_flag, plan, tool_results, citations,
final_answer -- no multi-turn/history tracking yet (deferred, see the design
notebook). tool_results is one nested dict rather than three top-level fields.
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

    transcript: str  # raw ASR output (input)
    query: str  # Router: normalized search query
    constraints: Dict[str, Any]  # Router: budget/brand/category/etc.
    safety_flag: Optional[str]  # Router: reason string, or None
    plan: Plan  # Planner: sourcing decision
    tool_results: ToolResults  # Retriever: reconciled MCP results
    citations: List[Dict[str, Any]]  # Answerer: {source, doc_id, url, title} per claim -- doc_id/url are exclusive per source (rag/web)
    final_answer: Optional[str]  # Answerer: spoken-summary text


EMPTY_STATE: GraphState = {
    "transcript": "",
    "query": "",
    "constraints": {},
    "safety_flag": None,
    "plan": {"use_rag": None, "use_web": None},
    "tool_results": {"products": [], "conflicts": [], "errors": []},
    "citations": [],
    "final_answer": None,
}
