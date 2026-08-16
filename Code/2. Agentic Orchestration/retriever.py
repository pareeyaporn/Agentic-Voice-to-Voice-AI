"""
Retriever node (§2.4). search() is ported from §1.4's hybrid retrieval
notebook (same reuse pattern §1.5 already used on §1.4: redefined, not
imported -- notebooks can't import each other). Kept here, still used by
Code/3. MCP Server & Tools/rag_search_tool.py -- retriever_node itself no
longer calls it directly (see below), but the MCP server does.

**The swap (§2.4's "call MCP tools only" item, closed):** retriever_node
now calls rag.search and web.search through the persistent MCP client
(mcp_client.py) instead of calling search() in-process. Real behavior, no
fabricated scenarios:
- rag.search always runs (plan.use_rag is always True)
- web.search only runs if plan.use_web -- both tools are real now (§3.2,
  §3.3), so this is a genuine conditional call, not a stubbed branch
- conflicts get reconciled for real when both tools returned results (see
  reconcile()) -- title-similarity matching (difflib, no new dependency),
  flags price disagreements rather than silently picking one source
- category is still accepted and forwarded (unlike the pre-swap version,
  which dropped it client-side) -- the server itself now returns an
  explicit warning when it can't apply it (§3.2), so the client doesn't
  need to duplicate that logic anymore
- material/quantity are dropped client-side -- the MCP tool's schema
  doesn't declare those parameters at all, so forwarding them would be a
  validation error, not a graceful no-op
- **Known gap, not solved here:** web products get `doc_id=None` (they
  only have a `url`, no private-catalog doc_id) -- Answerer's citation
  schema and prompt are doc_id-first, so a web result is unlikely to
  actually get cited even though it's present in tool_results.products.
  Reworking Answerer's citation model to handle both is a real follow-up,
  not attempted as part of this swap.
"""

import os
from difflib import SequenceMatcher

import chromadb
from sentence_transformers import SentenceTransformer

import mcp_client
from config import REPO_ROOT
from mcp_client import ToolCallError
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

MCP_ACCEPTED_RAG_FILTER_KEYS = ("budget_min", "budget_max", "category", "brand")
# material/quantity excluded -- the rag.search tool's schema doesn't declare
# them at all (see module docstring).

TITLE_SIMILARITY_THRESHOLD = 0.6
PRICE_CONFLICT_TOLERANCE = 0.01


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


def reconcile(rag_products: list[dict], web_products: list[dict]) -> list[dict]:
    """Matches rag.search vs web.search products by title similarity
    (difflib.SequenceMatcher, no new dependency -- stdlib is enough for
    this), flags price disagreements as conflicts rather than silently
    picking one source. Empty by construction if either list is empty --
    there's nothing to reconcile a single source against."""
    conflicts = []
    for rp in rag_products:
        best_match, best_score = None, 0.0
        for wp in web_products:
            score = SequenceMatcher(None, (rp.get("title") or "").lower(), (wp.get("title") or "").lower()).ratio()
            if score > best_score:
                best_match, best_score = wp, score
        if best_match is None or best_score < TITLE_SIMILARITY_THRESHOLD:
            continue
        rag_price, web_price = rp.get("price"), best_match.get("price")
        if rag_price is not None and web_price is not None and abs(rag_price - web_price) > PRICE_CONFLICT_TOLERANCE:
            conflicts.append({
                "rag_doc_id": rp.get("doc_id"),
                "title": rp.get("title"),
                "rag_price": rag_price,
                "web_price": web_price,
                "web_url": best_match.get("url"),
                "title_similarity": round(best_score, 3),
            })
    return conflicts


async def retriever_node(state: GraphState) -> GraphState:
    """Real (the swap): calls rag.search and (conditionally) web.search
    through the persistent MCP client -- not search() in-process anymore.
    async because MCP client calls are async; the graph is invoked via
    graph.ainvoke() now, not graph.invoke() (see graph.py / 2.7's notebook)."""
    products, errors = [], []

    constraints = state["constraints"]
    rag_args = {"query": state["query"], **{k: v for k, v in constraints.items() if k in MCP_ACCEPTED_RAG_FILTER_KEYS}}
    dropped = set(constraints) - set(rag_args)
    if dropped:
        errors.append({"tool": "rag.search", "error": f"unsupported filter(s) ignored: {sorted(dropped)}"})

    rag_products: list[dict] = []
    try:
        rag_result = await mcp_client.call_tool("rag.search", rag_args)
        rag_products = rag_result["products"]
        for p in rag_products:
            p["source"] = "rag"
        products.extend(rag_products)
        errors.extend({"tool": "rag.search", "error": w} for w in rag_result.get("warnings", []))
    except ToolCallError as e:
        errors.append({"tool": "rag.search", "error": f"[{e.error_type}] {e.message}"})

    web_products: list[dict] = []
    if state["plan"]["use_web"]:
        try:
            web_result = await mcp_client.call_tool("web.search", {"query": state["query"]})
            web_products = [
                {
                    "doc_id": None,  # known gap -- see module docstring
                    "title": r.get("title"),
                    "price": r.get("price"),
                    "brand": None,
                    "url": r.get("url"),
                    "snippet": r.get("snippet"),
                    "availability": r.get("availability"),
                    "source": "web",
                }
                for r in web_result["results"]
            ]
            products.extend(web_products)
        except ToolCallError as e:
            errors.append({"tool": "web.search", "error": f"[{e.error_type}] {e.message}"})

    conflicts = reconcile(rag_products, web_products)

    state["tool_results"] = {"products": products, "conflicts": conflicts, "errors": errors}
    return state
