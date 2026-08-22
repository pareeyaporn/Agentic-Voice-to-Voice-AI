# Agentic Voice-to-Voice AI

A voice-to-voice, multi-agent shopping assistant: speak a product request, and the system interprets intent, retrieves from a private catalog (with optional live web comparison), and replies by voice with cited sources.

Built for ADSP 32028 — Applied Generative AI: Agents and Multimodal Intelligence.

## Getting Started

**Prerequisites:** Python 3.11+, Node/npm, an OpenAI API key (LLM + TTS), a Tavily API key (web search, free tier).

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in OPENAI_API_KEY, TAVILY_API_KEY, LLM_MODEL

# Terminal 1 -- backend (port 8500)
uvicorn main:app --app-dir webapp/backend --port 8500

# Terminal 2 -- frontend (port 5173, proxies /api/* to the backend)
cd webapp/frontend && npm install && npm run dev
```

Opens at `http://localhost:5173`. Mock-data mode is on by default ($0 cost) — toggle it off in Settings to run the real pipeline. The MCP server starts automatically; nothing else to run. See [webapp/README.md](webapp/README.md) for more detail.

The vector index is already committed, so no rebuild is needed. To rebuild, run notebooks `1.1` → `1.2` → `1.3`.

**Alternative UI:** a Streamlit app (`Code/5. User Interface/app.py`) is also available -- same pipeline, single-process setup, no separate frontend build:
```bash
streamlit run "Code/5. User Interface/app.py"
```
Opens at `http://localhost:8501`. Either UI satisfies the project's UI deliverable.

## Troubleshooting

**`ModuleNotFoundError` for a package in `requirements.txt`** -- usually the wrong Python interpreter (multiple Pythons installed). Check `which python3` before reinstalling.

**No mic/upload button in the React UI** -- expected while Mock-data mode is on (the default); toggle it off in Settings.

**"Tool error(s)... category filter not applied"** -- expected, not a bug. `category_top` is constant across the demo slice, so it can't narrow anything; see §2.4 in the task backlog.

**Missing API key errors** -- copy `.env.example` to `.env` and fill in the named key; mock mode needs none at all.

## Architecture

One LangGraph pipeline; every retrieval path (private catalog or live web) goes through a single MCP server exposing two tools:

```mermaid
graph TD
    A["🎤 User Voice Input"] -->|Audio File| B["ASR<br/>faster-whisper<br/>asr.py"]

    B -->|Transcript| C1["Streamlit UI<br/>app.py"]
    B -->|Transcript| FE["React UI<br/>App.jsx"]
    FE <-->|HTTP + streamed NDJSON| BE["FastAPI Backend<br/>main.py<br/>/api/transcribe, /api/query, /api/tts"]

    C1 -->|Display Query| D["LangGraph<br/>graph.py"]
    BE -->|Display Query| D
    D --> E["Router<br/>Intent + Constraints"]
    E -->|safety_flag set| S["Safe-refusal path"]
    E -->|safe, intent = out_of_scope| OOS["Out-of-scope path<br/>polite redirect"]
    E -->|safe, in-scope intent| F["Planner<br/>rag vs. web sourcing"]
    F --> R["Retriever<br/>Call MCP Tools per plan"]
    R -->|rag.search always| G["MCP SERVER<br/>mcp_server.py"]
    R -.->|web.search if plan.use_web| G
    G -->|rag.search| H["RAG Search<br/>rag_search_tool.py"]
    G -.->|web.search| I["Web Search<br/>web_search_tool.py (Tavily)"]
    H --> J["Chroma Vector DB"]
    I -.-> K["Tavily API"]
    J --> G
    K -.-> G
    G --> R
    R -->|Reconciled products| L["Answerer/Critic<br/>Synthesize + ground + cite"]
    S --> M1["Streamlit UI<br/>Display Results"]
    OOS --> M1
    L -->|Answer + Citations| M1
    S --> BE
    OOS --> BE
    L -->|Answer + Citations| BE
    M1 --> N["Comparison Table"]
    M1 --> O["Agent Step Log"]
    BE -->|streamed step log +<br/>comparison + citations| FE
    M1 -->|Answer Text| P["TTS<br/>tts.py"]
    BE -->|Answer Text| P
    P -->|Audio| Q["🔊 Playback"]
    FE -->|Audio| Q
    Q --> A

    style FE fill:#61DAFB,color:#000
    style BE fill:#009688,color:#fff
```

