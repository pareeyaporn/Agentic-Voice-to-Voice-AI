"""
Compiles the LangGraph StateGraph (§2.1) from the real node implementations
in router.py/planner.py/retriever.py/answerer.py.

Node graph: Router -> Planner -> Retriever -> Answerer/Critic, with one
conditional edge out of Router: to safe_refusal if safety_flag is set, to
out_of_scope if the intent isn't a shopping request (safety wins when both
apply), else to Planner. Both short-circuit routes skip Planner/Retriever/
Answerer entirely. The rag-vs-web decision is NOT another edge -- it's
`plan['use_web']` data, read as a plain `if` inside Retriever. See
Architecture/graph_state_flow.mermaid.

**Invoke with `await graph.ainvoke(...)`, not `graph.invoke(...)`** --
retriever_node is async (calls MCP tools via a persistent client,
mcp_client.py), so the whole graph needs the async entrypoint.
"""

from typing import Literal

from langgraph.graph import END, StateGraph

from answerer import answerer_node
from planner import planner_node
from retriever import retriever_node
from router import out_of_scope_node, router_node, safe_refusal_node
from state import GraphState


def route_after_router(state: GraphState) -> Literal["safe_refusal", "out_of_scope", "planner"]:
    if state.get("safety_flag"):
        return "safe_refusal"
    if state.get("intent") == "out_of_scope":
        return "out_of_scope"
    return "planner"


def build_graph():
    builder = StateGraph(GraphState)
    builder.add_node("router", router_node)
    builder.add_node("safe_refusal", safe_refusal_node)
    builder.add_node("out_of_scope", out_of_scope_node)
    builder.add_node("planner", planner_node)
    builder.add_node("retriever", retriever_node)
    builder.add_node("answerer", answerer_node)

    builder.set_entry_point("router")
    builder.add_conditional_edges(
        "router",
        route_after_router,
        {"safe_refusal": "safe_refusal", "out_of_scope": "out_of_scope", "planner": "planner"},
    )
    builder.add_edge("planner", "retriever")
    builder.add_edge("retriever", "answerer")
    builder.add_edge("answerer", END)
    builder.add_edge("safe_refusal", END)
    builder.add_edge("out_of_scope", END)

    return builder.compile()


graph = build_graph()
