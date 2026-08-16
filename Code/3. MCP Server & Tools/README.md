# MCP Server & Tools

Covers task backlog §3 (CP2 deliverable: "MCP README, schemas"). One MCP server, two
tools, per the assignment's Two-Tool MCP Server Requirement: *"Safely call external
services and unify private retrieval under the same protocol."*

## Running the server standalone

```bash
cd "Code/3. MCP Server & Tools"
python mcp_server.py
```

Requires `.env` at the repo root with `OPENAI_API_KEY` (unused by this server directly,
but `retriever.py` — imported by `rag_search_tool.py` — asserts it's present, since it's
part of the shared `config.py` this module reuses) and `TAVILY_API_KEY`. The process
waits on stdin for MCP protocol messages — it's not meant to be run and watched
interactively; connect a real MCP client (see below) or a test notebook to talk to it.

## Transport: stdio

Decided over streamable HTTP/SSE. This server is spawned as a local subprocess by
whatever process runs the LangGraph app — not a shared network service multiple
independent clients connect to over a network. stdio needs no port/network
configuration and is the standard pattern for a locally-spawned MCP server (the same
model Claude Desktop uses for its local MCP servers). SSE/streamable-http remain
available later via `mcp_server.run(transport=...)` without restructuring either tool,
if this project ever needs the server reachable from a separate process/machine.

## Tools

### `rag.search`

Searches the private product catalog (`products_home_kitchen`, the Home & Kitchen demo
slice). Wraps [`Code/2. Agentic Orchestration/retriever.py`](../2.%20Agentic%20Orchestration/retriever.py)'s
`search()` — itself ported from §1.4 — rather than re-deriving retrieval logic.

**Input schema:**

| Field | Type | Default | Notes |
|---|---|---|---|
| `query` | string | *(required)* | |
| `top_k` | integer | `5` | |
| `budget_min` | number \| null | `null` | |
| `budget_max` | number \| null | `null` | |
| `category` | string \| null | `null` | **Accepted but not applied.** `category_top` is constant across `products_home_kitchen` (it's the field used to carve out this demo slice, §1.1/§1.2), so filtering by it here is structurally meaningless. Passing it returns a `warnings` entry explaining why, not a silent no-op. |
| `brand` | string \| null | `null` | |

**Output:** `{"products": [...], "warnings": [...]}`. Each product:
`doc_id, title, price, price_per_unit, price_unit, brand, category_top, url, distance`.
(`features` was in an earlier draft of this schema but was dropped — it was never stored
as retrievable Chroma metadata, §1.3 only used it to build the embedding text.)

### `web.search`

Searches the live web via [Tavily](https://tavily.com) (free tier, 1,000 credits/month,
no credit card). Implementation:
[`web_search_tool.py`](web_search_tool.py).

**Input schema:** `query` (string, required), `top_k` (integer, default `5`).

**Output:** `{"results": [...], "cache_hit": bool}`. Each result:
`title, url, snippet, price, availability`. `price`/`availability` are **best-effort,
low-confidence** — regex/keyword-extracted from the snippet text, since Tavily provides
no structured fields for either (same honesty posture as §1.2's brand-extraction regex:
real, tested, openly imperfect, not fabricated).

**Caching:** in-memory, keyed by `(query, top_k)`, 120s TTL (middle of the brief's
stated 60–300s range).

**Rate limiting / backoff:** retries only on transient errors (`TimeoutError`,
`UsageLimitExceededError`) — not on client errors like a bad API key, where retrying
can't help. 3 attempts, exponential backoff. Exhausting retries raises a typed
`ToolError` (see below), not the raw Tavily exception.

**Domain allowlist:** results restricted to `amazon.com, walmart.com, target.com,
ebay.com, bestbuy.com` via Tavily's own `include_domains` parameter. Robots.txt/ToS
compliance is handled server-side by Tavily's crawling infrastructure — the original
reason Tavily was picked over raw scraping — not re-implemented here.

## Cross-cutting (§3.4)

Both tools are wrapped in [`tool_logging.py`](tool_logging.py)'s `@logged_tool`
decorator (applied via ordinary Python decorator stacking under `@mcp_server.tool`, not
the MCP SDK's lower-level `ServerMiddleware` protocol — simpler, and covers exactly
what's needed here without taking on that API's wire-protocol-level surface).

- **Structured logging:** every call's request, response (or error), timestamp, and any
  `source_urls` in the result land in `tool_logging.TOOL_CALL_LOG`.
- **Secret scrubbing:** logged data is scrubbed both **by value** (redacts whatever the
  currently-configured `OPENAI_API_KEY`/`TAVILY_API_KEY`/etc. actually is, if it appears
  verbatim) and **by shape** (redacts anything matching common API-key patterns, e.g.
  `sk-...`, `tvly-...`, even a key never configured here) — so a leak from an unexpected
  source (e.g. a third-party HTTP client dumping a header into an error message) still
  gets caught.
- **Typed error contract:** any exception raised inside a tool gets normalized into a
  `ToolError(error_type, message)`. `error_type` is machine-branchable (`"timeout"`,
  `"rate_limited"`, `"internal_error"`, ...) — the actual requirement was "tools return
  typed errors the Retriever node can branch on," and `str(ToolError)` is
  `"[error_type] message"`, so the type survives even through MCP's text-only
  error-result format.

## Testing

Each subsection has its own notebook (real subprocess + real stdio transport, not an
in-process shortcut — exercises the actual integration point a real client uses):

- [`3.1 server skeleton smoke test.ipynb`](3.1%20server%20skeleton%20smoke%20test.ipynb) — tool discovery, schemas, server liveness
- [`3.2 rag search tool test.ipynb`](3.2%20rag%20search%20tool%20test.ipynb) — real calls against the real committed index (no synthetic fixture — it's already small/fast/committed)
- [`3.3 web search tool test.ipynb`](3.3%20web%20search%20tool%20test.ipynb) — 1 real Tavily call + mocked caching/backoff/allowlist tests (mocking is the right call *there* specifically — you can't reliably force a real rate-limit response on demand)
- [`3.4 cross-cutting test.ipynb`](3.4%20cross-cutting%20test.ipynb) — logging, scrubbing, typed errors

## Wired into the live graph

The Retriever node (§2.4, [`Code/2. Agentic Orchestration/retriever.py`](../2.%20Agentic%20Orchestration/retriever.py))
calls both tools through this server for real, via a persistent MCP client
([`Code/2. Agentic Orchestration/mcp_client.py`](../2.%20Agentic%20Orchestration/mcp_client.py))
— the server is spawned once (not per query, verified for real: first call ~0.2s
including the embedding-model load, every call after ~0.01s on the same session) and
reused across queries, and `retriever_node` is `async def` accordingly. `search()`
itself stays in `retriever.py` — it's still the real implementation
[`rag_search_tool.py`](rag_search_tool.py) imports — Retriever just no longer calls it
directly.

**Known limitation, stated not hidden:** the persistent MCP client's `close()` is
best-effort. anyio ties a session's task group to whichever asyncio Task first opened
it, and LangGraph runs async nodes in its own internally-spawned task, so closing from
outside that task raises an anyio error — caught and logged rather than left to crash
the caller. This only affects how *graceful* shutdown looks (the server subprocess dies
with the parent process regardless), not correctness.
