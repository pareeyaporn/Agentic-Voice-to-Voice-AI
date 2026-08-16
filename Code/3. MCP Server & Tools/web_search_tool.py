"""
web.search tool implementation (§3.3). `.py` module the §3.1 server imports
at request time (file-format convention reason (c)) -- not a notebook.

Provider: Tavily (decided in §3.3's original entry) via the official
`tavily-python` client, not raw HTTP -- avoids hand-rolling auth/request
shape/error handling Tavily's own SDK already provides.

Output schema per the assignment brief: {title, url, snippet, price?,
availability?}. Tavily's raw response gives title/url/content (mapped to
snippet) directly, but no structured price/availability fields -- those are
extracted from the snippet text with a lightweight regex/keyword heuristic,
same honesty posture as §1.2's brand extraction: real, best-effort, openly
low-confidence, not fabricated. Verified against a real snippet that
literally contained "$35 ... Sold out" (see the §3.3 test notebook).

Robots.txt/ToS: handled server-side by Tavily's own crawling infrastructure
(the reason Tavily was picked over raw scraping, per §3.3's original
decision) -- not re-implemented here. Domain allowlist is real and ours:
passed to Tavily as `include_domains`, restricting results to known
legitimate retail/marketplace domains rather than the open web.

Caching (TTL) and rate-limit backoff are both real, both unit-tested with
mocked responses (not against the live API -- deterministic, and doesn't
spend real Tavily credits to prove retry/backoff timing).
"""

import os
import re
import sys
import time
from typing import Optional

from tavily import TavilyClient
from tavily.errors import TimeoutError as TavilyTimeoutError
from tavily.errors import UsageLimitExceededError

from tool_logging import ToolError

# Same config/.env loading rag_search_tool.py uses -- real bug caught while
# testing this module standalone: without this, TAVILY_API_KEY was only ever
# in os.environ as a side effect of some *other* module happening to import
# config.py first. Load it explicitly here so this module is correct on its
# own, not dependent on import order elsewhere.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "2. Agentic Orchestration"))
import config  # noqa: F401,E402  (imported for its side effect: loading .env)

_client: Optional[TavilyClient] = None


def _get_client() -> TavilyClient:
    """Lazy singleton -- avoids constructing a client (and requiring
    TAVILY_API_KEY) at import time, matching how the MCP server should be
    importable even before every provider key is configured."""
    global _client
    if _client is None:
        _client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    return _client


ALLOWED_DOMAINS = [
    "amazon.com", "walmart.com", "target.com", "ebay.com", "bestbuy.com",
]

CACHE_TTL_SECONDS = 120  # middle of the brief's stated 60-300s range
_cache: dict[tuple, tuple[float, dict]] = {}

MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 0.5

_PRICE_RE = re.compile(r"\$\s?(\d{1,4}(?:\.\d{2})?)")
_OUT_OF_STOCK_WORDS = ("out of stock", "sold out", "unavailable", "no longer available")
_IN_STOCK_WORDS = ("in stock", "available now", "ships today")


def _extract_price(snippet: str) -> Optional[float]:
    """Best-effort, real regex extraction -- first "$X.XX" found in the
    snippet text. Low-confidence (could pick up an unrelated dollar amount
    in the text), same honesty posture as §1.2's brand regex."""
    m = _PRICE_RE.search(snippet or "")
    return float(m.group(1)) if m else None


def _extract_availability(snippet: str) -> Optional[str]:
    """Best-effort keyword heuristic, not a structured field Tavily provides."""
    s = (snippet or "").lower()
    if any(w in s for w in _OUT_OF_STOCK_WORDS):
        return "out_of_stock"
    if any(w in s for w in _IN_STOCK_WORDS):
        return "in_stock"
    return None


def _call_with_backoff(query: str, max_results: int) -> dict:
    """Retries on transient errors only (timeout, usage-limit) -- not on
    client errors like a bad API key or malformed request, where retrying
    can't help. Raises a typed ToolError after exhausting retries, not the
    raw Tavily exception -- §3.4's error contract, so a caller (once the
    Retriever calls this via MCP, §2.4's open swap) can branch on
    `error_type` rather than parse free text."""
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return _get_client().search(query, max_results=max_results, include_domains=ALLOWED_DOMAINS)
        except TavilyTimeoutError as e:
            last_error = ToolError("timeout", str(e))
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_BASE_SECONDS * (2**attempt))
        except UsageLimitExceededError as e:
            last_error = ToolError("rate_limited", str(e))
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_BASE_SECONDS * (2**attempt))
    raise last_error


def web_search_impl(query: str, top_k: int = 5) -> dict:
    """Real implementation behind the `web.search` MCP tool. Returns
    {"results": [{title, url, snippet, price, availability}], "cache_hit": bool}."""
    cache_key = (query, top_k)
    cached = _cache.get(cache_key)
    if cached is not None:
        cached_at, cached_result = cached
        if time.time() - cached_at < CACHE_TTL_SECONDS:
            return {**cached_result, "cache_hit": True}

    raw = _call_with_backoff(query, top_k)
    results = [
        {
            "title": r.get("title"),
            "url": r.get("url"),
            "snippet": r.get("content"),
            "price": _extract_price(r.get("content", "")),
            "availability": _extract_availability(r.get("content", "")),
        }
        for r in raw.get("results", [])
    ]
    result = {"results": results}
    _cache[cache_key] = (time.time(), result)
    return {**result, "cache_hit": False}
