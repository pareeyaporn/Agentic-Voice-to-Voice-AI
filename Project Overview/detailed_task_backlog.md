# Detailed Task Backlog

Granular, checkable task list for building the Agentic Voice-to-Voice AI assistant. Complements [team_structure_and_task_breakdown.md](team_structure_and_task_breakdown.md) (who owns what, at a role level) with the actual engineering tasks each role needs to complete, grouped by component, each tagged with owner and target checkpoint.

**Legend — Owner:** `ORCH` Orchestration Lead · `DATA` Data Engineer · `VOICE` Voice/Integration Engineer · `UI` Frontend/UI Engineer · `LEAD` Project Lead
**Legend — Checkpoint:** `CP1` Week 6 · `CP2` Week 8 · `FINAL` Week 10

---

## 1. Data Pipeline & Indexing (`DATA`)

### 1.1 Acquisition & Exploration — `CP1`
- [x] Download Amazon Product Dataset 2020 via `kagglehub.dataset_download("promptcloud/amazon-product-dataset-2020")` — resolves to `marketing_sample_for_amazon_com-ecommerce__20200101_20200131__10k_data.csv`, 10,002 rows × 28 columns (verified 2026-08-15)
- [x] Confirmed real column set: `Uniq Id, Product Name, Brand Name, Asin, Category, Upc Ean Code, List Price, Selling Price, Quantity, Model Number, About Product, Product Specification, Technical Details, Shipping Weight, Product Dimensions, Image, Variants, Sku, Product Url, Stock, Product Details, Dimensions, Color, Ingredients, Direction To Use, Is Amazon Seller, Size Quantity Variant, Product Description`
- [x] **Known data gaps (confirmed by running [Code/data/explore_data.ipynb](../Code/data/explore_data.ipynb) against the full 10,002-row CSV — broader than the initial hand check):**
  - **13 of 28 columns are 100% empty**, not just 2: `Product Description, Stock, Size Quantity Variant, Product Details, Dimensions, Color, Quantity, Ingredients, Asin, Brand Name, Direction To Use, List Price, Sku`
  - **`Asin` and `Sku` are both entirely empty** — there is no reliable external product key to join a second dataset on; any join (e.g. for ratings) would have to be fuzzy, by title, not authoritative
  - **No rating/stars column exists at all** — the "4.6★ rating" in the brief's example interaction is not backed by this dataset; either drop rating from the pitch/UI or fuzzy-join a second ratings source
  - **No review-level data** — this is a single flat product table, not a products+reviews pair
  - `Category` is only 91.7% populated (830 blank rows); `Selling Price` is 98.9% non-null but only 95.2% parse to a clean number; `Product Name` has 137 duplicate values
  - Category distribution is skewed: ~67% `Toys & Games`; `Home & Kitchen` (708–712 rows) and `Sports & Outdoors` (540 rows) are the next largest; `Household`/`Cleaning` categories total only ~25 rows combined — **too sparse to use as the demo slice**
- [x] Pick category slice sized for a demo (~500+ products) — **decided: `Home & Kitchen`** (708–712 rows) instead of Household Cleaning, given actual row counts
- [x] Exploratory notebook (CSV in, CSV out — no parquet, per project convention): [Code/data/explore_data.ipynb](../Code/data/explore_data.ipynb) — field coverage/nulls per column, price distribution (`Selling Price`), duplicate check (`Asin`/`Uniq Id`/`Product Name`), category distribution, plus charts (field-coverage bar, price-distribution histogram, category-distribution bar) for all three; self-contained and pre-executed with real output. Writes [Code/data/processed/column_coverage.csv](../Code/data/processed/column_coverage.csv)
- [x] Decide final working schema given the gaps above — see [data_schema_and_licensing.md](data_schema_and_licensing.md) for the full `products_clean.csv` field mapping
- [x] Document data licensing/usage constraints — see [data_schema_and_licensing.md](data_schema_and_licensing.md) (CC0 Public Domain)
- [ ] (Optional, if rating/reviews are wanted) Evaluate a second PromptCloud/Kaggle dataset to fuzzy-join in ratings or review snippets by title (no `Asin`/`Sku` available as a clean join key)

### 1.2 Preprocessing — `CP1`
- [ ] Clean text fields (strip HTML, normalize whitespace/encoding) in `Product Name`, `About Product`, `Product Description`
- [ ] Extract brand from `Product Name`/`About Product` text (regex or LLM extraction) since `Brand Name` is unpopulated
- [ ] Normalize units for fair comparison where package size is parseable (e.g. price per oz/count)
- [ ] Deduplicate near-identical listings (same ASIN/title variants)
- [ ] Flatten/parse the pipe-delimited `Category` hierarchy into usable filter fields
- [ ] Persist cleaned `products_clean.csv` to `Code/data/processed/` (no reviews file — none exists for this dataset, per §1.1)

### 1.3 Embedding & Indexing — `CP1` → `CP2`
- [ ] Choose embedding model (must be swappable via config, consistent with model-agnostic LLM requirement)
- [ ] Build embedding text = `Product Name` + `About Product` (+ `Product Specification`/`Technical Details` if useful)
- [ ] Stand up vector store (Chroma or FAISS) with metadata payload attached to each vector
- [ ] Write `data_index.py` build script (idempotent, re-runnable on data changes)
- [ ] Add a `make index` / CLI entrypoint so anyone can rebuild the index locally

