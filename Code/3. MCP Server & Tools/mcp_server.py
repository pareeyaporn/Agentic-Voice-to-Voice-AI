"""
MCP server skeleton (§3.1). Long-running process, so `.py` per the file-format
convention (reason (a): not a notebook-appropriate one-shot execution).

One server, two tools -- `rag.search` and `web.search` -- per the project's
architecture (Architecture/architecture_with_mcp.mermaid). Both real:
`rag.search` (§3.2, rag_search_tool.py, wraps §1.4/§2.4's search()) and
`web.search` (§3.3, web_search_tool.py, Tavily). Retriever (§2.4) calls both
through this server for real now, via a persistent MCP client
(Code/2. Agentic Orchestration/mcp_client.py) -- spawned once, not per query.

Transport: stdio, not streamable HTTP/SSE. This server is spawned as a local
subprocess by the same process running the LangGraph app (Retriever node),
not a shared network service multiple independent clients connect to over a
network -- stdio is the standard pattern for that (same model Claude
Desktop uses for local MCP servers), with no port/network config needed.
Revisit if this project ever needs the server reachable from a separate
process/machine (SSE/streamable-http remain available via `.run(transport=...)`
without restructuring the tools themselves).

Run standalone: `python mcp_server.py`
"""

from typing import Optional

from mcp.server.mcpserver import MCPServer

from rag_search_tool import rag_search_impl
from tool_logging import logged_tool
from web_search_tool import web_search_impl

mcp_server = MCPServer(name="agentic-voice-shopping-mcp", version="0.1.0")


@mcp_server.tool(name="rag.search", description="Search the private product catalog (Home & Kitchen demo slice).")
@logged_tool("rag.search")
def rag_search(
    query: str,
    top_k: int = 5,
    budget_min: Optional[float] = None,
    budget_max: Optional[float] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
) -> dict:
    """Real (§3.2): wraps §2.4's retriever.py search(), which itself wraps
    §1.4's search() logic -- not re-derived a third time. Output: {products:
    [{doc_id, title, price, price_per_unit, price_unit, brand, category_top,
    url, distance}], warnings: [...]}. `category` is accepted but not
    applied -- see rag_search_tool.py's module docstring for why. Wrapped in
    `@logged_tool` (§3.4): every call's request/response/timestamp/source
    URLs get logged (secrets scrubbed), and any raised exception gets
    normalized into a typed `ToolError`."""
    return rag_search_impl(
        query, top_k=top_k, budget_min=budget_min, budget_max=budget_max, category=category, brand=brand
    )


@mcp_server.tool(name="web.search", description="Search the live web for current pricing/availability (Tavily).")
@logged_tool("web.search")
def web_search(query: str, top_k: int = 5) -> dict:
    """Real (§3.3): wraps web_search_tool.py's Tavily integration. Output:
    {results: [{title, url, snippet, price?, availability?}], cache_hit}.
    price/availability are best-effort regex/keyword extraction from the
    snippet text, not structured fields Tavily provides -- low-confidence,
    same honesty posture as §1.2's brand extraction. Wrapped in
    `@logged_tool` (§3.4), same as rag.search."""
    return web_search_impl(query, top_k=top_k)


if __name__ == "__main__":
    mcp_server.run(transport="stdio")
