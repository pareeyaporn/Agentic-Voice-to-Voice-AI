"""
Router node (§2.2): one structured-output LLM call does intent
classification, constraint extraction, and safety-flag detection together.

System prompt: Code/6. Prompts & Documentation/router_system_prompt.md

Known gap: `intent` is computed but not persisted to GraphState (kept to
the 8-field schema, §2.1) -- an out_of_scope query still flows through
Planner/Retriever/Answerer instead of short-circuiting.
"""

import os
from typing import Literal, Optional

from pydantic import BaseModel, Field

from config import LLM_MODEL, LLM_PROVIDER, PROMPTS_DIR
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

router_llm = get_chat_model(LLM_PROVIDER, LLM_MODEL, temperature=0).with_structured_output(RouterOutput)


def classify_transcript(transcript: str) -> RouterOutput:
    return invoke_and_log(router_llm, "router", ROUTER_SYSTEM_PROMPT, transcript)


def router_node(state: GraphState) -> GraphState:
    result = classify_transcript(state["transcript"])
    state["query"] = result.query
    state["constraints"] = result.constraints.model_dump(exclude_none=True)
    state["safety_flag"] = result.safety_flag
    return state


def safe_refusal_node(state: GraphState) -> GraphState:
    """Reached only when Router's safety_flag is set. Skips Planner/Retriever/Answerer."""
    state["final_answer"] = f"I can't help with that: {state['safety_flag']}"
    return state
