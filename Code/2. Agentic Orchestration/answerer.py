"""
Answerer/Critic node (§2.5). One structured-output LLM call synthesizes the
spoken recommendation + citations -- but grounding, raw-ID leaks, and the
~15s length budget are all enforced deterministically in Python afterward,
not trusted to the prompt alone. A prompt instruction is a request; a
citation compared against the actual list of retrieved doc_ids is a fact.

scrub_raw_ids() exists because the prompt alone genuinely wasn't reliable
enough: verified a real, reproducible case (~40% of runs on one low-context
query) where the model spoke a raw doc_id mid-sentence despite the prompt
saying not to -- caught by testing the actual behavior, not assumed fixed
just because the prompt asked nicely.

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
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config import LLM_MODEL, LLM_PROVIDER, PROMPTS_DIR
from providers import get_chat_model, invoke_and_log
from state import GraphState

ANSWER_WORD_BUDGET = 40
NO_RESULTS_FALLBACK = "I couldn't find a good match for that in the catalog."
UNGROUNDED_FALLBACK = "I found some options but couldn't confirm the details, so I don't want to guess."
RAW_ID_LEAK_FALLBACK = "I found a good match but had trouble summarizing it cleanly -- let me know if you'd like me to try again."

# doc_ids in this project are 32-char hex strings (md5-shaped, from products_clean.csv's
# `id` column, §1.3). 16+ hex chars is a generous floor -- real spoken content basically
# never produces a string that long and that shape by accident.
_RAW_ID_RE = re.compile(r"\b[0-9a-f]{16,}\b", re.IGNORECASE)


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


def scrub_raw_ids(result: AnswererOutput) -> AnswererOutput:
    """Deterministic backstop for the prompt's "never speak a doc_id" rule
    -- not trusted to the prompt alone, because it isn't reliable enough on
    its own: verified this actually happens (a doc_id spoken mid-sentence,
    e.g. "...cheapest option, doc_id 9f0435b9a121e69b6aaf04113a800992"),
    reproducibly, in ~40% of runs of one specific low-context query before
    this existed -- a real, measured failure rate, not a hypothetical one.
    Same "no partial credit" posture as grounding_check: any leak discards
    the whole answer rather than trying to surgically strip it out."""
    if _RAW_ID_RE.search(result.answer):
        return AnswererOutput(answer=RAW_ID_LEAK_FALLBACK, citations=[])
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
    result = scrub_raw_ids(result)
    result = enforce_length(result)

    state["final_answer"] = result.answer
    state["citations"] = [c.model_dump(exclude_none=True) for c in result.citations]
    return state
