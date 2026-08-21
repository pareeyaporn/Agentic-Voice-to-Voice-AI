"""
FastAPI backend for the React webapp (webapp/frontend). Thin HTTP layer over
the exact same modules the Streamlit app (§5) uses -- graph.py (§2), asr.py/
tts.py (§4), ui_common.py's mock data -- no logic is re-derived here.

Async model: FastAPI runs one event loop, so mcp_client.py's persistent MCP
session works natively -- same one-loop/many-tasks pattern async_runtime.py
built for Streamlit, minus the background thread. First real query spawns
the MCP server subprocess; it's reused for the process's lifetime.

The step log streams as NDJSON (one JSON object per line) from a plain POST
-- not SSE, which the fetch() API can't POST to without a polyfill. The
frontend reads the body incrementally and renders each step as it lands.

Run: .venv/bin/uvicorn main:app --app-dir webapp/backend --port 8500
"""

import asyncio
import json
import os
import sys
import tempfile

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_BACKEND_DIR))
for _sub in ("2. Agentic Orchestration", "4. Speech (ASR + TTS)", "5. User Interface"):
    sys.path.insert(0, os.path.join(_REPO_ROOT, "Code", _sub))

import config as orch_config  # noqa: E402
import graph as graph_mod  # noqa: E402
import mcp_client  # noqa: E402
import providers  # noqa: E402  -- LLM_CALL_LOG, for the Prompt Disclosure panel
import speech_config  # noqa: E402
from state import EMPTY_STATE  # noqa: E402
from ui_common import MOCK_EXAMPLES, STEP_SUMMARIES, build_context_note  # noqa: E402

import asr  # noqa: E402
import tts  # noqa: E402

MOCK_STEP_DELAY_SECONDS = 0.4  # replayed steps land one by one, like the real graph


app = FastAPI(title="Agentic Voice-to-Voice Shopping Assistant API")

# Vite's dev server is a different origin; the built frontend (served by any
# static host) may be too. Local demo only -- not hardened for deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def _shutdown() -> None:
    await mcp_client.close()  # best-effort, see mcp_client.close()'s docstring


class QueryRequest(BaseModel):
    query: str
    mock: bool = True
    # Small memory feature (see ui_common.build_context_note): the client holds
    # its own last-turn state (React's `history`) and sends it back explicitly --
    # the backend is otherwise stateless per-request, no server-side session.
    last_query: str | None = None
    last_answer: str | None = None


class TTSRequest(BaseModel):
    text: str


@app.get("/api/config")
def get_config() -> dict:
    return {
        "llm_provider": orch_config.LLM_PROVIDER,
        "llm_model": orch_config.LLM_MODEL or None,
        "llm_configured": bool(orch_config.LLM_MODEL and os.environ.get("OPENAI_API_KEY")),
        "asr": f"{speech_config.ASR_PROVIDER} / {speech_config.ASR_MODEL_SIZE}",
        "tts": f"{speech_config.TTS_PROVIDER} / {speech_config.TTS_MODEL}",
        "mock_examples": list(MOCK_EXAMPLES.keys()),
    }


@app.get("/api/prompt-log")
def get_prompt_log() -> list:
    """Prompt Disclosure: every real LLM call this process has made."""
    return [
        {
            "node": call["node"],
            "system_prompt_chars": call["system_prompt_chars"],
            "input": call["input"][:200],
            "output": str(call["output"])[:200],
        }
        for call in providers.LLM_CALL_LOG
    ]


@app.post("/api/transcribe")
def transcribe(file: UploadFile) -> dict:
    """Sync endpoint on purpose: FastAPI runs it in the threadpool, so the
    CPU-bound faster-whisper call never blocks the event loop (and with it
    the streaming /api/query responses)."""
    suffix = os.path.splitext(file.filename or "")[-1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(file.file.read())
        path = f.name
    try:
        result = asr.transcribe(path)
    except asr.ASRError as e:
        raise HTTPException(status_code=422, detail=e.message)
    finally:
        os.unlink(path)
    return {"text": result.text, "language": result.language}


def _final_payload(products, citations, final_answer, errors, query) -> dict:
    # `query` is the Router's rewritten, cleaned-up search query (state["query"],
    # §2.2) -- not the raw transcript the user typed/spoke. The frontend's
    # follow-up chips template onto this; templating onto the raw transcript
    # instead produced broken chips like "cheapest Can you help me find a
    # lunch box under $15?" for any full-sentence query (found via real UI
    # testing, not a mocked case).
    return {
        "type": "final",
        "products": products,
        "citations": citations,
        "final_answer": final_answer,
        "errors": errors,
        "query": query,
    }


async def _stream_mock(query: str):
    example = MOCK_EXAMPLES.get(query)
    if example is None:
        yield json.dumps({"type": "error",
                          "message": "No mock example for that exact text -- pick one from the list."}) + "\n"
        return
    for node_name, summary in example["step_log"]:
        yield json.dumps({"type": "step", "node": node_name, "summary": summary}) + "\n"
        await asyncio.sleep(MOCK_STEP_DELAY_SECONDS)
    # Mock examples don't store a separately-cleaned query -- their dict key
    # already reads as a short phrase, so it doubles as one here.
    yield json.dumps(_final_payload(
        example["products"], example["citations"], example["final_answer"], example["errors"], query
    )) + "\n"


async def _stream_real(query: str, context_note: str | None):
    state = dict(EMPTY_STATE)
    state["transcript"] = query
    state["context_note"] = context_note
    final_state = state
    try:
        async for chunk in graph_mod.graph.astream(state, stream_mode="updates"):
            for node_name, delta in chunk.items():
                final_state = delta
                summarize = STEP_SUMMARIES.get(node_name)
                summary = summarize(delta) if summarize else f"{node_name} ran"
                yield json.dumps({"type": "step", "node": node_name, "summary": summary}) + "\n"
    except Exception as e:  # graph/MCP/LLM failure -- surfaced to the client, not swallowed
        yield json.dumps({"type": "error", "message": f"Something went wrong running the assistant: {e}"}) + "\n"
        return
    yield json.dumps(_final_payload(
        final_state["tool_results"]["products"],
        final_state["citations"],
        final_state["final_answer"],
        final_state["tool_results"]["errors"],
        final_state.get("query") or query,  # router-cleaned query; raw transcript as a defensive fallback
    )) + "\n"


@app.post("/api/query")
async def run_query(req: QueryRequest) -> StreamingResponse:
    if req.mock:
        stream = _stream_mock(req.query)
    else:
        context_note = build_context_note(req.last_query, req.last_answer)
        stream = _stream_real(req.query.strip(), context_note)
    return StreamingResponse(stream, media_type="application/x-ndjson")


@app.post("/api/tts")
def synthesize(req: TTSRequest) -> Response:
    """Sync on purpose, same threadpool reasoning as /api/transcribe."""
    try:
        result = tts.synthesize(req.text)
    except tts.TTSError as e:
        raise HTTPException(status_code=503, detail=e.message)
    return Response(content=result.audio_bytes, media_type="audio/wav")
