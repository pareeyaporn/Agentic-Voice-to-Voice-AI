"""
Router node (§2.2): one structured-output LLM call does intent
classification, constraint extraction, and safety-flag detection together.
Uses method="function_calling" (OpenAI's tool-calling API), not the default
json_schema mode -- the charter's LLM guidelines explicitly ask for
function/tool calling to stay in use.

System prompt: Code/6. Prompts & Documentation/router_system_prompt.md

`intent` is persisted to GraphState and an out_of_scope query short-circuits
to `out_of_scope_node` (a polite redirect, no retrieval/LLM cost) -- this
closes what was previously documented here as a known gap. `follow_up` is
treated as in-scope: with no multi-turn history yet (§2.1), running it as a
standalone query beats refusing it.
"""

import os
from typing import Literal, Optional

from pydantic import BaseModel, Field

from config import LLM_MODEL, LLM_PROVIDER, PROMPTS_DIR, require_llm_config
from providers import get_chat_model, invoke_and_log
from state import GraphState


class RouterConstraints(BaseModel):
    budget_min: Optional[float] = Field(None, description="Minimum price in USD, if stated")
    budget_max: Optional[float] = Field(None, description="Maximum price in USD, if stated")
    brand: Optional[str] = Field(None, description="Brand name, if stated")
    category: Optional[str] = Field(None, description="Product category/sub-category, if stated")
    material: Optional[str] = Field(None, description="Material, if stated")
    quantity: Optional[int] = Field(None, description="Quantity/pack size, if stated")


class RouterOutput(BaseModel):
    intent: Literal["product_search", "comparison", "follow_up", "out_of_scope"]
    query: str = Field(description="The transcript rewritten as a clean search query")
    constraints: RouterConstraints
    safety_flag: Optional[str] = Field(None, description="Reason the request itself is unsafe, else null")


with open(os.path.join(PROMPTS_DIR, "router_system_prompt.md")) as f:
    ROUTER_SYSTEM_PROMPT = f.read()

# Built lazily, not at import -- app.py imports the graph even in mock-data
# mode (§5.1), which must work with no .env/API key at all.
_router_llm = None


def _get_router_llm():
    global _router_llm
    if _router_llm is None:
        require_llm_config()
        _router_llm = get_chat_model(LLM_PROVIDER, LLM_MODEL, temperature=0).with_structured_output(
            RouterOutput, method="function_calling"
        )
    return _router_llm


def classify_transcript(transcript: str, context_note: Optional[str] = None) -> RouterOutput:
    """context_note (small memory feature, see state.py's docstring): the
    previous turn's query+answer, if any -- prepended so the Router can
    resolve a vague follow-up ("what about something cheaper") against real
    prior context instead of guessing. None on a session's first turn, same
    as today's behavior."""
    human_content = f"{context_note}\n\nNew request: {transcript}" if context_note else transcript
    return invoke_and_log(_get_router_llm(), "router", ROUTER_SYSTEM_PROMPT, human_content)


def router_node(state: GraphState) -> GraphState:
    result = classify_transcript(state["transcript"], state.get("context_note"))
    state["intent"] = result.intent
    state["query"] = result.query
    state["constraints"] = result.constraints.model_dump(exclude_none=True)
    state["safety_flag"] = result.safety_flag
    return state


def safe_refusal_node(state: GraphState) -> GraphState:
    """Reached only when Router's safety_flag is set. Skips Planner/Retriever/Answerer."""
    state["final_answer"] = f"I can't help with that: {state['safety_flag']}"
    return state


def out_of_scope_node(state: GraphState) -> GraphState:
    """Reached only when Router's intent is out_of_scope (and no safety_flag --
    that route wins). A polite redirect, not a refusal: the query isn't unsafe,
    it's just not a shopping request, so no retrieval/LLM spend happens."""
    state["final_answer"] = (
        "I'm a shopping assistant, so that's outside what I can help with -- "
        "but I'd be happy to find or compare products for you."
    )
    return state
