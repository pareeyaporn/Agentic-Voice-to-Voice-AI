"""
Async runtime bridge for the Streamlit UI (§5). Streamlit re-runs app.py's
top level on every rerun, but graph.py is async and holds a persistent MCP
`ClientSession` (§2.4) for the life of the process. `asyncio.run()` per
rerun would open and tear down a new event loop each time, invalidating
that session and paying its startup cost again on every query.

Fixed with one background thread running one event loop for the process's
lifetime; every rerun submits its coroutine to that same loop via
`asyncio.run_coroutine_threadsafe()` and blocks for the result. The MCP
session is created once and reused across calls -- never closed from a
different task, which is what breaks anyio's cancel scope (§2.4).

No `import streamlit` here by design, so this bridge is testable with plain
Python independent of the UI.
"""

import asyncio
import threading
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop = None
_thread: threading.Thread = None
_lock = threading.Lock()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop, _thread
    if _loop is not None:
        return _loop
    with _lock:
        if _loop is not None:  # re-check inside the lock -- avoid a double-start race
            return _loop
        loop = asyncio.new_event_loop()

        def _run_forever():
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(target=_run_forever, daemon=True, name="graph-event-loop")
        thread.start()
        _loop = loop
        _thread = thread
        return _loop


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Submits `coro` to the persistent background loop and blocks for its
    result. Safe across reruns: each call is a new asyncio Task, but all run
    on the same loop, and this module never closes the MCP session (only
    opening/closing a cancel scope from a different task is unsafe)."""
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()
