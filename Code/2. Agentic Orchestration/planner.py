"""
Planner node (§2.3). Decides whether this query needs live web data
(`web.search`, §3.3) in addition to the private catalog (`rag.search`,
§3.2, which is always used -- not part of this decision).

Real tool-calling, not a keyword rule: the LLM is given a `WebSearch` tool
via `.bind_tools()` and decides for itself whether to call it, based on the
query. Whether it calls the tool *is* the `use_web` decision -- Retriever
(§2.4) still does the actual MCP `web.search` call separately; this node
only decides whether to.

Replaces an earlier keyword-list version (checking for "current"/"now"/
"latest"/etc. as substrings) that worked but never touched an LLM's actual
tool-calling API -- the charter's LLM guidelines ask for that explicitly.
Real, new cost: this adds one LLM call per query where the Planner
previously cost $0.

System prompt: Code/6. Prompts & Documentation/planner_system_prompt.md
"""

import os

from pydantic import BaseModel, Field

from config import LLM_MODEL, LLM_PROVIDER, PROMPTS_DIR
from providers import get_chat_model, invoke_and_log
from state import GraphState


class WebSearch(BaseModel):
    """Call this if the query needs live/current price or availability
    information beyond what the private catalog can offer."""

    reason: str = Field(description="One short phrase: why live web data is needed here")


with open(os.path.join(PROMPTS_DIR, "planner_system_prompt.md")) as f:
    PLANNER_SYSTEM_PROMPT = f.read()

planner_llm = get_chat_model(LLM_PROVIDER, LLM_MODEL, temperature=0).bind_tools([WebSearch])


def decide_use_web(query: str) -> bool:
    """True iff the model actually chose to call WebSearch for this query."""
    result = invoke_and_log(planner_llm, "planner", PLANNER_SYSTEM_PROMPT, query)
    return len(result.tool_calls) > 0


def planner_node(state: GraphState) -> GraphState:
    state["plan"] = {"use_rag": True, "use_web": decide_use_web(state["query"])}
    return state
