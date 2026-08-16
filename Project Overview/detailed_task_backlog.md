# Detailed Task Backlog

Granular, checkable task list for building the Agentic Voice-to-Voice AI assistant. Complements [team_structure_and_task_breakdown.md](team_structure_and_task_breakdown.md) (roles) with the actual engineering tasks, grouped by component, tagged with owner and target checkpoint.

**Owner:** `ORCH` Orchestration Lead · `DATA` Data Engineer · `VOICE` Voice/Integration Engineer · `UI` Frontend/UI Engineer (4-person team, no separate Project Lead — see [team_structure_and_task_breakdown.md](team_structure_and_task_breakdown.md))
**Checkpoint:** `CP1` Week 6 · `CP2` Week 8 · `FINAL` Week 10

**File format:** `.ipynb` by default; `.py` only for a long-running process (§3.1 MCP server), a framework entrypoint (§5.1 `streamlit run app.py`), or a module a running `.py` process imports at query time.

---

## 1. Data Pipeline & Indexing (`DATA`)

### 1.1 Acquisition & Exploration — `CP1`
- [x] Downloaded Amazon Product Dataset 2020 — 10,002 rows × 28 columns
- [x] Data gaps: 13/28 columns 100% empty (`Asin`, `Sku`, `Brand Name`, `List Price`, etc.); no rating/review data at all; `Category` 91.7% populated; `Product Name` has 137 duplicates
- [x] Picked **`Home & Kitchen`** (708–712 rows) as the demo slice — largest viable category after Toys & Games (~67% of the dataset, too broad)
- [x] Exploration notebook: [1.1 explore data.ipynb](../Code/1.%20Data%20Pipeline%20&%20Indexing/1.1%20explore%20data.ipynb) — coverage/price/duplicate/category analysis + charts
- [x] Schema + licensing: [data_schema_and_licensing.md](data_schema_and_licensing.md) (CC0 Public Domain)
- [ ] (Optional) Fuzzy-join a second dataset for ratings/reviews — no clean join key exists

### 1.2 Preprocessing — `CP1`
- [x] Cleaned text fields (HTML strip, unicode normalize, whitespace collapse)
- [x] Brand extracted via regex from `Product Name` (`Brand Name` is empty) — ~96% coverage but low accuracy on spot-check (~5/12 exact); treat as a coarse signal only
- [x] Price-per-unit normalized where package size is parseable (~10% of rows)
- [x] Deduplicated on exact title match (10,002 → 9,930 rows)
- [x] `Category` flattened into `category_top` / `category_full`
- [x] Output: [products_clean.csv](../Code/1.%20Data%20Pipeline%20&%20Indexing/processed/products_clean.csv) (9,930 rows × 13 columns)
- [x] Post-cleaning recheck: `Home & Kitchen` slice is 706 rows, kids'-goods-heavy (Kitchen & Dining only ~7.5%), not cookware-heavy

