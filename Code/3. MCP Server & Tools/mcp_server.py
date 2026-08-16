"""
MCP server (§3.1). Long-running process, so `.py`, not a notebook.

One server, two tools: `rag.search` (§3.2, wraps §1.4/§2.4's search()) and
`web.search` (§3.3, Tavily). Retriever (§2.4) calls both through this
server via a persistent MCP client (Code/2. Agentic Orchestration/mcp_client.py),
spawned once, not per query.

Transport: stdio -- this server is a local subprocess of the LangGraph app,
not a shared network service, so stdio needs no port/network config (same
pattern Claude Desktop uses for local MCP servers).

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
    """Wraps §2.4's retriever.py search() (§3.2). Output: {products: [{doc_id,
    title, price, price_per_unit, price_unit, brand, category_top, url,
    distance}], warnings: [...]}. `category` is accepted but not applied --
    see rag_search_tool.py's docstring. `@logged_tool` (§3.4) logs every
    call and normalizes exceptions into a typed `ToolError`."""
    return rag_search_impl(
        query, top_k=top_k, budget_min=budget_min, budget_max=budget_max, category=category, brand=brand
    )


@mcp_server.tool(name="web.search", description="Search the live web for current pricing/availability (Tavily).")
@logged_tool("web.search")
def web_search(query: str, top_k: int = 5) -> dict:
    """Wraps web_search_tool.py's Tavily integration (§3.3). Output:
    {results: [{title, url, snippet, price?, availability?}], cache_hit}.
    price/availability are best-effort regex extraction from the snippet
    text, not structured Tavily fields -- low-confidence, stated as such."""
    return web_search_impl(query, top_k=top_k)


if __name__ == "__main__":
    mcp_server.run(transport="stdio")
