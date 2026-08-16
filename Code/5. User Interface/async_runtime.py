"""
Async runtime bridge for the Streamlit UI (§5). Streamlit is a synchronous
framework that re-executes app.py's top-level code on every rerun (every
button click, every mic recording) -- but `graph.py` is async (§2.4's
Retriever swap: `await graph.ainvoke(...)`, holding a persistent MCP
`ClientSession` in `mcp_client.py` for the life of the process, not
reconnected per query).

`asyncio.run()` per rerun would defeat that: it opens a brand-new event loop
and tears it down when the call returns, so the MCP session's cancel scope
(anyio ties it to the task that opened it, per §2.4's own documented finding)
would be invalidated on the very next rerun -- silently paying the ~0.2s
per-query startup cost again on every single query, exactly the cost the
persistent-session swap was built to avoid.

Fixed the same way any sync framework bridges to a long-lived async resource:
one background thread runs one event loop for the entire process's lifetime;
every rerun submits its coroutine to that same loop via
`asyncio.run_coroutine_threadsafe()` and blocks for the result. The MCP
session gets created once, in one task, on that one loop, and every
subsequent call (including from later, unrelated Streamlit reruns) reuses it
-- never re-entered or closed from a different task, which is the specific
case §2.4 found breaks anyio's cancel scope.

Not Streamlit-specific by design -- this module has zero `import streamlit`,
so it can be (and is, see the test at the bottom) verified directly with
plain Python before ever being wired into the UI.
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
    """Submits `coro` to the one persistent background loop and blocks the
    calling (sync) thread for its result. Safe to call repeatedly across
    Streamlit reruns -- each call is a new asyncio Task, but all of them run
    on the same loop, which is what keeps the MCP session's cancel scope
    valid (usage from a different task on the *same* loop is fine; only
    entering/exiting -- i.e. opening/closing -- a cancel scope from a
    different task is the documented problem, and this module never closes
    the session)."""
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()