### 1.4 Hybrid Retrieval — `CP2`
- [ ] Implement vector search + metadata filter combination (budget, parsed brand, category — skip ingredient filters unless a source is added per §1.1)
- [ ] Add unit-aware ranking/tie-breaking (e.g. price-per-oz when comparing sizes)
- [ ] (Optional) Add a reranker pass over top-k candidates
- [ ] Return results with `doc_id` for citation traceability

### 1.5 RAG Evaluation — `CP2` → `FINAL`
- [ ] Build a small labeled eval set (10–20 representative queries with expected top products)
- [ ] Measure precision/recall@k on the eval set
- [ ] Log failure cases (wrong brand match, missed budget filter, stale price) and iterate
- [ ] Write up eval methodology + results for the RAG Eval Plan (CP2 deliverable)

---

## 2. Agentic Orchestration — LangGraph (`ORCH`)

### 2.1 Graph Design — `CP1`
- [ ] Define graph state schema (query, transcript, constraints, plan, tool results, citations, safety flags, final answer)
- [ ] Sketch node graph: Router → Planner → Retriever → Answerer/Critic (matches [architecture_with_mcp.mermaid](../Architecture/architecture_with_mcp.mermaid))
- [ ] Decide conditional edges (e.g. skip web.search unless query implies "current/latest/now")

### 2.2 Router Node — `CP1` → `CP2`
- [ ] Intent classification: is this a product search/comparison/follow-up/out-of-scope query?
- [ ] Constraint extraction: budget, material, brand, category, quantity
- [ ] Safety flag detection (e.g. unsafe chemical mixing questions) → route to a safe-refusal path
- [ ] Write & version the router system prompt in `prompts/`

### 2.3 Planner Node — `CP1` → `CP2`
- [ ] Source selection rule: prefer `rag.search`; add `web.search` when query implies live price/availability
- [ ] Decide fields to retrieve and comparison criteria (price, parsed brand, feature/spec match; rating and ingredients only if backfilled from a second data source per §1.1)
- [ ] Write planner prompt/rubric in `prompts/` (this doc doubles as the CP2 "planner rules" deliverable)

### 2.4 Retriever Node (Agentic RAG) — `CP2`
- [ ] Call MCP tools only (no direct DB/API calls) per [architecture_with_mcp.mermaid](../Architecture/architecture_with_mcp.mermaid)
- [ ] Reconcile `rag.search` vs `web.search` results by SKU/brand/title similarity
- [ ] Flag and log conflicts (e.g. live price disagrees with catalog price) rather than silently picking one
- [ ] Handle partial failures gracefully (one tool times out/errors, continue with the other)

### 2.5 Answerer/Critic Node — `CP2` → `FINAL`
- [ ] Synthesize concise recommendation with inline citations (private `doc_id` + live URLs)
- [ ] Grounding check: reject/rewrite answer if it references products not present in tool results
- [ ] Safety check pass (no unsafe chemical-mixing advice, no fabricated claims)
- [ ] Enforce ≤15s spoken-summary length constraint before handing off to TTS
- [ ] Write answerer/critic prompt in `prompts/`

### 2.6 LLM Provider Abstraction — `CP1`
- [ ] Config/env-var driven model selection (OpenAI, Anthropic, Gemini, Bedrock, or open-weight)
- [ ] Confirm tool/function calling works against at least 2 providers to validate swappability
- [ ] Central prompt/logging wrapper so every node's system prompt + tool I/O is captured (Prompt Disclosure requirement)

### 2.7 Testing — `CP2` → `FINAL`
- [ ] Unit tests per node (router classifies correctly, planner picks right sources, etc.)
- [ ] End-to-end graph test with mocked MCP tools
- [ ] Regression test set of the 5–10 demo queries

---

## 3. MCP Server & Tools (`VOICE`)

### 3.1 Server Skeleton — `CP1`
- [ ] Stand up `mcp_server.py` with tool discovery (names + JSON schemas)
- [ ] Choose transport (stdio or streamable HTTP/SSE) and document the choice
- [ ] Health-check / smoke-test entrypoint

### 3.2 `rag.search` Tool — `CP1` → `CP2`
- [ ] Define input schema (query, filters: budget/brand/category, top_k)
- [ ] Define output schema (`sku, title, price, brand?, features, doc_id` — omit `rating`/`ingredients` unless a second source is joined in per §1.1)
- [ ] Route to `tools/rag_search.py`, which calls the vector DB built in §1.3
- [ ] Unit tests against a fixture index

### 3.3 `web.search` Tool — `CP2`
- [ ] Pick a legitimate web-search API (Brave/Serper/Bing) and get API keys into `.env.example` (never committed)
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
- [ ] Implement `asr.py` using Whisper (or comparable) — fragment-based (record → transcribe) first
- [ ] Support WAV/MP3 input from the UI's mic capture
- [ ] Return transcript (+ timestamps if available)
- [ ] Basic accent/multilingual smoke test
- [ ] (Stretch) streaming ASR if time allows

### 4.2 TTS — `CP2`
- [ ] Implement `tts.py`; make provider swappable (OpenAI TTS/Realtime, ElevenLabs, Azure, Polly, Coqui)
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
- [ ] Streamlit (or React) app skeleton: mic capture (record/upload) → send file to ASR
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
