"""
rag.search tool implementation (§3.2). `.py` module the §3.1 server imports
at request time -- not a notebook.

Wraps §2.4's retriever.py `search()` (itself ported from §1.4) rather than
re-deriving retrieval logic a third time. Retriever (§2.4) calls this tool
via MCP, not `search()` directly.

Output schema is exactly what search() returns -- doc_id, title, price,
price_per_unit, price_unit, brand, category_top, url, distance. `features`
isn't included: it was never stored as retrievable metadata (only used to
build the embedding text, §1.3), so the backlog's original draft schema
was never buildable as written.
"""

import os
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "2. Agentic Orchestration"))

from retriever import search  # noqa: E402  (path setup must run first)

# Mirrors retriever.py's SEARCH_FILTER_KEYS: category is deliberately not
# forwarded to search() -- category_top is constant across
# products_home_kitchen (§2.4 finding), so filtering by it there is
# structurally meaningless, not just unreliable.
_FORWARDED_FILTER_KEYS = ("budget_min", "budget_max", "brand")


def rag_search_impl(
    query: str,
    top_k: int = 5,
    budget_min: Optional[float] = None,
    budget_max: Optional[float] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
) -> dict:
    """Implementation behind the `rag.search` MCP tool. Returns
    {"products": [...], "warnings": [...]}. `category` is accepted but not
    applied (see module docstring); using it produces a warning, not a
    silent no-op."""
    warnings = []
    if category is not None:
        warnings.append(
            "category filter not applied: category_top is constant across "
            "products_home_kitchen (§2.4 finding), so it can't narrow results here"
        )

    kwargs = {k: v for k, v in {"budget_min": budget_min, "budget_max": budget_max, "brand": brand}.items() if v is not None}
    products = search(query, top_k=top_k, **kwargs)

    return {"products": products, "warnings": warnings}
