# Performance & Reliability Report (§4.3)

Real numbers only, generated from [4.3 performance and reliability.ipynb](../Code/4.%20Speech%20%28ASR%20%2B%20TTS%29/4.3%20performance%20and%20reliability.ipynb) -- nothing here is estimated.

## End-to-end latency

Full pipeline (ASR -> Router -> Planner -> Retriever -> Answerer -> TTS), 2 representative queries:

| Query | ASR | Router | Planner | Retriever | Answerer | Graph total | TTS | **Total** |
|---|---|---|---|---|---|---|---|---|
| "insulated lunch box for kids under twenty dollars" | 1.57s | 1.51s | 2.90s | 6.56s | 1.45s | 12.42s | 3.17s | **17.16s** |
| "what's the current price of an insulated lunch box" | 1.03s | 1.55s | 1.75s | 3.34s | 1.75s | 8.39s | 3.14s | **12.56s** |

Retriever is consistently the largest single slice (real MCP round-trips: `rag.search` always, `web.search` when Planner calls for it). Both totals are well within a live-demo attention span; no single node is a runaway outlier.

## Timeouts

Every real network call previously ran on its SDK's own default (OpenAI's is 600s -- confirmed via `openai._base_client.DEFAULT_TIMEOUT`), which could leave the UI's spinner running for up to 10 minutes on a hung call. Fixed with explicit bounds per call site:

| Call site | Timeout | Why |
|---|---|---|
| LLM calls (`providers.py`) | 30s, 1 retry | Fail fast for a live demo rather than the SDK's default 2 retries |
| TTS (`tts.py`) | 30s, 1 retry | Same reasoning |
| `web.search` (`web_search_tool.py`) | 15s per attempt, 3 attempts | `tavily-python`'s own default is 60s x 3 retries = 180s worst case; 15s keeps a normal response comfortably while bounding the worst case |
| UI outer bound (`async_runtime.py`) | 120s | Defense-in-depth only -- `future.result(timeout=...)` bounds the caller's wait but doesn't cancel the coroutine, so this is a backstop for something not respecting its own bound, not the primary defense |

`app.py` catches `TimeoutError` specifically with a clear user-facing message ("taking longer than expected...") rather than a generic error.

## Stress test: 6 back-to-back queries

Fired with no delay between them, isolating session/cache/backoff behavior (not ASR/TTS-wrapped):

- **Total wall time: 38.93s** for 6 real `graph.ainvoke()` calls.
- **MCP session persistence confirmed:** 1 distinct session object reused across all 6 calls -- the server subprocess is not respawned per query.
- **Tavily cache confirmed engaging on a real repeat:** query 6 exactly repeated query 5's text. Query 5 (first call): 8.46s. Query 6 (cached): 5.35s -- faster as expected, not just passing in the mocked unit test.
- **5 of 6 queries logged a `rag.search` error.** Verified for real, not assumed: every one is the documented "category filter not applied" warning (`category_top` is constant within `products_home_kitchen`, §2.4 finding) -- not a genuine failure. Most of the 6 queries mention product-type language the Router extracts as a `category` constraint, which reliably triggers this (expected, informational) warning.

## What this doesn't cover

- Concurrent/multi-user load -- every measurement above is one query at a time. The React+FastAPI webapp (§5.4) can receive concurrent requests, and `mcp_client.get_session()` has no lock against a concurrent first-call race; not exercised here.
- Network-degraded conditions (slow/flaky connection) -- the timeouts above are sized for a *hung* call, not tested against a genuinely slow-but-alive one.
