# React + FastAPI Webapp (alternative UI)

An alternative frontend to the Streamlit app (`Code/5. User Interface/app.py`) —
same pipeline, same mock data (shared via `Code/5. User Interface/ui_common.py`),
different presentation layer. The Streamlit app remains the reference UI; either
one satisfies the project's UI deliverable.

```
webapp/
  backend/   FastAPI — thin HTTP layer over graph.py / asr.py / tts.py
  frontend/  React (Vite) — mic capture, streamed step log, comparison table, TTS playback
```

## Run

Two processes, from the repo root (same `pip install -r requirements.txt` as the root README's Getting Started — no separate virtualenv):

```bash
# 1. Backend (port 8500)
uvicorn main:app --app-dir webapp/backend --port 8500

# 2. Frontend dev server (port 5173, proxies /api/* to the backend)
cd webapp/frontend && npm install && npm run dev
```

Open http://localhost:5173. Mock-data mode is on by default and needs no `.env`;
for the real pipeline, fill in `.env` (see `.env.example`) before starting the backend.

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/config` | GET | Provider info + mock example queries |
| `/api/transcribe` | POST (multipart) | Audio file → transcript (local faster-whisper) |
| `/api/query` | POST (JSON `{query, mock, last_query?, last_answer?}`) | Runs the LangGraph pipeline; streams NDJSON: `{type:"step"}` per node, then `{type:"final"}` |
| `/api/tts` | POST (JSON `{text}`) | Answer text → WAV bytes (OpenAI TTS) |
| `/api/prompt-log` | GET | Prompt Disclosure: every real LLM call this session |

The step log streams over a plain POST as NDJSON lines (not SSE — `fetch()`
can't POST to an EventSource), so steps render live as each graph node finishes.

**Small memory feature:** `last_query`/`last_answer` (optional) carry only the
immediately preceding turn -- not a full conversation history -- so the Router
can resolve a vague follow-up ("what about something cheaper") against real
prior context. The frontend sends back its own in-memory session history
(never localStorage); the backend stays stateless per-request otherwise. See
`Code/2. Agentic Orchestration/state.py`'s `context_note` field.
