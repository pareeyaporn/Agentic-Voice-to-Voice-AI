"""
Answerer/Critic node (§2.5). One structured-output LLM call (method=
"function_calling", OpenAI's tool-calling API -- see router.py's docstring
for why) synthesizes the spoken recommendation + citations; grounding,
raw-ID leaks, and the length budget are then enforced deterministically in
Python, not trusted to the prompt alone -- `scrub_raw_ids()` exists because
a real test found the model spoke a raw doc_id mid-sentence in ~40% of runs
on one low-context query despite the prompt saying not to.

The LLM only ever echoes back a `ref` (a candidate's `doc_id` for rag, `url`
for web) without needing to classify which kind it is; `resolve_citations()`
looks the ref up against the real retrieved products to build the citation
from ground truth, rather than trusting the model's own source claim.

System prompt: Code/6. Prompts & Documentation/answerer_critic_system_prompt.md

Router (§2.2) already routes unsafe requests to `safe_refusal`, so no
separate safety re-check happens here. Empty results skip the LLM call
entirely and return a fixed fallback.
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

# A `ref` is either a doc_id (32-char hex, §1.3) or a url. 16+ hex chars is a
# generous floor -- real spoken content essentially never matches by accident.
_RAW_ID_RE = re.compile(r"\b[0-9a-f]{16,}\b|https?://\S+|www\.\S+", re.IGNORECASE)


class AnswererCitation(BaseModel):
    ref: str = Field(description="The candidate's doc_id (rag) or url (web) -- copy it exactly as shown")


class AnswererOutput(BaseModel):
    answer: str = Field(description="The spoken recommendation, ~40 words or fewer")
    citations: List[AnswererCitation] = Field(default_factory=list)


with open(os.path.join(PROMPTS_DIR, "answerer_critic_system_prompt.md")) as f:
    ANSWERER_SYSTEM_PROMPT = f.read()

answerer_llm = get_chat_model(LLM_PROVIDER, LLM_MODEL, temperature=0).with_structured_output(
    AnswererOutput, method="function_calling"
)


def _ref(p: Dict[str, Any]) -> Optional[str]:
    """A product's citable identifier: doc_id for rag results, url for web
    results (rag products have both; web products only ever have url)."""
    return p.get("doc_id") or p.get("url")


def format_candidates(products: List[Dict[str, Any]], rag_limit: int = 5, web_limit: int = 3) -> str:
    """Takes each source's own top slice rather than truncating the combined
    list -- products is [rag..., web...] and rag always fills all 5 slots on
    its own, so a plain products[:limit] silently hid every web candidate
    from the LLM. web_limit=3, not 5: Tavily's weakest results tail into
    generic listing pages rather than specific products."""
    if not products:
        return "(no candidate products retrieved)"
    rag = [p for p in products if p.get("source", "rag") == "rag"][:rag_limit]
    web = [p for p in products if p.get("source") == "web"][:web_limit]
    lines = []
    for p in rag + web:
        price = f"${p['price']:.2f}" if p.get("price") is not None else "price unknown"
        source = p.get("source", "rag")
        lines.append(
            f"- ref: {_ref(p)} | source: {source} | title: {p['title']} | {price} | brand: {p.get('brand') or 'unknown'}"
        )
    return "\n".join(lines)


def grounding_check(result: AnswererOutput, products: List[Dict[str, Any]]) -> AnswererOutput:
    """Deterministic, not LLM-judged: every cited ref must be one Retriever
    actually returned. Any miss discards the whole answer."""
    valid_refs = {_ref(p) for p in products if _ref(p)}
    if any(c.ref not in valid_refs for c in result.citations):
        return AnswererOutput(answer=UNGROUNDED_FALLBACK, citations=[])
    return result


def resolve_citations(citations: List[AnswererCitation], products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Builds {source, doc_id, url, title} from ground-truth product data,
    looked up by ref -- only called after grounding_check, so every ref is
    guaranteed to match. Source is derived by lookup, not the LLM's claim."""
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
    the prompt alone wasn't reliable enough (a doc_id was spoken mid-sentence
    in ~40% of runs on one low-context query before this existed). Catches a
    leaked url too, since a ref can be either; any leak discards the answer."""
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
