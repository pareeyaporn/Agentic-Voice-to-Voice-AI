"""
Persistent MCP client (§2.4). Spawns `Code/3. MCP Server & Tools/mcp_server.py`
once and keeps a long-lived ClientSession open for the process's lifetime
instead of reconnecting per query -- ~0.2s first call (model load), ~0.01s
after, on the same session.

Uses AsyncExitStack (stdlib) to hold the stdio_client + ClientSession async
context managers open beyond a single `async with` block.
"""

import json
import os
import re
import sys
from contextlib import AsyncExitStack
from typing import Any, Optional

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
MCP_SERVER_PATH = os.path.join(MODULE_DIR, "..", "3. MCP Server & Tools", "mcp_server.py")

_exit_stack: Optional[AsyncExitStack] = None
_session: Optional[ClientSession] = None

_ERROR_TYPE_RE = re.compile(r"\[(\w+)\]")


class ToolCallError(Exception):
    """Client-side reconstruction of the server's typed ToolError.
    error_type is parsed from MCP's text-only error format
    ("Error executing tool <name>: [error_type] message")."""

    def __init__(self, error_type: str, message: str):
        self.error_type = error_type
        self.message = message
        super().__init__(f"[{error_type}] {message}")


async def get_session() -> ClientSession:
    """Starts the server subprocess + session on first call, reuses it on
    every call after. Not re-spawned per query."""
    global _exit_stack, _session
    if _session is not None:
        return _session

    stack = AsyncExitStack()
    params = StdioServerParameters(command=sys.executable, args=[MCP_SERVER_PATH])
    read, write = await stack.enter_async_context(stdio_client(params))
    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()

    _exit_stack = stack
    _session = session
    return session


async def close() -> None:
    """Shuts down the persistent subprocess/session. Best-effort: anyio ties
    the underlying task group to whichever asyncio Task first opened the
    session, and LangGraph runs async nodes in its own internally-spawned
    task -- so calling close() from elsewhere often raises anyio's "exit
    cancel scope in a different task" RuntimeError. Caught and logged here
    rather than crashing the caller; doesn't affect correctness since the
    subprocess dies with the parent process regardless, only how graceful
    the shutdown looks."""
    global _exit_stack, _session
    if _exit_stack is not None:
        try:
            await _exit_stack.aclose()
        except RuntimeError as e:
            print(f"mcp_client.close(): best-effort cleanup hit a known anyio cross-task limitation ({e}); "
                  f"the server subprocess will still exit with the parent process.")
    _exit_stack = None
    _session = None


async def call_tool(name: str, arguments: dict[str, Any]) -> dict:
    """Calls an MCP tool through the persistent session. Raises
    ToolCallError (typed, not just text) on failure rather than making the
    caller unwrap a CallToolResult manually."""
    session = await get_session()
    result = await session.call_tool(name, arguments)
    if result.is_error:
        text = result.content[0].text if result.content else "unknown error"
        m = _ERROR_TYPE_RE.search(text)
        error_type = m.group(1) if m else "unknown"
        raise ToolCallError(error_type, text)
    return json.loads(result.content[0].text)
