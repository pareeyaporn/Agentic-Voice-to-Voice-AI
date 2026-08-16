"""
Compiles the LangGraph StateGraph (§2.1) from the real node implementations
in router.py/planner.py/retriever.py/answerer.py.

Node graph: Router -> Planner -> Retriever -> Answerer/Critic, with a
safety_flag branch out of Router straight to safe_refusal (skips
Planner/Retriever/Answerer entirely).

Only one graph-level conditional edge: Router -> safe_refusal vs.
Router -> Planner, on whether safety_flag got set. The rag-vs-web decision
is NOT a second edge -- it's plan['use_web'] data, read as a plain `if`
inside the Retriever node (a choice within one node, not a choice between
nodes). See Architecture/graph_state_flow.mermaid.

This module is what a real importer (§2.7's testing notebook, and eventually
§5's Streamlit UI) imports -- see the design notebook's file-format note.

**Invoke with `await graph.ainvoke(...)`, not `graph.invoke(...)`** -- since
the Retriever swap, retriever_node is async (it calls MCP tools through a
persistent client, mcp_client.py). LangGraph runs mixed sync/async nodes in
one graph fine (verified directly, not assumed), but the whole graph has to
be driven with the async entrypoint once any node is async.
"""

from typing import Literal

from langgraph.graph import END, StateGraph

from answerer import answerer_node
from planner import planner_node
from retriever import retriever_node
from router import router_node, safe_refusal_node
from state import GraphState


def route_after_router(state: GraphState) -> Literal["safe_refusal", "planner"]:
    return "safe_refusal" if state.get("safety_flag") else "planner"


def build_graph():
    builder = StateGraph(GraphState)
    builder.add_node("router", router_node)
    builder.add_node("safe_refusal", safe_refusal_node)
    builder.add_node("planner", planner_node)
    builder.add_node("retriever", retriever_node)
    builder.add_node("answerer", answerer_node)

    builder.set_entry_point("router")
    builder.add_conditional_edges(
        "router", route_after_router, {"safe_refusal": "safe_refusal", "planner": "planner"}
    )
    builder.add_edge("planner", "retriever")
    builder.add_edge("retriever", "answerer")
    builder.add_edge("answerer", END)
    builder.add_edge("safe_refusal", END)

    return builder.compile()


graph = build_graph()