### 1.3 Embedding & Indexing — `CP1` → `CP2`
- [x] Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (local, free, config-driven)
- [x] Embedding text = title + features, falling back to technical_details/spec
- [x] Chroma vector store, two collections in two persist dirs (kept under GitHub's 50MB limit): `products_home_kitchen` (706 rows, 6.6MB, committed) and `products_all` (9,930 rows, ~65MB, gitignored)
- [x] PCA + t-SNE embedding-space visualization by category (added on request)
- [x] New dependency: `scikit-learn` (confirmed with user)
- [x] Fixed a PyTorch/scikit-learn OpenMP segfault via `OMP_NUM_THREADS=1` + `KMP_DUPLICATE_LIB_OK=TRUE`
- [x] Build notebook: [1.3 build index.ipynb](../Code/1.%20Data%20Pipeline%20&%20Indexing/1.3%20build%20index.ipynb) (idempotent rebuild)

**Finding:** the brief's example queries ("frying pan", "coffee maker") return poor matches — this dataset has near-zero cookware, a data-coverage gap, not a retrieval bug. Reframed demo queries around what the data supports (lunch boxes, bedding, party supplies) — see README.

### 1.4 Hybrid Retrieval — `CP2`
- [x] Vector + metadata filtering: `category`/`budget_min`/`budget_max` via Chroma's `where`; `brand` via over-fetch + substring post-filter (too noisy for exact match)
- [x] Unit-aware tie-breaking: compares same-unit candidates pairwise instead of against the single best match — fixed a real ranking bug (cheapest-per-unit item moved from 7th to 3rd on a test query)
- [x] Reranker skipped — results already strong without one
- [x] Results carry `doc_id` + `url` for citations
- [x] `search()` is collection-agnostic (defaults to `products_home_kitchen`, also works against `products_all`)

### 1.5 RAG Evaluation — `CP2` → `FINAL`
- [x] 14-query eval set (10 plain, 2 filtered, 2 full-catalog); ground truth is a keyword/substring proxy on title (no human labels exist — stated limitation)
- [x] **Precision@5 = 0.90.** Recall@5 = 0.32, but that's a structural artifact of the proxy ground-truth sizes, not a real quality signal — precision is the informative number here
- [x] Logged failure cases — the keyword ground truth itself has both false negatives and false positives
- [x] Write-up: [rag_eval_plan.md](rag_eval_plan.md)
- [x] Filters validated by the eval (budget/brand both hit strong precision/recall)
- [x] Reranker-skip decision confirmed by the eval numbers

---

## 2. Agentic Orchestration — LangGraph (`ORCH`)

### 2.1 Graph Design — `CP1`
- [x] 8-field `GraphState` schema (`TypedDict`s: `GraphState`, `Plan`, `ToolResults`)
- [x] Node graph: Router → Planner → Retriever → Answerer/Critic, built as a real compiled+executed LangGraph `StateGraph`
- [x] One conditional edge: Router → `safe_refusal` vs. Planner, on `safety_flag`. The rag/web sourcing choice is data (`plan['use_web']`), read as a plain `if` inside Retriever, not a second edge
- [x] Design/prototyping in [2.1-2.6 graph and nodes.ipynb](../Code/2.%20Agentic%20Orchestration/2.1-2.6%20graph%20and%20nodes.ipynb) (frozen record); later extracted into `.py` modules (`config.py`, `state.py`, `providers.py`, `router.py`, `planner.py`, `retriever.py`, `answerer.py`, `graph.py`) once §2.7 needed a real importable graph

### 2.2 Router Node — `CP1` → `CP2`
- [x] Intent classification (search/comparison/follow-up/out-of-scope) via one structured-output LLM call. Known gap: `intent` isn't acted on — an out-of-scope query still flows through the graph instead of short-circuiting
- [x] Constraint extraction (budget/material/brand/category/quantity) in the same call
- [x] Safety-flag detection → routes to `safe_refusal`, verified end-to-end
- [x] Prompt: [router_system_prompt.md](../Code/6.%20Prompts%20%26%20Documentation/router_system_prompt.md) — now includes a 4-row few-shot examples table (added after the charter re-read found the Prompt Disclosure line explicitly expects few-shot examples, and none of the 3 prompts originally had any). Verified with real calls after adding: still parses correctly, and the safety-flag example's exact wording showed up in a real follow-up call's output
- [x] Model: `gpt-5.6-luna`

### 2.3 Planner Node — `CP1` → `CP2`
- [x] `use_rag` always `True`; `use_web` decided by a real LLM tool call — [planner_system_prompt.md](../Code/6.%20Prompts%20%26%20Documentation/planner_system_prompt.md)
- [x] **Revised from the original keyword-rule version, not the original build:** first shipped as a free keyword check (`current`/`latest`/`now`/`in stock`/etc., no LLM call). Re-reading the charter surfaced that its LLM guideline explicitly asks to "keep tool-use enabled (function/tool calling)," and this project made zero use of any LLM's native tool-calling API anywhere — the keyword rule never touched an LLM, and Router/Answerer's structured output used OpenAI's separate JSON-schema mode, not tool-calling. Fixed by giving Planner a real `WebSearch` tool via `.bind_tools()` and letting the model decide whether to call it, replacing the keyword list. Verified against the same 4 representative queries the keyword version was tested on — same decisions, now via a real tool call
- [x] **Real, new cost, confirmed with the user before building:** this adds one real LLM call per query where Planner previously cost $0
- [x] **Real API snag found and fixed:** the pinned model (a reasoning model) rejected tool-calling on the `/v1/chat/completions` surface outright ("Function tools with reasoning_effort are not supported... use /v1/responses") -- caught by actually running it, not assumed to work. Fixed by defaulting `use_responses_api=True` for the openai provider in `providers.py`'s `get_chat_model()`, which routes through `/v1/responses` instead
- [x] **Router and Answerer also switched to real tool-calling** (`method="function_calling"` on their `with_structured_output()` calls) for the same charter-alignment reason -- free: same one call each, same parsed result, just OpenAI's tool-calling API instead of its separate structured-output API. Verified both still parse correctly with real calls

### 2.4 Retriever Node (Agentic RAG) — `CP2`
- [x] Calls MCP tools only, via a persistent client (`mcp_client.py`), not `search()` directly. Server starts once per process (~0.2s first call, ~0.01s after); node is `async def`, graph runs via `await graph.ainvoke(...)`
- [x] Reconciles rag/web results by title similarity, flags price conflicts (`reconcile()`, `difflib.SequenceMatcher`) — unit-verified with synthetic data; 0 conflicts found in real runs so far (results genuinely didn't overlap)
- [x] Partial tool failures handled via typed `ToolCallError`, not a crash
- [x] Fixed: `category_top` is constant within `products_home_kitchen`, so filtering by it there is meaningless — dropped client-side, now forwarded again since the server (§3.2) warns instead of silently dropping
- [x] Fixed an anyio bug: closing the MCP session from a different asyncio Task than opened it raises `RuntimeError` (anyio ties cancel scopes to the opening task; LangGraph runs async nodes in its own task) — `mcp_client.close()` now catches and logs this rather than crashing; affects shutdown cleanliness only, not correctness
- [x] Known gap (resolved in §2.5): web results had no `doc_id`, so citations were rag-only by construction

### 2.5 Answerer/Critic Node — `CP2` → `FINAL`
- [x] One structured-output LLM call synthesizes recommendation + citations
- [x] Grounding check: deterministic — every cited ref must match a real retrieved product, else the whole answer is discarded for a fixed fallback
- [x] No separate safety re-check — Router already filters unsafe queries before Answerer runs
- [x] ~40-word length budget enforced by truncation (can cut mid-sentence — known rough edge)
- [x] Prompt: [answerer_critic_system_prompt.md](../Code/6.%20Prompts%20%26%20Documentation/answerer_critic_system_prompt.md) — now includes 2 worked examples (rag-only, mixed rag+web) showing candidates in, `{answer, citations}` out, reinforcing the "never speak a ref in `answer`" rule concretely rather than only stating it
- [x] **Fixed:** the model occasionally spoke a raw `doc_id` aloud (~40% of runs on one low-context query) — prompt tension between "cite by doc_id" and "don't recite IDs." Fixed with a clearer prompt (dropped the leak to 0/6) plus a deterministic regex backstop, `scrub_raw_ids()`
- [x] **Citation schema fix:** `doc_id` was required, so web results (url-only) could never be cited. Replaced with a generic `ref` field (doc_id or url), resolved to `{source, doc_id, url, title}` by lookup against real products — the LLM never self-classifies rag vs. web
- [x] **Second, deeper bug:** `format_candidates()` truncated to the first 5 products, and rag always filled all 5 — so web products never reached the LLM even after the schema fix. Fixed by giving each source its own slice (5 rag + 3 web). Verified: first web-sourced citation appeared after this fix

### 2.6 LLM Provider Abstraction — `CP1`
- [x] Provider: OpenAI (existing account); new dependency `langchain-openai` (confirmed with user)
- [x] `get_chat_model(provider, model)` branches across openai/anthropic/google/bedrock — only openai is exercised, others untested but same interface
- [x] openai branch defaults `use_responses_api=True` — found necessary by testing: the pinned reasoning model rejects tool-calling on the older `/v1/chat/completions` surface, needed for Router/Answerer/Planner's real tool-calling calls (§2.2/§2.3/§2.5)
- [x] Dropped the "test 2+ providers" bullet — the brief only requires code swappability, not live multi-provider testing
- [x] `invoke_and_log()` is the single LLM entrypoint for every node, capturing system prompt + I/O (Prompt Disclosure requirement)

### 2.7 Testing — `CP2` → `FINAL`
- [x] Free (0 LLM-cost) deterministic tests re-verified after `.py` extraction (Planner rule, grounding/length checks)
- [x] Real end-to-end `graph.invoke()` test confirms the safety path skips Planner/Retriever/Answerer
- [x] 6-query regression set through the real graph — surfaced a known, harmless gap: an out-of-scope "weather" query still retrieves products, but the Answerer stays honest rather than hallucinating
- [x] Total cost: 21 real LLM calls across this notebook (`{'planner': 9, 'router': 7, 'answerer': 5}`) -- up from 12 after Planner's keyword rule became a real tool-calling LLM call (§2.3)

---

## 3. MCP Server & Tools (`VOICE`)

### 3.1 Server Skeleton — `CP1`
- [x] `mcp_server.py`, stdio transport, both tools (`rag.search`, `web.search`) registered with real JSON schemas
- [x] New dependency: official `mcp` SDK (v2.0.0 uses `mcp.server.mcpserver.MCPServer`, not the commonly-documented `FastMCP`)
- [x] Transport: stdio — local single-process use, no network config needed
- [x] Smoke test: real subprocess + stdio round trip — [3.1 server skeleton smoke test.ipynb](../Code/3.%20MCP%20Server%20%26%20Tools/3.1%20server%20skeleton%20smoke%20test.ipynb)

### 3.2 `rag.search` Tool — `CP1` → `CP2`
- [x] [rag_search_tool.py](../Code/3.%20MCP%20Server%20%26%20Tools/rag_search_tool.py) wraps §2.4's `retriever.py` `search()`
- [x] Input: `query, top_k, budget_min, budget_max, category, brand`
- [x] Output schema corrected from the original draft: `doc_id, title, price, price_per_unit, price_unit, brand, category_top, url, distance` — `features` dropped (never stored as queryable metadata)
- [x] `category` filter returns an explicit `warnings` field when it can't narrow results, instead of silently dropping it
- [x] Tests against the real committed index (no synthetic fixture needed): [3.2 rag search tool test.ipynb](../Code/3.%20MCP%20Server%20%26%20Tools/3.2%20rag%20search%20tool%20test.ipynb), 4 cases

### 3.3 `web.search` Tool — `CP2`
- [x] Provider: Tavily (free tier, 1,000 credits/month, built for LLM consumption)
- [x] Output: `title, url, snippet, price?, availability?` — price/availability regex-extracted from snippet text (low-confidence, same posture as brand extraction)
- [x] Caching: 120s TTL, in-memory, keyed by `(query, top_k)`
- [x] Backoff: 3 attempts, transient errors only
- [x] Domain allowlist (amazon/walmart/target/ebay/bestbuy) via Tavily's `include_domains`
- [x] Tests: 1 real call + 6 mocked cases — [3.3 web search tool test.ipynb](../Code/3.%20MCP%20Server%20%26%20Tools/3.3%20web%20search%20tool%20test.ipynb)
- [x] Fixed: `web_search_tool.py` wasn't loading `.env` itself, relying on another module having done it first

### 3.4 Cross-Cutting — `CP2`
- [x] Structured logging (`@logged_tool` decorator): request/response/timestamp/source URLs
- [x] Secret scrubbing: by value + by shape (catches key-shaped strings even from unexpected sources)
- [x] Typed `ToolError(error_type, message)` contract, machine-branchable
- [x] MCP README: [Code/3. MCP Server & Tools/README.md](../Code/3.%20MCP%20Server%20%26%20Tools/README.md)

---

## 4. Speech (ASR + TTS) (`VOICE`)

### 4.1 ASR — `CP1` → `CP2`
- [x] [asr.py](../Code/4.%20Speech%20%28ASR%20%2B%20TTS%29/asr.py): local `faster-whisper` (free, no API key), lazy-loaded singleton — ~246s first call (model download), ~3.5s after
- [x] Handles WAV/MP3/webm input, verified against a real webm/opus clip (the actual browser mic-recorder format)
- [x] Returns transcript + per-segment timestamps
- [x] Multilingual smoke test via synthesized (not real human) Spanish/French audio — es/fr both detected correctly
- [ ] (Stretch) streaming ASR — not attempted

### 4.2 TTS — `CP2`
- [x] [tts.py](../Code/4.%20Speech%20%28ASR%20%2B%20TTS%29/tts.py): OpenAI TTS, provider-swappable (only the openai path is implemented)
- [x] ≤15s budget enforced by measuring actual audio duration (not just word count) and regenerating once at a faster speed if over
- [x] **Fixed:** duration measurement trusted `wave.getnframes()`, but OpenAI's streamed WAV response sets that header field to a placeholder — turned a 2s clip into a reported 24.8-day duration. Fixed by computing duration from the actual received bytes instead
- [x] Typed `TTSError`; text-only fallback is a UI-layer decision, not baked into this module

**Testing:** [4.1-4.2 speech smoke test.ipynb](../Code/4.%20Speech%20%28ASR%20%2B%20TTS%29/4.1-4.2%20speech%20smoke%20test.ipynb) — real TTS→ASR round trip, budget-correction path, multilingual case, error paths. Cost: 5 real TTS calls, ~$0.015 total.

### 4.3 Performance & Reliability — `FINAL`
- [ ] Measure end-to-end latency (needs §5's UI)
- [ ] Timeouts/fallbacks for slow calls
- [ ] Stress test back-to-back queries

---

## 5. User Interface (`UI`)

### 5.1 Scaffold — `CP1`
- [x] Streamlit app ([app.py](../Code/5.%20User%20Interface/app.py)): mic recording (`streamlit-mic-recorder`, confirmed with user) + file upload + type-text, 3 input paths
- [x] Mock-data mode (sidebar toggle, default ON) — 3 canned examples at $0 cost, also serves as a demo-mode fallback
- [x] **Fixed a real architecture risk:** `asyncio.run()` per Streamlit rerun would've silently broken §2.4's persistent MCP session (new event loop each time). Fixed with [async_runtime.py](../Code/5.%20User%20Interface/async_runtime.py) — one background event-loop thread for the process's life; verified the same `ClientSession` is reused across reruns, 2nd call ~3x faster
- [x] **Fixed:** §2's and §4's `config.py` shared the same bare module name — importing both in one process would silently collide. Renamed §4's to `speech_config.py`

### 5.2 Core Flow — `CP2`
- [x] ASR → graph → TTS wired end-to-end, verified via Streamlit's headless test API (`AppTest`)
- [x] Editable live transcript, so an ASR mistake can be fixed before the paid graph call
- [x] Agent step log via `graph.astream(..., stream_mode="updates")` — one-line summary per node
- [x] Comparison table (title/price/brand/source) — `features` dropped, same as §3.2's finding (never stored as retrievable metadata)
- [x] Citations distinguish 🗂️ catalog (`doc_id`) vs 🌐 web (URL)
- [x] "Play answer" button — real TTS playback, cached per answer text so replay doesn't re-pay; disabled in mock mode

### 5.3 Polish — `FINAL`
- [ ] Loading states, error messaging, responsive layout, usability testing

---

## 6. Prompts & Documentation (split across the 4 roles)

- [x] `prompts/` folder + Prompt Disclosure mapping — `ORCH` — [Code/6. Prompts & Documentation/](../Code/6.%20Prompts%20%26%20Documentation/) has all 3 prompts; each node's `.py` docstring names its own prompt file
- [x] Root `README.md` kept in sync — `UI`
- [x] `.env.example` kept in sync — `UI`, populated by whoever adds a dependency
- [x] Data write-up — `DATA` — [data_schema_and_licensing.md](data_schema_and_licensing.md)
- [x] Graph design write-up — `ORCH` — README's Architecture section + [graph_state_flow.mermaid](../Architecture/graph_state_flow.mermaid)
- [x] MCP write-up (reuses §3.4 README) — `VOICE`
- [x] Safety notes — `ORCH` (refusal behavior, documented in router.py) + `VOICE` (domain allowlist/ToS, in the MCP README)
- [x] Setup/run scripts — `UI` — [requirements.txt](../requirements.txt) + README's "Getting Started"

---

## 7. Milestone Deliverables Checklist

### Checkpoint 1 — Week 6
- [ ] One-page proposal
- [ ] Data exploration notebook
- [ ] Related-work summary
- [ ] Indexed vector DB
- [x] MCP server + tool schemas — fully implemented, not just stubbed
- [x] Streamlit UI scaffold with mock data

### Checkpoint 2 — Week 8
- [x] Architecture diagram — [architecture_with_mcp.mermaid](../Architecture/architecture_with_mcp.mermaid)
- [x] UI with live graph integration — real, not a wireframe
- [x] RAG eval plan — [rag_eval_plan.md](rag_eval_plan.md)
- [x] MCP README
- [x] LangGraph working end-to-end (real, not mocked)
- [x] ASR/TTS/web.search functional and wired into the UI
- [x] `.env.example` + setup instructions — [requirements.txt](../requirements.txt), README's "Getting Started"

### Final — Week 10
- [ ] Live demo ≤7 min
- [ ] Clean repository
- [ ] Comprehensive README
- [ ] `prompts/` folder complete
- [ ] Performance & reliability report
- [ ] Presentation slides
- [ ] Safety notes documented

---

## 8. Cross-Cutting Risks to Track

- [ ] RAG quality risk — reranker/tuning if precision drops
- [ ] Latency risk — simplify/cache if ASR/TTS is slow
- [ ] Live tool risk — demo mode falls back to rag-only if web.search is down
- [x] Conflict handling demoable — `reconcile()` runs for real when `use_web=True`, unit-verified to flag conflicts; no naturally-occurring conflict has shown up in real runs yet (a matter of query choice, not implementation)
