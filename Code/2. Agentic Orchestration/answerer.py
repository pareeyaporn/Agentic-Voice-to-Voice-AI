"""
Answerer/Critic node (§2.5). One structured-output LLM call synthesizes the
spoken recommendation + citations -- but grounding, raw-ID leaks, the ~15s
length budget, and (see below) *which* identifier a citation actually is are
all resolved deterministically in Python afterward, not trusted to the
prompt alone. A prompt instruction is a request; a citation compared against
the actual list of retrieved products is a fact.

scrub_raw_ids() exists because the prompt alone genuinely wasn't reliable
enough: verified a real, reproducible case (~40% of runs on one low-context
query) where the model spoke a raw doc_id mid-sentence despite the prompt
saying not to -- caught by testing the actual behavior, not assumed fixed
just because the prompt asked nicely.

**Citations, rag vs. web:** the LLM only ever echoes back a `ref` (a
candidate's `doc_id` if it's a rag result, its `url` if it's a web result --
whichever `format_candidates()` showed it). It never has to *classify*
which kind it is. resolve_citations() does that by looking the ref up
against the real retrieved products and building the citation from
ground-truth data (source/doc_id/url/title) -- deliberately not trusting the
LLM to self-report `source` correctly, same reasoning as scrub_raw_ids():
don't ask the model to make a judgment call Python can just verify.

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

# A `ref` is either a doc_id (32-char hex, md5-shaped, from products_clean.csv's `id`
# column, §1.3) or a url (web citations, since the citation schema change). Both get
# checked -- a URL leak is exactly as bad as a doc_id leak now that either can be a ref.
# 16+ hex chars is a generous floor for the doc_id case -- real spoken content basically
# never produces a string that long and that shape by accident.
_RAW_ID_RE = re.compile(r"\b[0-9a-f]{16,}\b|https?://\S+|www\.\S+", re.IGNORECASE)


class AnswererCitation(BaseModel):
    ref: str = Field(description="The candidate's doc_id (rag) or url (web) -- copy it exactly as shown")


class AnswererOutput(BaseModel):
    answer: str = Field(description="The spoken recommendation, ~40 words or fewer")
    citations: List[AnswererCitation] = Field(default_factory=list)


with open(os.path.join(PROMPTS_DIR, "answerer_critic_system_prompt.md")) as f:
    ANSWERER_SYSTEM_PROMPT = f.read()

answerer_llm = get_chat_model(LLM_PROVIDER, LLM_MODEL, temperature=0).with_structured_output(AnswererOutput)


def _ref(p: Dict[str, Any]) -> Optional[str]:
    """A product's citable identifier: doc_id for rag results, url for web
    results (rag products have both; web products only ever have url)."""
    return p.get("doc_id") or p.get("url")


def format_candidates(products: List[Dict[str, Any]], limit: int = 5) -> str:
    if not products:
        return "(no candidate products retrieved)"
    lines = []
    for p in products[:limit]:
        price = f"${p['price']:.2f}" if p.get("price") is not None else "price unknown"
        source = p.get("source", "rag")
        lines.append(
            f"- ref: {_ref(p)} | source: {source} | title: {p['title']} | {price} | brand: {p.get('brand') or 'unknown'}"
        )
    return "\n".join(lines)


def grounding_check(result: AnswererOutput, products: List[Dict[str, Any]]) -> AnswererOutput:
    """Deterministic, not LLM-judged: every cited ref must be one Retriever
    actually returned (checked against real product refs, rag or web --
    the LLM doesn't have to classify which kind, see module docstring). Any
    miss discards the whole answer."""
    valid_refs = {_ref(p) for p in products if _ref(p)}
    if any(c.ref not in valid_refs for c in result.citations):
        return AnswererOutput(answer=UNGROUNDED_FALLBACK, citations=[])
    return result


def resolve_citations(citations: List[AnswererCitation], products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Builds the real citation objects GraphState.citations actually holds
    -- source/doc_id/url/title -- from ground-truth product data, looked up
    by ref. Only ever called after grounding_check has passed, so every ref
    here is guaranteed to match a real product. This is what makes "private
    doc_ids and live URLs, clearly distinguished" (§5.2) possible -- source
    is derived by lookup, never trusted from the LLM's own output."""
    by_ref = {_ref(p): p for p in products if _ref(p)}
    resolved = []
    for c in citations:
        p = by_ref[c.ref]
        resolved.append({
            "source": p.get("source", "rag"),
            "doc_id": p.get("doc_id"),
            "url": p.get("url"),
            "title": p.get("title"),
        })
    return resolved


def scrub_raw_ids(result: AnswererOutput) -> AnswererOutput:
    """Deterministic backstop for the prompt's "never speak a ref" rule --
    not trusted to the prompt alone, because it isn't reliable enough on its
    own: verified this actually happens (a doc_id spoken mid-sentence, e.g.
    "...cheapest option, doc_id 9f0435b9a121e69b6aaf04113a800992"),
    reproducibly, in ~40% of runs of one specific low-context query before
    this existed -- a real, measured failure rate, not a hypothetical one.
    Also catches a leaked url now, since a `ref` can be either. Same "no
    partial credit" posture as grounding_check: any leak discards the whole
    answer rather than trying to surgically strip it out."""
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

    result = grounding_check(result, products)
    result = scrub_raw_ids(result)
    result = enforce_length(result)

    state["final_answer"] = result.answer
    state["citations"] = resolve_citations(result.citations, products)
    return state
