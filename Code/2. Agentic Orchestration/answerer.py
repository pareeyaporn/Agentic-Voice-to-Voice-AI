"""
Answerer/Critic node (§2.5). One structured-output LLM call synthesizes the
spoken recommendation + citations -- but grounding and the ~15s length budget
are enforced deterministically in Python afterward, not trusted to the
prompt alone. A prompt instruction is a request; a citation compared against
the actual list of retrieved doc_ids is a fact.

System prompt: Code/6. Prompts & Documentation/answerer_critic_system_prompt.md

No separate chemical-safety re-check here: Router (§2.2) already routes
unsafe requests to safe_refusal before Answerer ever runs -- by construction,
Answerer never sees a flagged-unsafe query.

Empty results skip the LLM call entirely: if tool_results.products is empty,
the correct answer is knowable in advance (say nothing was found), so this
returns a fixed fallback directly -- cheaper than a call, zero hallucination
risk on a case a rule already covers completely.
"""

import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config import LLM_MODEL, LLM_PROVIDER, PROMPTS_DIR
from providers import get_chat_model, invoke_and_log
from state import GraphState

ANSWER_WORD_BUDGET = 40
NO_RESULTS_FALLBACK = "I couldn't find a good match for that in the catalog."
UNGROUNDED_FALLBACK = "I found some options but couldn't confirm the details, so I don't want to guess."


class AnswererCitation(BaseModel):
    doc_id: str
    url: Optional[str] = None


class AnswererOutput(BaseModel):
    answer: str = Field(description="The spoken recommendation, ~40 words or fewer")
    citations: List[AnswererCitation] = Field(default_factory=list)


with open(os.path.join(PROMPTS_DIR, "answerer_critic_system_prompt.md")) as f:
    ANSWERER_SYSTEM_PROMPT = f.read()

answerer_llm = get_chat_model(LLM_PROVIDER, LLM_MODEL, temperature=0).with_structured_output(AnswererOutput)


def format_candidates(products: List[Dict[str, Any]], limit: int = 5) -> str:
    if not products:
        return "(no candidate products retrieved)"
    lines = []
    for p in products[:limit]:
        price = f"${p['price']:.2f}" if p.get("price") is not None else "price unknown"
        lines.append(f"- doc_id: {p['doc_id']} | title: {p['title']} | {price} | brand: {p.get('brand') or 'unknown'}")
    return "\n".join(lines)


def grounding_check(result: AnswererOutput, valid_doc_ids: set) -> AnswererOutput:
    """Deterministic, not LLM-judged: every cited doc_id must be one
    Retriever actually returned. Any miss discards the whole answer."""
    if any(c.doc_id not in valid_doc_ids for c in result.citations):
        return AnswererOutput(answer=UNGROUNDED_FALLBACK, citations=[])
    return result


def enforce_length(result: AnswererOutput) -> AnswererOutput:
    words = result.answer.split()
    if len(words) <= ANSWER_WORD_BUDGET:
        return result
    return AnswererOutput(answer=" ".join(words[:ANSWER_WORD_BUDGET]) + "...", citations=result.citations)


def answerer_node(state: GraphState) -> GraphState:
    products = state["tool_results"]["products"]

    if not products:
        state["final_answer"] = NO_RESULTS_FALLBACK
        state["citations"] = []
        return state

    candidate_text = format_candidates(products)
    human_message = f"Query: {state['query']}\nConstraints: {state['constraints']}\n\nCandidates:\n{candidate_text}"
    result: AnswererOutput = invoke_and_log(answerer_llm, "answerer", ANSWERER_SYSTEM_PROMPT, human_message)

    valid_doc_ids = {p["doc_id"] for p in products}
    result = grounding_check(result, valid_doc_ids)
    result = enforce_length(result)

    state["final_answer"] = result.answer
    state["citations"] = [c.model_dump(exclude_none=True) for c in result.citations]
    return state
