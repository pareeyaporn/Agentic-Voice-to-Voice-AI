"""
Cross-cutting concerns for MCP tool calls (§3.4): structured logging, secret
scrubbing, and a typed error contract. Applied via the `@logged_tool`
decorator in mcp_server.py -- simpler than the SDK's low-level
`ServerMiddleware` protocol, and covers exactly what's needed here.
"""

import functools
import os
import re
import time
from typing import Any, Callable

TOOL_CALL_LOG: list[dict] = []

# Redact by value (currently-configured secrets) AND by shape (common API
# key prefixes), so a secret is still caught even from an unexpected source.
_SECRET_ENV_VARS = ("OPENAI_API_KEY", "TAVILY_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY")
_SECRET_SHAPE_RE = re.compile(r"\b(sk-[A-Za-z0-9_-]{10,}|tvly-[A-Za-z0-9_-]{10,})\b")


def scrub_secrets(text: str) -> str:
    if not isinstance(text, str):
        return text
    for var in _SECRET_ENV_VARS:
        val = os.environ.get(var)
        if val:
            text = text.replace(val, "***REDACTED***")
    return _SECRET_SHAPE_RE.sub("***REDACTED***", text)


def _scrub_recursive(obj: Any) -> Any:
    if isinstance(obj, str):
        return scrub_secrets(obj)
    if isinstance(obj, dict):
        return {k: _scrub_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub_recursive(v) for v in obj]
    return obj


def _extract_source_urls(response: Any) -> list[str]:
    """Generic: works for both tools' shapes (rag.search's `products`, list
    of dicts with `url`; web.search's `results`, same shape)."""
    if not isinstance(response, dict):
        return []
    items = response.get("products") or response.get("results") or []
    return [item["url"] for item in items if isinstance(item, dict) and item.get("url")]


class ToolError(Exception):
    """Typed error contract: `error_type` is machine-branchable, `message`
    is human-readable. str(ToolError) is "[error_type] message" so the type
    survives MCP's text-only error-result format."""

    def __init__(self, error_type: str, message: str):
        self.error_type = error_type
        self.message = message
        super().__init__(f"[{error_type}] {message}")


def logged_tool(tool_name: str) -> Callable:
    """Logs request/response/timestamp/source_urls for every call, scrubs
    secrets before logging, and normalizes any exception into a typed
    ToolError before it propagates."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            entry = {
                "tool": tool_name,
                "timestamp": time.time(),
                "request": _scrub_recursive(dict(kwargs)),
            }
            try:
                response = fn(*args, **kwargs)
                entry["response"] = _scrub_recursive(response)
                entry["source_urls"] = _extract_source_urls(response)
                entry["error_type"] = None
                TOOL_CALL_LOG.append(entry)
                return response
            except ToolError as e:
                entry["response"] = None
                entry["error_type"] = e.error_type
                entry["error_message"] = scrub_secrets(e.message)
                TOOL_CALL_LOG.append(entry)
                raise
            except Exception as e:
                entry["response"] = None
                entry["error_type"] = "internal_error"
                entry["error_message"] = scrub_secrets(str(e))
                TOOL_CALL_LOG.append(entry)
                raise ToolError("internal_error", str(e)) from e

        return wrapper

    return decorator
