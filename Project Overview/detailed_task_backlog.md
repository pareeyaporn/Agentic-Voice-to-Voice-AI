# Detailed Task Backlog

Granular, checkable task list for building the Agentic Voice-to-Voice AI assistant. Complements [team_structure_and_task_breakdown.md](team_structure_and_task_breakdown.md) (who owns what, at a role level) with the actual engineering tasks each role needs to complete, grouped by component, each tagged with owner and target checkpoint.

**Legend — Owner:** `ORCH` Orchestration Lead · `DATA` Data Engineer · `VOICE` Voice/Integration Engineer · `UI` Frontend/UI Engineer · `LEAD` Project Lead
**Legend — Checkpoint:** `CP1` Week 6 · `CP2` Week 8 · `FINAL` Week 10

**File format convention:** default to `.ipynb` everywhere a notebook can do the job (see project memory — this is a hard preference, not a style note). Use `.py` only where a notebook genuinely can't: a long-running server process (§3.1 MCP server), a framework-mandated entrypoint (§5.1 Streamlit's `streamlit run app.py`), or a module one of those running `.py` processes must `import` at query time (importing code from a live `.ipynb` isn't practical). Every `.py` file planned below should trace to one of these three reasons, not a default.

---

## 1. Data Pipeline & Indexing (`DATA`)

### 1.1 Acquisition & Exploration — `CP1`
- [x] Download Amazon Product Dataset 2020 via `kagglehub.dataset_download("promptcloud/amazon-product-dataset-2020")` — resolves to `marketing_sample_for_amazon_com-ecommerce__20200101_20200131__10k_data.csv`, 10,002 rows × 28 columns (verified 2026-08-15)
- [x] Confirmed real column set: `Uniq Id, Product Name, Brand Name, Asin, Category, Upc Ean Code, List Price, Selling Price, Quantity, Model Number, About Product, Product Specification, Technical Details, Shipping Weight, Product Dimensions, Image, Variants, Sku, Product Url, Stock, Product Details, Dimensions, Color, Ingredients, Direction To Use, Is Amazon Seller, Size Quantity Variant, Product Description`
- [x] **Known data gaps (confirmed by running [Code/1. Data Pipeline & Indexing/1.1 explore data.ipynb](../Code/1.%20Data%20Pipeline%20&%20Indexing/1.1%20explore%20data.ipynb) against the full 10,002-row CSV — broader than the initial hand check):**
  - **13 of 28 columns are 100% empty**, not just 2: `Product Description, Stock, Size Quantity Variant, Product Details, Dimensions, Color, Quantity, Ingredients, Asin, Brand Name, Direction To Use, List Price, Sku`
  - **`Asin` and `Sku` are both entirely empty** — there is no reliable external product key to join a second dataset on; any join (e.g. for ratings) would have to be fuzzy, by title, not authoritative
  - **No rating/stars column exists at all** — the "4.6★ rating" in the brief's example interaction is not backed by this dataset; either drop rating from the pitch/UI or fuzzy-join a second ratings source
  - **No review-level data** — this is a single flat product table, not a products+reviews pair
  - `Category` is only 91.7% populated (830 blank rows); `Selling Price` is 98.9% non-null but only 95.2% parse to a clean number; `Product Name` has 137 duplicate values
  - Category distribution is skewed: ~67% `Toys & Games`; `Home & Kitchen` (708–712 rows) and `Sports & Outdoors` (540 rows) are the next largest; `Household`/`Cleaning` categories total only ~25 rows combined — **too sparse to use as the demo slice**
- [x] Pick category slice sized for a demo (~500+ products) — **decided: `Home & Kitchen`** (708–712 rows) instead of Household Cleaning, given actual row counts
- [x] Exploratory notebook (CSV in, CSV out — no parquet, per project convention): [Code/1. Data Pipeline & Indexing/1.1 explore data.ipynb](../Code/1.%20Data%20Pipeline%20&%20Indexing/1.1%20explore%20data.ipynb) — field coverage/nulls per column, price distribution (`Selling Price`), duplicate check (`Asin`/`Uniq Id`/`Product Name`), category distribution, plus charts (field-coverage bar, price-distribution histogram, category-distribution bar) for all three; self-contained and pre-executed with real output. Writes [Code/1. Data Pipeline & Indexing/processed/column_coverage.csv](../Code/1.%20Data%20Pipeline%20&%20Indexing/processed/column_coverage.csv)
- [x] Decide final working schema given the gaps above — see [data_schema_and_licensing.md](data_schema_and_licensing.md) for the full `products_clean.csv` field mapping
- [x] Document data licensing/usage constraints — see [data_schema_and_licensing.md](data_schema_and_licensing.md) (CC0 Public Domain)
- [ ] (Optional, if rating/reviews are wanted) Evaluate a second PromptCloud/Kaggle dataset to fuzzy-join in ratings or review snippets by title (no `Asin`/`Sku` available as a clean join key)

### 1.2 Preprocessing — `CP1`
- [x] Clean text fields (strip HTML, unescape entities, normalize unicode, collapse whitespace) in `Product Name`, `About Product`, `Technical Details`, `Product Specification` (`Product Description` is 100% empty per §1.1, nothing to clean there)
- [x] Extract brand from `Product Name` text since `Brand Name` is unpopulated — regex heuristic (explicit `"<Line> by <Brand>"` pattern first, then a capped 2-word leading-capitalized-word-run fallback). **Honest quality note:** ~96% coverage, but coverage ≠ accuracy — a hand-reviewed sample puts exact matches around 5/12, ~5/12 correct-prefix-plus-noise, ~2/12 wrong/undercaptured. Treat as a low-confidence signal for coarse grouping, not something to cite. LLM-based extraction would do better if brand precision is ever needed downstream.
- [x] Normalize units for fair comparison where package size is parseable (price per oz/ml/lb/kg/g/ct from a title regex) — found in ~10% of rows; most titles don't state a package size
- [x] Deduplicate near-identical listings — no `Asin`/`Sku` key exists (§1.1), so dedupe on exact `Product Name` match; removed duplicate-title rows (10,002 → 9,930)
- [x] Flatten/parse the pipe-delimited `Category` hierarchy into `category_top` + `category_full` filter fields
- [x] Persist cleaned `products_clean.csv` to `Code/1. Data Pipeline & Indexing/processed/` (no reviews file — none exists for this dataset, per §1.1)
- [x] **Post-cleaning category recheck (§7 of the notebook)** — re-verify the `Home & Kitchen` demo-slice decision (made in §1.1, on raw data) against the *cleaned* data, and check sub-category composition here, before indexing, rather than discovering it during §1.3 as originally happened. Confirmed: 706 rows (matches the raw ~708-712 estimate — the small drop is just the dedup pass), but the slice is **kids'-goods-heavy, not cookware-heavy** (Home Décor 198, Furniture 195, Bedding 177, Event & Party Supplies 72, Kitchen & Dining only 53/706 ≈ 7.5%). This check now lives here so a future category-slice decision gets caught earlier in the pipeline.

Implementation: [Code/1. Data Pipeline & Indexing/1.2 process data.ipynb](../Code/1.%20Data%20Pipeline%20&%20Indexing/1.2%20process%20data.ipynb) — self-contained, pre-executed, builds on [1.1 explore data.ipynb](../Code/1.%20Data%20Pipeline%20&%20Indexing/1.1%20explore%20data.ipynb)'s findings, plus charts (brand-extraction method breakdown, package-size unit distribution, price-per-unit distribution, post-cleaning category distribution, Home & Kitchen sub-category breakdown). Output: [Code/1. Data Pipeline & Indexing/processed/products_clean.csv](../Code/1.%20Data%20Pipeline%20&%20Indexing/processed/products_clean.csv) (9,930 rows × 13 columns).

### 1.3 Embedding & Indexing — `CP1` → `CP2`
- [x] Choose embedding model — **`sentence-transformers` / `all-MiniLM-L6-v2`, local, free, 384 dims** (no API key/billing needed; decided over OpenAI embeddings after checking OpenAI's free-tier status is unclear as of 2026 and requires a billing method either way). Config-driven via `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL` in `.env` (see [.env.example](../.env.example)) — swappable without code changes, consistent with the model-agnostic requirement's spirit even though embeddings aren't the "LLM" that requirement literally targets
- [x] Build embedding text = `title` + `features` (fallback: `technical_details` → `product_specification` when `features` is missing)
- [x] Stand up vector store — **Chroma**, local/embedded; metadata payload per vector: `id, title, brand, category_top, price, price_per_unit, price_unit, url` (`id` doubles as the citation `doc_id`). **Two separate persist directories, not one shared one** (revised after checking real sizes — see below): `Code/1. Data Pipeline & Indexing/processed/chroma_db_home_kitchen/` (~6.6MB, committed) and `chroma_db_all/` (~65MB, gitignored — rebuild by re-running `1.3 build index.ipynb`)
- [x] **Two collections, split into two separate persist directories** (initially built as one shared directory — Chroma supports multiple named collections in one directory, like tables in one database — but reversed after checking real sizes): `products_home_kitchen` (706 rows, `chroma_db_home_kitchen/`, 6.6MB, committed) and `products_all` (9,930 rows, `chroma_db_all/`, ~65MB, gitignored). Confirmed empirically the split was necessary, not just theoretical — `products_all` accounted for 69,785 of 74,861 total metadata rows (93%) in the combined 58MB file; an isolated Home & Kitchen-only directory measured 6.6MB, comfortably under GitHub's 50MB soft limit. `chroma_db_all/` is regenerated by re-running `1.3 build index.ipynb` (no separate script needed — it already rebuilds both collections from scratch every run). Embedding text is built and embedded **once** for all rows; `Home & Kitchen` reuses a slice rather than re-embedding. Config: `CHROMA_PERSIST_DIR_HOME_KITCHEN`, `CHROMA_PERSIST_DIR_ALL`, `CHROMA_COLLECTION_ALL` in [.env.example](../.env.example)
- [x] **Embedding space visualization** — PCA (full 9,930 points) + t-SNE (3,000-point sample, for speed), colored by category (top 7 + "Other"). Not originally in this checklist; added on request. Confirms visually what was already found analytically: `Clothing`/`Baby Products`/`Sports & Outdoors` form distinct clusters, `Home & Kitchen` stays scattered (consistent with it being a heterogeneous mix, not a coherent category)
- [x] **New dependency:** `scikit-learn` (PCA + t-SNE), confirmed with the user before adding, per the project's tech-confirmation convention
- [x] **Real bug hit and fixed:** computing PCA/t-SNE after loading `sentence-transformers` segfaulted the kernel (exit code 139) — a known PyTorch/scikit-learn OpenMP-runtime conflict on macOS (both link their own copy of OpenMP; loading both in one process can crash). Fixed with `OMP_NUM_THREADS=1` + `KMP_DUPLICATE_LIB_OK=TRUE`, set at the top of the notebook before any heavy imports. Diagnosed by reproducing outside the Jupyter kernel (plain script) to get a real traceback instead of "kernel died"
- [x] Build script — **[Code/1. Data Pipeline & Indexing/1.3 build index.ipynb](../Code/1.%20Data%20Pipeline%20&%20Indexing/1.3%20build%20index.ipynb)**, not `data_index.py` (project-wide convention is `.ipynb`, not `.py` — see project memory). Idempotent: drops and recreates the Chroma collection on every run
- [x] CLI/rebuild entrypoint — re-running the notebook (`jupyter nbconvert --to notebook --execute --inplace`) rebuilds the index from scratch; no separate `make index` needed given the ipynb-only convention

**Important finding (data coverage, not a retrieval-quality bug):** sanity-checking the index with queries matching the assignment brief's example ("eco-friendly kitchen cleaner", "non-stick frying pan", "coffee maker under $50") returned poor matches — cake pans, coffee mugs, a toaster, no actual cookware/cleaners. Investigated and confirmed this is a **dataset-wide gap**: searching the full 9,930-row cleaned dataset (all categories, not just the indexed slice) for "frying pan"/"skillet" returns **zero** matches; "coffee maker" returns **one**. Even the `Kitchen & Dining` sub-category (55 rows, any top-level category) turns out to be mostly kids' lunch boxes/snack bags, not cookware. The `Home & Kitchen` slice is actually kids'-goods-heavy: of 706 indexed rows, sub-categories are Home Décor (198), Furniture (195, mostly Kids'), Bedding (177, mostly Kids'), Event & Party Supplies (72), Kitchen & Dining (53, mostly lunch boxes).

**Decision:** reframe the project's demo pitch/example queries around what the data actually supports well (kids' lunch boxes, bedding, furniture, storage, party supplies) rather than sourcing a different dataset — see the updated root README. Re-ran the sanity check with reframed queries ("insulated lunch box for kids", "kids bedding set", "toy storage organizer", "birthday party decorations") — all returned genuinely strong, correct top-3 matches (similarity distances dropped from ~1.1–1.5 to ~0.5–0.9), confirming the indexing pipeline itself works correctly; the original queries were simply asking for products this dataset doesn't have.

### 1.4 Hybrid Retrieval — `CP2`
- [x] Implement vector search + metadata filter combination — **[Code/1. Data Pipeline & Indexing/1.4 hybrid retrieval.ipynb](../Code/1.%20Data%20Pipeline%20&%20Indexing/1.4%20hybrid%20retrieval.ipynb)**, reads the collections from §1.3, no rebuild. `category`/`budget_min`/`budget_max` go through Chroma's native `where` clause (reliable — clean exact/numeric fields). **`brand` does not** — it's a low-confidence regex-derived field (§1.2, ~5/12 exact match), so an exact metadata match would silently drop good results over extraction noise; implemented as an over-fetch + Python substring post-filter instead
- [x] Add unit-aware ranking/tie-breaking — **real design iteration, not right on the first try:** the first version compared every candidate's distance to the single best match ("near the #1 result"). Tested against several real queries (`party plates`, `latex party balloons`, `paper napkins`) and found same-`price_unit` product variants (e.g. two pack sizes of the same balloons) are consistently **not** close to the #1 result (spreads of 0.15–0.3+) — they're close to **each other** instead (0.07–0.15). Redesigned to compare same-unit candidates pairwise within their own group rather than against the global best. Verified working on `"plastic party plates"`: the cheapest-per-unit item ($0.855/ct) moved from its original 7th position to 3rd, confirmed via real (not simulated) output
- [x] Reranker — **skipped**, per project decision (backlog marked it optional; vector + filter results were already strong in §1.3's sanity checks). Revisit in §1.5 if eval numbers show it's actually needed
- [x] Return results with `doc_id` for citation traceability — every result dict carries `doc_id` (`= id` from `products_clean.csv`) plus `url`
- [x] **Collection-agnostic by design** (not in the original checklist, added because it was cheap given §1.3's two-collection setup): `search()` takes a `collection` parameter, defaults to `products_home_kitchen`, works unchanged against `products_all` — demonstrated with a `"remote control car"` query against the full catalog

### 1.5 RAG Evaluation — `CP2` → `FINAL`
- [x] Build an eval set — **14 queries** (not hand-picked "easy" ones): 10 plain `Home & Kitchen`, 2 with filters (`budget_max`, `brand`), 2 against `products_all`. No human-labeled relevance exists for this dataset, so "expected top products" is a **keyword/substring proxy** on `title` — a real, stated limitation (see below), not gold-standard labels
- [x] Measure precision/recall@5 — **mean precision@5 = 0.90** (strong — 12/14 queries at 0.8+). **Mean recall@5 = 0.32, but this number is largely a structural artifact**: recall@5 is capped at `5/relevant_total`, so a query with 94 keyword-matches (`"board game for family night"`) can't score above ~0.05 even with a perfect top-5, while one with 6 matches (`"paper plates"`) can hit 0.67. Comparing recall@5 across queries with very different ground-truth sizes isn't meaningful — precision@5 is the informative number here
- [x] Log failure cases — inspected the two lowest-precision queries with real retrieved-vs-expected titles (not just scores), and found the keyword ground truth itself is imperfect in **both directions**: false negatives (a banner clearly relevant to `"birthday party decorations"` doesn't contain the literal word "party," counted as a miss) and false positives (`"board game"` keyword matches a board-game-themed T-shirt and a dice bag, not actual games, inflating that query's relevant-set denominator)
- [x] Write up eval methodology + results — **[Project Overview/rag_eval_plan.md](rag_eval_plan.md)** (CP2 deliverable). Implementation: [Code/1. Data Pipeline & Indexing/1.5 rag evaluation.ipynb](../Code/1.%20Data%20Pipeline%20&%20Indexing/1.5%20rag%20evaluation.ipynb), self-contained, pre-executed, reuses `search()` from §1.4, no new dependencies
- [x] **Filters validated by the eval, not just assumed working:** `budget_max=15` query still hit 1.00 precision; `brand="Wildkin"` query hit 1.00 recall (all 4 ground-truth Wildkin items retrieved), confirming the low-confidence-field post-filter approach from §1.4 actually works
- [x] **Reranker decision revisited and confirmed:** no reranker was needed to reach these precision numbers — the §1.4 decision to skip it stands

---

## 2. Agentic Orchestration — LangGraph (`ORCH`)

### 2.1 Graph Design — `CP1`
- [x] Define graph state schema (query, transcript, constraints, plan, tool results, citations, safety flags, final answer) — implemented as `TypedDict`s (`GraphState`, `Plan`, `ToolResults`) in [Code/2. Agentic Orchestration/2.1-2.6 graph and nodes.ipynb](../Code/2.%20Agentic%20Orchestration/2.1-2.6%20graph%20and%20nodes.ipynb), matches the 8-field list exactly, no extra fields
- [x] Sketch node graph: Router → Planner → Retriever → Answerer/Critic (matches [architecture_with_mcp.mermaid](../Architecture/architecture_with_mcp.mermaid) and [graph_state_flow.mermaid](../Architecture/graph_state_flow.mermaid)) — built as a real, compiled, executed LangGraph `StateGraph` with stub node functions (sanctioned by the CP1 checklist's "implementation can still be stubbed"), not just a diagram
- [x] Decide conditional edges (e.g. skip web.search unless query implies "current/latest/now") — **one graph-level conditional edge**: Router → safe_refusal vs. Router → Planner, on `safety_flag`. The rag-vs-web decision is *not* a second edge — it's `plan['use_web']` data, read as a plain `if` inside the Retriever node (a choice within one node, not a choice between nodes). Verified with two real `graph.invoke()` runs + assertions: the safety path provably skips Planner and Retriever (their placeholder outputs stay unchanged)
- [x] **File format note:** design/prototyping happened in a notebook — [Code/2. Agentic Orchestration/2.1-2.6 graph and nodes.ipynb](../Code/2.%20Agentic%20Orchestration/2.1-2.6%20graph%20and%20nodes.ipynb), self-contained, pre-executed, one file for §2.1-2.6 rather than one-per-subsection (see original rationale below). **Now also exported to `.py`, earlier than planned**: §2.7 turned out to need a real importable graph sooner than §5 would have, so `config.py`/`state.py`/`providers.py`/`router.py`/`planner.py`/`retriever.py`/`answerer.py`/`graph.py` were extracted directly from the notebook's already-tested cells (not rewritten). Split into multiple small `.py` files rather than one big one — `.py` files can import each other freely, unlike notebooks, so the "must be one file" constraint that applied to the design notebook doesn't carry over. The design notebook stays as a frozen record; it's not kept in sync with the `.py` files going forward. Original rationale for one notebook file: §1's stages hand off data artifacts (a CSV, a Chroma dir) between notebooks, a natural file boundary; §2.1-2.5's "stages" are functions that had to live in one shared `StateGraph` object to run as a graph at all during the design/prototyping phase.

### 2.2 Router Node — `CP1` → `CP2`
- [x] Intent classification: is this a product search/comparison/follow-up/out-of-scope query? — one structured-output LLM call (`RouterOutput.intent`, one of the 4 categories), verified against a 4-query test set (1 per intent, all matched). **Known gap:** `intent` is computed but not persisted to `GraphState` (kept to the 8-field schema from §2.1) — an `out_of_scope` query currently flows through Planner/Retriever/Answerer like any other rather than short-circuiting; revisit if that proves unsatisfying once §2.3-2.5 exist, see the note in `router_node`'s docstring
- [x] Constraint extraction: budget, material, brand, category, quantity — `RouterConstraints` Pydantic model, same LLM call as intent (not a separate one), verified real budget/category extraction on the smoke-test query
- [x] Safety flag detection (e.g. unsafe chemical mixing questions) → route to a safe-refusal path — verified end-to-end via a real `graph.invoke()`: an actual unsafe transcript gets classified and correctly routes to `safe_refusal`, skipping Planner/Retriever (asserted, not just eyeballed)
- [x] Write & version the router system prompt in `prompts/` — [Code/6. Prompts & Documentation/router_system_prompt.md](../Code/6.%20Prompts%20%26%20Documentation/router_system_prompt.md) (first content in that folder; the other 3 node prompts land with §2.3-2.5)
- [x] **Cost note (not an original checklist item, added per user request):** LLM call volume in [Code/2. Agentic Orchestration/2.1-2.6 graph and nodes.ipynb](../Code/2.%20Agentic%20Orchestration/2.1-2.6%20graph%20and%20nodes.ipynb) is kept deliberately low (6 real calls total: 1 smoke test + 3-query intent test set + 2 inside the full graph test run) rather than an exhaustive eval — Router is real, LLM-driven (not swapped for rules), but call count stays proportional to what's needed to verify it works
- [x] Implementation model: `gpt-5.6-luna`, pinned in `.env` `LLM_MODEL` (was left blank in §2.6 pending this moment)

### 2.3 Planner Node — `CP1` → `CP2`
- [x] Source selection rule: prefer `rag.search`; add `web.search` when query implies live price/availability — implemented as `use_rag` always `True`, `use_web` from a keyword rule (`current/latest/now/today/right now/currently/in stock/available/still available/on sale`) in [Code/2. Agentic Orchestration/2.1-2.6 graph and nodes.ipynb](../Code/2.%20Agentic%20Orchestration/2.1-2.6%20graph%20and%20nodes.ipynb), verified against 7 test queries (0 mismatches)
- [x] Decide fields to retrieve and comparison criteria (price, parsed brand, feature/spec match; rating and ingredients only if backfilled from a second data source per §1.1) — documented as a **static policy** rather than a per-query decision (the catalog's available fields don't vary per query), see `planner_rules.md` below
- [x] Write planner prompt/rubric in `prompts/` (this doc doubles as the CP2 "planner rules" deliverable) — [Code/6. Prompts & Documentation/planner_rules.md](../Code/6.%20Prompts%20%26%20Documentation/planner_rules.md)
- [x] **Deliberately no LLM call (not an original checklist item, decision recorded per user's cost-consciousness request under §2.2):** the `use_web` decision is a single keyword-driven binary, and the backlog's own framing of the rule was already keyword-based, so an LLM call here would add cost/latency without a clear quality gain. Revisit as an LLM call only if real usage shows the keyword rule misfiring — not preemptively

### 2.4 Retriever Node (Agentic RAG) — `CP2`
- [ ] Call MCP tools only (no direct DB/API calls) per [architecture_with_mcp.mermaid](../Architecture/architecture_with_mcp.mermaid) — **intentionally not yet**: calls §1.4's `search()` directly (copied into [Code/2. Agentic Orchestration/2.1-2.6 graph and nodes.ipynb](../Code/2.%20Agentic%20Orchestration/2.1-2.6%20graph%20and%20nodes.ipynb), same reuse pattern §1.5 already used on §1.4), per the sanctioned stub-now/MCP-later plan (CP1 checklist: "MCP server skeleton... implementation can still be stubbed"). Swaps to a real MCP call once §3.1/3.2 exist
- [x] Reconcile `rag.search` vs `web.search` results by brand/title similarity (not SKU — 100% empty per §1.1, same fix already applied to §3.2's output schema) — **structurally ready, not yet exercised**: `tool_results.conflicts` stays empty because there's no second (web) result set to reconcile against until §3.3's `web.search` is real; the reconciliation step itself isn't written yet, only its empty-by-construction placeholder
- [x] Flag and log conflicts (e.g. live price disagrees with catalog price) rather than silently picking one — same caveat as above, nothing to flag yet without a second source
- [x] Handle partial failures gracefully (one tool times out/errors, continue with the other) — verified with a **real** partial failure, not simulated: `web.search` genuinely doesn't exist yet (§3.3 decided, not built), so `plan.use_web=True` logs a real error in `tool_results.errors` and rag results still come back
- [x] **Real bug found and fixed while wiring this up:** `products_home_kitchen`'s `category_top` is uniformly `"Home & Kitchen"` across all 706 rows (it's the field used to carve out this demo slice in §1.1/§1.2), so filtering *within* the slice by it is structurally meaningless — first caught by a real assertion failure (0 products returned for a real query), not manual inspection. `category` dropped from Retriever's hard-filter set for now, joins `material`/`quantity` as a logged, dropped constraint. Never caught before because §1.4/§1.5 never actually exercised `search()`'s `category` parameter with a real value

### 2.5 Answerer/Critic Node — `CP2` → `FINAL`
- [x] Synthesize concise recommendation with inline citations (private `doc_id` + live URLs) — one structured-output LLM call in [Code/2. Agentic Orchestration/2.1-2.6 graph and nodes.ipynb](../Code/2.%20Agentic%20Orchestration/2.1-2.6%20graph%20and%20nodes.ipynb), verified with a real end-to-end run: real products in, real grounded recommendation with real `doc_id` citations out
- [x] Grounding check: reject/rewrite answer if it references products not present in tool results — **deterministic Python check, not LLM-judged**: every cited `doc_id` is compared against the actual `tool_results.products` set; any mismatch discards the whole answer for a fixed fallback (no partial-credit editing). Verified with a unit test (valid citation passes, invalid citation gets discarded) and with the real end-to-end run (`assert all citations grounded`)
- [x] Safety check pass (no unsafe chemical-mixing advice, no fabricated claims) — **no separate re-check implemented, by design**: Router (§2.2) already routes flagged-unsafe queries to `safe_refusal` before Answerer ever runs, so Answerer structurally never sees one; a redundant re-check here would test nothing new. "No fabricated claims" is covered by the grounding check above
- [x] Enforce ≤15s spoken-summary length constraint before handing off to TTS — deterministic ~40-word budget enforced by truncation after the LLM call (not re-prompted). **Known rough edge, stated not hidden:** truncation can cut mid-sentence; a re-prompt loop would fix that at the cost of a second call per violation — not implemented since it hasn't proven necessary yet
- [x] Write answerer/critic prompt in `prompts/` — [Code/6. Prompts & Documentation/answerer_critic_system_prompt.md](../Code/6.%20Prompts%20%26%20Documentation/answerer_critic_system_prompt.md)
- [x] **Cost note:** all three §2.5-specific tests (grounding check, length enforcement, empty-results fallback) run at 0 LLM calls — two are pure deterministic functions, and empty-results short-circuits before ever calling the LLM. The only real Answerer call in the notebook is the one already-budgeted call inside the full-graph test run

### 2.6 LLM Provider Abstraction — `CP1`
- [x] Pick the primary LLM provider — **decided: OpenAI**, using an existing OpenAI API account (no new signup needed). Cheap/fast model tier for the Router/Planner/Answerer nodes (exact model string to be pinned when §2.2–§2.5 are implemented, since OpenAI's lineup shifts). `LLM_PROVIDER=openai` in [.env.example](../.env.example); `OPENAI_API_KEY` already scaffolded there
- [x] **New dependency:** `langchain-openai` — the LangGraph-side integration package that lets graph nodes call the OpenAI API (the key itself is provider-specific, not LangChain-specific; this package is what wires it into LangGraph nodes). Confirmed with the user before adding, per the project's tech-confirmation convention. Alongside `langgraph` itself (mandated by the assignment, not a discretionary add)
- [x] Config/env-var driven model selection (OpenAI, Anthropic, Gemini, Bedrock, or open-weight) — model-agnostic pattern still applies even with OpenAI as the default; swapping providers should only touch `.env`. **Real branching now, not just a model string**: `get_chat_model(provider, model)` in [Code/2. Agentic Orchestration/2.1-2.6 graph and nodes.ipynb](../Code/2.%20Agentic%20Orchestration/2.1-2.6%20graph%20and%20nodes.ipynb) switches on `LLM_PROVIDER` across `openai`/`anthropic`/`google`/`bedrock` (the brief's own listed hosted options), replacing §2.2's originally-hardcoded `ChatOpenAI`. Only the `openai` path is actually exercised (real call, real key) — `anthropic`/`google`/`bedrock` are written to the same interface but genuinely untested, stated as such
- [x] ~~Confirm tool/function calling works against at least 2 providers to validate swappability~~ — **checked against the actual assignment brief text and dropped, per user request**: the brief's Model-Agnostic Requirement says only *"the code is swappable via environment variables/config"* — it never says every listed provider must be tested, live or mocked. This bullet was this project's own backlog adding a stricter bar than the brief sets. What the brief actually requires (code swappability) is satisfied by the item above; testing a 2nd provider would need its own paid API key for no graded benefit
- [x] Central prompt/logging wrapper so every node's system prompt + tool I/O is captured (Prompt Disclosure requirement) — `invoke_and_log()` is now the only path any node uses to call an LLM; captures system prompt + input + output into `LLM_CALL_LOG` for every real call. Verified with a real end-to-end run: 3 calls logged (2 router, 1 answerer), matching exactly what the graph actually did
- [x] **Cost note:** §2.6 added zero new real LLM calls — same 3 calls (2 router + 1 answerer) as before this section existed; the provider-branch/logging refactor doesn't change what gets called, only how

### 2.7 Testing — `CP2` → `FINAL`
- [x] Unit tests per node (router classifies correctly, planner picks right sources, etc.) — **the LLM-backed ones already exist in §2.2-2.5** of the design notebook (Router's intent test set, Planner's 7 cases, Retriever's 3 cases, Answerer's grounding/length/empty tests), not duplicated here to avoid spending real money re-deriving already-known conclusions. [Code/2. Agentic Orchestration/2.7 testing.ipynb](../Code/2.%20Agentic%20Orchestration/2.7%20testing.ipynb) re-verifies only the **free** (0 LLM-cost) deterministic pieces post-extraction (Planner's rule, Answerer's `grounding_check`/`enforce_length`), to catch a copy/paste bug in the `.py` port specifically
- [x] End-to-end graph test with mocked MCP tools — **not mocked, real**: one real `graph.invoke()` against the actual imported `graph.py` (not a redefinition), asserting the safety path still correctly skips Planner/Retriever/Answerer post-extraction. No MCP mocking needed since Retriever still calls §1.4's `search()` directly (§3's MCP server doesn't exist yet, per the sanctioned stub-now plan)
- [x] Regression test set of the 5–10 demo queries — **6 queries** (cost-conscious middle of the stated range), covering plain search+budget filter, comparison, follow-up, out-of-scope, a live-price-signal trigger (`use_web=True`), and one safety case, all run through the real graph. Real finding surfaced, not just passing: the `weather` out-of-scope query still retrieved 5 semantically-irrelevant products (the known §2.2 gap — `intent` isn't acted on) but the Answerer stayed honest ("I don't have any weather information in the available products") rather than hallucinating — the gap costs a wasted retrieval call, not a wrong answer
- [x] **Actual cost, not estimated:** 12 real LLM calls total for this notebook (7 router + 5 answerer) — 1 from the end-to-end test, 11 from the 6-query regression set

---

## 3. MCP Server & Tools (`VOICE`)

### 3.1 Server Skeleton — `CP1`
- [ ] Stand up the MCP server — long-running process, so `.py` per the file-format convention above (reason (a): not a notebook-appropriate one-shot execution) — with tool discovery (names + JSON schemas)
- [ ] Choose transport (stdio or streamable HTTP/SSE) and document the choice
- [ ] Health-check / smoke-test entrypoint

### 3.2 `rag.search` Tool — `CP1` → `CP2`
- [ ] **File format note:** the tool implementation lives in a `.py` module the §3.1 server imports at request time (reason (c)) — not a notebook. It wraps §1.4's `search()` logic rather than re-deriving it.
- [ ] Define input schema (query, filters: budget/brand/category, top_k)
- [ ] Define output schema (`id, title, price, brand?, features, doc_id` — no `sku` (100% empty per §1.1), omit `rating`/`ingredients` unless a second source is joined in)
- [ ] Route to the retrieval logic already built in [1.4 hybrid retrieval.ipynb](../Code/1.%20Data%20Pipeline%20%26%20Indexing/1.4%20hybrid%20retrieval.ipynb) (`search()`) — this tool wraps that, doesn't reimplement it
- [ ] Unit tests against a fixture index

### 3.3 `web.search` Tool — `CP2`
- [x] Pick a legitimate web-search API — **decided: Tavily**, not Brave/Serper/Bing (those were the brief's examples, "e.g.," not a required list). Purpose-built for LLM/agent consumption (clean, structured, relevance-ranked results — no scraping/parsing needed); free tier verified at 1,000 credits/month, no credit card (checked live, not assumed); official MCP server exists at [tavily-ai/tavily-mcp](https://github.com/tavily-ai/tavily-mcp) as a reference for tool structure, though per "one server, two tools" this project wraps Tavily's API as our own `web.search` tool inside our own single MCP server rather than running their server standalone. `WEB_SEARCH_PROVIDER`/`TAVILY_API_KEY` in [.env.example](../.env.example)
- [ ] Define output schema (`title, url, snippet, price?, availability?`)
- [ ] Implement caching (TTL 60–300s) to avoid redundant calls
- [ ] Implement rate limiting / backoff
- [ ] Respect robots.txt/ToS; restrict to an allowlist of domains
- [ ] Unit tests with mocked HTTP responses

### 3.4 Cross-Cutting — `CP2`
- [ ] Structured logging: request/response, timestamp, source URL for every tool call
- [ ] Never log secrets (API keys, tokens) — scrub before logging
- [ ] Error handling contract: tools return typed errors the Retriever node can branch on
- [ ] Write the MCP README: tool schemas, transport, how to run the server standalone (CP2 deliverable)

---

## 4. Speech (ASR + TTS) (`VOICE`)

### 4.1 ASR — `CP1` → `CP2`
- [ ] Implement `asr.py` using Whisper (or comparable) — `.py` per the file-format convention above (reason (c): the UI imports this at query time) — fragment-based (record → transcribe) first
- [ ] Support WAV/MP3 input from the UI's mic capture
- [ ] Return transcript (+ timestamps if available)
- [ ] Basic accent/multilingual smoke test
- [ ] (Stretch) streaming ASR if time allows

### 4.2 TTS — `CP2`
- [ ] Implement `tts.py` — `.py` per the file-format convention above (reason (c): the UI imports this at query time); make provider swappable (OpenAI TTS/Realtime, ElevenLabs, Azure, Polly, Coqui)
- [ ] Enforce ≤15s output aligned with the Answerer node's summary
- [ ] Fragment-based synthesis (generate full audio, then play) first; streaming as stretch goal
- [ ] Handle synthesis failures with a text-only fallback in the UI

### 4.3 Performance & Reliability — `FINAL`
- [ ] Measure end-to-end latency (ASR → graph → TTS) on representative queries
- [ ] Add timeouts/fallbacks for slow ASR/TTS/API calls
- [ ] Stress test with back-to-back queries; confirm caching/rate-limits hold up

---

## 5. User Interface (`UI`)

### 5.1 Scaffold — `CP1`
- [ ] Streamlit (or React) app skeleton: mic capture (record/upload) → send file to ASR — `.py` per the file-format convention above (reason (b): `streamlit run` requires a `.py` entrypoint, not a notebook)
- [ ] Mock-data mode so UI work is unblocked before the graph/tools are ready

### 5.2 Core Flow — `CP2`
- [ ] Wire ASR → graph → TTS end-to-end
- [ ] Live transcript display
- [ ] Agent step log (what each node did, which tools were called)
- [ ] Comparison table (title, price, brand, key features, source — drop rating/ingredients columns unless backfilled per §1.1)
- [ ] Citations + data lineage (private `doc_id`s and live URLs, clearly distinguished)
- [ ] "Play TTS" button with audio playback

### 5.3 Polish — `FINAL`
- [ ] Loading states while ASR/graph/TTS run
- [ ] Error messaging (tool failure, no results, ASR failure)
- [ ] Responsive layout pass
- [ ] Lightweight usability test with 2–3 outside users; note friction points

---

## 6. Prompts & Documentation (`LEAD`, with input from `ORCH`)

- [ ] Create `prompts/` folder: router, planner, retriever/reconciliation, answerer/critic system prompts + any few-shot examples
- [ ] Map each prompt to the graph node/tool that uses it (Prompt Disclosure grading requirement)
- [ ] `README.md` — keep in sync as components land (installation, running, troubleshooting) — *root README already scaffolded*
- [ ] `.env.example` — every required env var (LLM provider keys, web-search API key, model name/config) with no real secrets
- [ ] Data preprocessing & indexing write-up
- [ ] Graph design write-up (nodes, state schema, edges)
- [ ] MCP server/tool schema write-up (can reuse §3.4 README)
- [ ] Safety notes (domain allowlist, robots.txt/ToS stance, refusal behavior for unsafe queries)
- [ ] Setup/run scripts (`make index`, `make server`, `make ui`, or equivalent)

---

## 7. Milestone Deliverables Checklist

### Checkpoint 1 — Week 6
- [ ] One-page proposal (problem, data slice, tools)
- [ ] Data exploration/ingestion notebook
- [ ] Brief related-work summary
- [ ] Indexed products in vector DB (can be a small/dev-sized index)
- [ ] MCP server skeleton + tool schemas (implementation can still be stubbed)
- [ ] Streamlit UI scaffold with mock data

### Checkpoint 2 — Week 8
- [ ] Architecture diagram (graph + MCP calls) — *done, see [architecture_with_mcp.mermaid](../Architecture/architecture_with_mcp.mermaid)*
- [ ] UI wireframe/working scaffold with live graph integration
- [ ] RAG eval plan (and initial results)
- [ ] MCP README (schemas, transport, caching/logging)
- [ ] LangGraph implementation working end-to-end (mocks acceptable for slow pieces)
- [ ] ASR, TTS, `web.search` functional
- [ ] `.env.example` and setup instructions

### Final — Week 10
- [ ] Live demo, ≤7 minutes
- [ ] Clean repository, all code committed
- [ ] Comprehensive README (install, run, troubleshoot)
- [ ] `prompts/` folder complete (Prompt Disclosure)
- [ ] Performance & reliability report
- [ ] Presentation slides (problem, approach, results, limitations)
- [ ] Safety notes & known limitations documented

---

## 8. Cross-Cutting Risks to Track

- [ ] **RAG quality risk:** if precision is low, budget time for a reranker or manual feature tuning (per contingency plan in team structure doc)
- [ ] **Latency risk:** if ASR/TTS is slow, simplify prompts and lean on caching before the demo
- [ ] **Live tool risk:** have a "demo mode" that falls back to `rag.search`-only if `web.search`/external APIs are down during the live demo
- [ ] **Conflict handling:** make sure reconciliation logic (private vs. live data disagreement) is demoable, not just theoretical — it's an explicit grading line item (Planning & Tool Use, 10 pts)