Two UI options, same pipeline underneath (`graph.py` doesn't know or care which one called it) -- Streamlit stays the reference UI, React+FastAPI is an alternative. Streamlit is one process calling `asr.py`/`graph.py`/`tts.py` in-process; React+FastAPI is two processes talking over HTTP, with `main.py` as a thin API layer over the exact same modules. See [webapp/README.md](webapp/README.md) for the React+FastAPI path.

See also [architecture_comparison.mermaid](Architecture/architecture_comparison.mermaid) (naive vs. MCP-routed design).

## Key Components

| Component | Role |
|---|---|
| **Orchestration (LangGraph)** | Router → Planner → Retriever → Answerer/Critic |
| **ASR** | Local `faster-whisper`, free, fragment-based |
| **Agentic RAG** | Hybrid vector + metadata search, Chroma (`products_home_kitchen` demo slice + `products_all` full catalog) |
| **MCP Server** | One server, two tools — `rag.search`, `web.search` (Tavily) — with caching + logging |
| **TTS** | OpenAI TTS, ≤15s answers, provider-swappable |
| **UI** | Streamlit (reference) — mic input, step log, comparison table, citations, Play-TTS. React + FastAPI (alternative) — voice-first orb, hands-free loop |
| **LLM** | Model-agnostic via env config (OpenAI, Anthropic, Gemini, Bedrock, open-weight) |

## Prompt Disclosure

Per the charter's requirement — a `prompts/` folder (or README section) containing the main system prompts, tool-call instructions, planner rubric, and any few-shot examples, showing how prompts map to nodes/tools:

| Requirement | Present | Where |
|---|---|---|
| Main system prompts | ✅ | [Code/6. Prompts & Documentation/](Code/6.%20Prompts%20%26%20Documentation/) — Router, Planner, Answerer/Critic |
| Tool-call instructions | ✅ | [planner_system_prompt.md](Code/6.%20Prompts%20%26%20Documentation/planner_system_prompt.md)'s "Call `web_search` when" / "Don't call it when" |
| Planner rubric | ✅ | Same file — that call/don't-call split *is* the rubric |
| Few-shot examples | ✅ | Every prompt file has an `## Examples` section (Router: 5 cases · Planner: 4 · Answerer: 2 fully worked) |
| Prompts mapped to nodes/tools | ✅ | Each prompt file states which node uses it (`**Used by:**`); each node's `.py` docstring names its own prompt file right back |

At runtime, every real LLM call (system prompt + input + output) is also logged live — visible in-app via each UI's "Prompt Disclosure" panel (`providers.py`'s `LLM_CALL_LOG`, `/api/prompt-log` in the webapp).

## Data

**[Amazon Product Dataset 2020](https://www.kaggle.com/datasets/promptcloud/amazon-product-dataset-2020)** (Kaggle, CC0). 10,002 products, 28 columns — but no rating/review/ingredients data, and `Brand Name`/`Asin`/`Sku` are 100% empty. Demo category: **`Home & Kitchen`** (706 rows, mostly kids' bedding/furniture/party supplies, not cookware).

Full schema, gaps, and licensing: [data_schema_and_licensing.md](Project%20Overview/data_schema_and_licensing.md).

## Repository Structure

```
Project/
├── Architecture/        # System diagrams (Mermaid) -- shared across Code/ sections
├── Code/                 # Implementation, numbered to match the task backlog
│   ├── 1. Data Pipeline & Indexing/     # exploration, cleaning, embedding, retrieval, eval
│   ├── 2. Agentic Orchestration/        # LangGraph nodes + graph.py
│   ├── 3. MCP Server & Tools/           # MCP server + rag.search/web.search
│   ├── 4. Speech (ASR + TTS)/           # asr.py, tts.py
│   ├── 5. User Interface/               # Streamlit app.py
│   └── 6. Prompts & Documentation/      # system prompts
├── Data/                 # Raw Kaggle download (see Data/README.md)
├── Project Overview/     # Proposal, related work, team structure, task backlog, data schema, RAG eval plan
├── webapp/               # Alternative UI: React + FastAPI (see webapp/README.md)
├── requirements.txt
├── .env.example
└── README.md
```

Each numbered `Code/` folder has its own README or module docstrings for detail. Two things worth knowing: `speech_config.py` (§4) is deliberately not named `config.py` (§5's UI imports both in one process, and same-named modules would collide); `2.1-2.6 graph and nodes.ipynb` is a frozen design record, not kept in sync with the live `.py` files.

## Team

4-person team, no separate Project Lead — see [team_structure_and_task_breakdown.md](Project%20Overview/team_structure_and_task_breakdown.md) for roles and [detailed_task_backlog.md](Project%20Overview/detailed_task_backlog.md) for the task list.

| Role | Owns |
|---|---|
| Orchestration Lead | LangGraph pipeline, prompts, conflict resolution |
| Data Engineer | Data pipeline, indexing, hybrid retrieval, RAG eval |
| Voice/Integration Engineer | ASR, TTS, MCP server, web-search tool |
| Frontend/UI Engineer | Streamlit app, README, demo/presentation |

## Milestones

| Checkpoint | Week | Deliverables |
|---|---|---|
| Checkpoint 1 | 6 | ✅ [One-page proposal](Project%20Overview/project_proposal.md) · ✅ [Data slice](Project%20Overview/data_schema_and_licensing.md) · ✅ [Ingestion notebook](Code/1.%20Data%20Pipeline%20%26%20Indexing/1.1%20explore%20data.ipynb) · ✅ [Related work](Project%20Overview/related_work_summary.md) |
| Checkpoint 2 | 8 | ✅ [Architecture diagram](Architecture/architecture_with_mcp.mermaid) (graph + MCP calls) · ✅ UI ([Streamlit](Code/5.%20User%20Interface/app.py) / [React](webapp/)) · ✅ [RAG eval plan](Project%20Overview/rag_eval_plan.md) · ✅ [MCP README](Code/3.%20MCP%20Server%20%26%20Tools/README.md) (schemas) |
| Final | 10 | ✅ Live demo (≤7 min) · ✅ Clean repo + this README · ✅ Build scripts ([index](Code/1.%20Data%20Pipeline%20%26%20Indexing/1.3%20build%20index.ipynb), [MCP server](Code/3.%20MCP%20Server%20%26%20Tools/mcp_server.py)) · ✅ Presentation |

## Status

🚧 §1-5 (Data, Orchestration, MCP, Speech, UI) implemented and tested, including performance/reliability (see [performance_reliability_report.md](Project%20Overview/performance_reliability_report.md)). Remaining: usability testing with real external users (needs people outside the team).
