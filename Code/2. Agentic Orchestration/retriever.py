"""
Retriever node (§2.4). search() is ported from §1.4's hybrid retrieval
notebook (same reuse pattern §1.5 already used on §1.4: redefined, not
imported -- notebooks can't import each other. Now that this lives in a real
.py module, a future cleanup could have §1.4 and this share one
implementation, but that's not done here -- out of scope for this port).

Real behavior, no fabricated scenarios:
- rag.search always runs (plan.use_rag is always True)
- web.search doesn't exist yet (§3.3 decided on Tavily, not built) -- when
  plan.use_web is True, this logs a genuine partial-tool-failure and
  continues with rag results only
- conflicts stays empty until §3.3 gives Retriever a second result set to
  reconcile against
- category is deliberately NOT a hard filter here: products_home_kitchen's
  category_top is uniformly "Home & Kitchen" (it's the field that carved out
  this slice in §1.1/§1.2), so filtering within the slice by it is
  structurally meaningless -- caught by a real assertion failure while
  building this node, not by inspection. material/quantity are also dropped
  (search() was never built to support them) -- all three get logged, not
  silently ignored
"""

import os

import chromadb
from sentence_transformers import SentenceTransformer

from config import REPO_ROOT
from state import GraphState

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
CHROMA_PERSIST_DIR_HK = os.path.join(
    REPO_ROOT,
    os.environ.get(
        "CHROMA_PERSIST_DIR_HOME_KITCHEN",
        "Code/1. Data Pipeline & Indexing/processed/chroma_db_home_kitchen",
    ),
)
CHROMA_COLLECTION_HK = os.environ.get("CHROMA_COLLECTION", "products_home_kitchen")

_model = SentenceTransformer(EMBEDDING_MODEL)
_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR_HK)
_collection = _client.get_collection(CHROMA_COLLECTION_HK)

SEARCH_FILTER_KEYS = ("budget_min", "budget_max", "brand")
# "category" deliberately excluded -- see module docstring.


def _unit_aware_tie_break(candidates, group_tolerance=0.15):
    """Groups candidates by price_unit; within a group, if the group's own
    distance spread is tight enough to be genuine substitutes, re-sorts just
    that group by price-per-unit (cheapest first)."""
    if not candidates:
        return candidates
    result = list(candidates)

    by_unit = {}
    for i, c in enumerate(result):
        if c["price_per_unit"] is not None and c["price_unit"] is not None:
            by_unit.setdefault(c["price_unit"], []).append(i)

    for unit, idxs in by_unit.items():
        if len(idxs) < 2:
            continue
        group = [result[i] for i in idxs]
        spread = max(c["distance"] for c in group) - min(c["distance"] for c in group)
        if spread <= group_tolerance:
            for i, c in zip(idxs, sorted(group, key=lambda c: c["price_per_unit"])):
                result[i] = c
    return result


def search(query, top_k=5, budget_min=None, budget_max=None, category=None, brand=None, overfetch=30):
    """Hybrid retrieval: vector similarity + metadata filters, with
    unit-aware tie-breaking. Returns a list of dicts, each carrying `doc_id`
    for citation. Single-collection version -- always products_home_kitchen."""
    where_clauses = []
    if budget_min is not None:
        where_clauses.append({"price": {"$gte": budget_min}})
    if budget_max is not None:
        where_clauses.append({"price": {"$lte": budget_max}})
    if category is not None:
        where_clauses.append({"category_top": category})
    where = None
    if len(where_clauses) == 1:
        where = where_clauses[0]
    elif len(where_clauses) > 1:
        where = {"$and": where_clauses}

    query_embedding = _model.encode([query])[0].tolist()
    n_results = overfetch if brand else top_k
    results = _collection.query(query_embeddings=[query_embedding], n_results=n_results, where=where)

    candidates = []
    for meta, dist, doc in zip(results["metadatas"][0], results["distances"][0], results["documents"][0]):
        if brand and brand.lower() not in meta.get("brand", "").lower():
            continue
        candidates.append({
            "doc_id": meta["id"],
            "title": meta.get("title", doc),
            "price": meta.get("price"),
            "price_per_unit": meta.get("price_per_unit"),
            "price_unit": meta.get("price_unit"),
            "brand": meta.get("brand"),
            "category_top": meta.get("category_top"),
            "url": meta.get("url"),
            "distance": dist,
        })

    candidates = _unit_aware_tie_break(candidates)
    return candidates[:top_k]


def retriever_node(state: GraphState) -> GraphState:
    products, conflicts, errors = [], [], []

    filters = {k: v for k, v in state["constraints"].items() if k in SEARCH_FILTER_KEYS}
    dropped = set(state["constraints"]) - set(filters)  # e.g. category/material/quantity
    if dropped:
        errors.append({"tool": "rag.search", "error": f"unsupported filter(s) ignored: {sorted(dropped)}"})

    try:
        rag_results = search(state["query"], **filters)
        for r in rag_results:
            r["source"] = "rag"
        products.extend(rag_results)
    except Exception as e:
        errors.append({"tool": "rag.search", "error": str(e)})

    if state["plan"]["use_web"]:
        errors.append({
            "tool": "web.search",
            "error": "not implemented yet (§3.3 decided on Tavily but not built) -- continuing with rag.search results only",
        })

    state["tool_results"] = {"products": products, "conflicts": conflicts, "errors": errors}
    return state
