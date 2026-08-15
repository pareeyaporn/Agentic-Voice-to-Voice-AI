# Agentic Voice-to-Voice AI

A voice-to-voice, multi-agent shopping assistant for e-commerce. Users speak a natural-language product request (e.g. *"I need an eco-friendly stainless-steel cleaner under $15"*), and the system interprets intent, plans a retrieval strategy, grounds its answer in a private product catalog (with optional live web comparison), and replies by voice with cited sources.

Built for ADSP 32028 — Applied Generative AI: Agents and Multimodal Intelligence.

## Project Context

Traditional chatbots struggle to interpret spoken intent, search private catalogs, check live availability, and answer clearly — especially hands-free. This project delivers an assistant that:

- Enables voice-to-voice queries for intuitive product search & comparison
- Uses a multi-agent flow (intent → plan → retrieve/tools → summarize) orchestrated with **LangGraph**
- Provides context-aware, grounded recommendations with citations to both private data and any live sources retrieved

## Architecture

Orchestration is a LangGraph pipeline. Every retrieval path — private catalog or live web — is routed through a single MCP server exposing two tools, never called directly:

```mermaid
graph TD
    A["🎤 User Voice Input"] -->|Audio File| B["ASR<br/>Whisper<br/>asr.py"]

    B -->|Transcript| C["Streamlit UI<br/>main.py"]

    C -->|Display Query| D["LangGraph<br/>Orchestration<br/>graph.py"]

    D --> E["Router Node<br/>Intent Classifier"]
    E -->|Parse constraints<br/>budget, material, etc| F["Retriever Node<br/>Call MCP Tools"]

    F -->|Tool Call:<br/>rag.search| G["MCP SERVER<br/>mcp_server.py<br/><br/>Tool Discovery<br/>+ Routing"]

    F -->|Tool Call:<br/>web.search| G

    G -->|Route to implementation<br/>rag.search| H["RAG Search<br/>tools/rag_search.py"]
    G -->|Route to implementation<br/>web.search| I["Web Search<br/>tools/web_search.py"]

    H -->|Return products| J["Chroma Vector DB<br/>data_index.py"]
    I -->|Return results| K["Web API<br/>Brave/Serper"]

    J -->|Results| G
    K -->|Results| G

    G -->|Structured Results| F

    F -->|Products List| L["Answerer Node<br/>Synthesize Response"]

    L -->|Answer + Citations| M["Streamlit UI<br/>Display Results"]

    M -->|Show Table| N["Comparison Table<br/>Title, Price, Rating"]
    M -->|Show Log| O["Agent Log<br/>What happened<br/>at each node"]

    M -->|Answer Text| P["TTS<br/>OpenAI/ElevenLabs<br/>tts.py"]
    P -->|Audio Output| Q["🔊 Speaker/Audio Player"]

    Q -->|Play| A
```

The [Architecture](Architecture/) folder also has [architecture_comparison.mermaid](Architecture/architecture_comparison.mermaid), which contrasts a naive direct-function-call design against the required MCP-routed design — useful context for why the pipeline is shaped this way.

## Key Components

| Component | Role |
|---|---|
| **Agentic Orchestration (LangGraph)** | Router (intent classifier) → Planner (source/field selection) → Retriever (agentic RAG via MCP) → Answerer/Critic (grounded synthesis + safety) |
| **ASR** | Speech-to-text via Whisper (or comparable); fragment-based (record → transcribe) or streaming |
| **Agentic RAG** | Hybrid vector + metadata search over the Amazon Product Dataset 2020 (e.g. Home & Kitchen), indexed in FAISS/Chroma |
| **MCP Server** | One server, two tools — `rag.search` (private catalog) and `web.search` (live comparison via Brave/Serper/Bing) — with tool discovery, schemas, caching (TTL 60–300s), and logging |
| **TTS** | Spoken answer ≤15s, fragment-based or streaming (OpenAI TTS, ElevenLabs, Azure Speech, Amazon Polly, Coqui) |
| **UI** | Streamlit (or React): mic input, live transcript, agent step log, comparison table, citations, Play-TTS button |
| **LLM** | Model-agnostic — swappable via environment variables/config (OpenAI, Anthropic, Gemini, Bedrock, or open-weight Llama/Mistral/Qwen/Phi) |

## Data

Primary corpus: **[Amazon Product Dataset 2020](https://www.kaggle.com/datasets/promptcloud/amazon-product-dataset-2020)** (Kaggle, `promptcloud/amazon-product-dataset-2020`).

```python
import kagglehub
path = kagglehub.dataset_download("promptcloud/amazon-product-dataset-2020")
```

This resolves to a single CSV, `marketing_sample_for_amazon_com-ecommerce__20200101_20200131__10k_data.csv` — **10,002 products, 28 columns**. We downloaded and inspected it directly (see [Code/data/1.1 explore data.ipynb](Code/data/1.1%20explore%20data.ipynb)); the real schema differs from a generic "id/title/brand/price/rating/features/ingredients" sketch in a few ways worth knowing before building on it. Everything here stays CSV end-to-end — no parquet conversion.

| Field we need | Actual column | Note |
|---|---|---|
| id | `Uniq Id` | ✅ 100% populated, zero duplicates — the real primary key |
| title | `Product Name` | ✅ 100% populated, but 137 duplicate values — dedupe in preprocessing |
| category | `Category` | 91.7% populated (pipe-delimited hierarchy, e.g. `Home & Kitchen \| ...`); ~8% of rows have no category |
| price | `Selling Price` | 98.9% non-null, but only 95.2% parse to a clean number; use this, not `List Price` (**0% populated**) |
| features | `About Product` | 97.3% populated; closest match to a feature-bullet field, no column literally named "features" |
| brand | — | `Brand Name` column exists but is **empty in 100% of rows** — must be parsed from `Product Name`/`About Product` instead |
| ingredients | — | `Ingredients` column exists but is **empty in 100% of rows** — treat as unavailable |
| rating | — | **no rating/stars field exists anywhere in this file** |
| reviews | — | **no review-level data** — this is a single flat product table, not a products+reviews pair |
| join key for a 2nd dataset | — | **`Asin` and `Sku` are also 100% empty** — no reliable external key exists; any join would have to be fuzzy, by title |

**13 of the 28 columns are entirely empty** (`Product Description, Stock, Size Quantity Variant, Product Details, Dimensions, Color, Quantity, Ingredients, Asin, Brand Name, Direction To Use, List Price, Sku`) — see [Code/data/processed/column_coverage.csv](Code/data/processed/column_coverage.csv) for the full per-column breakdown.

Category distribution is also skewed: **67% Toys & Games**; `Home & Kitchen` (~710 rows) and `Sports & Outdoors` (540 rows) are the next largest, while `Household`/`Cleaning` categories total only ~25 rows — too sparse to be the demo slice. **`Home & Kitchen` is the recommended demo category** instead of Household Cleaning.

Practical implications:
- Star ratings can't be cited in answers/UI unless a second dataset is fuzzy-joined by title (no ASIN/SKU key exists here) — otherwise drop rating from the pitch and UI.
- Brand should be extracted via regex/LLM parsing from `Product Name`, not read from `Brand Name`.
- "Ingredients" won't be populated for any products; don't design retrieval filters that assume it is.

Full writeup of the schema decision and licensing (CC0 Public Domain): [Project Overview/data_schema_and_licensing.md](Project%20Overview/data_schema_and_licensing.md).

Products are embedded on `Product Name` + `About Product` (+ `Product Specification`/`Technical Details` if useful) and indexed for hybrid retrieval; prices are unit-normalized where package size is available, for fair comparison.

## Repository Structure

```
Project/
├── Architecture/          # System diagrams (Mermaid)
├── Code/                  # Implementation (in progress)
│   └── data/              # exploration/preprocessing/indexing scripts (CSV in, CSV out — no parquet)
├── Data/                  # Raw Kaggle download (CSV + zip) — see Data/README.md
├── Project Overview/      # Project description, team structure, task backlog, data schema & licensing
└── README.md
```

Planned code layout as implementation lands:

```
Code/
├── data/       # ingestion, preprocessing, vector DB indexing
│   ├── 1.1 explore data.ipynb      # field coverage, price distribution, duplicates, category counts
│   ├── 1.2 process data.ipynb   # text cleaning, brand/unit extraction, dedup, category flattening
│   └── processed/              # generated outputs (column_coverage.csv, products_clean.csv)
├── graph/      # LangGraph nodes: router, planner, retriever, answerer
├── tools/      # MCP server + rag.search / web.search implementations
├── ui/         # Streamlit app
├── prompts/    # system/tool/router/planner prompts (prompt disclosure)
└── .env.example
```

## Team

See [team_structure_and_task_breakdown.md](Project%20Overview/team_structure_and_task_breakdown.md) for the full role breakdown, week-by-week critical path, and deliverables checklist.

For the granular, checkable engineering task list (per component, per checkpoint), see [detailed_task_backlog.md](Project%20Overview/detailed_task_backlog.md).

| Role | Owns |
|---|---|
| Orchestration Lead | LangGraph pipeline, routing logic, prompts, conflict resolution |
| Data Engineer | Data pipeline, vector DB indexing, hybrid retrieval, RAG eval |
| Voice/Integration Engineer | ASR, TTS, MCP server, web-search tool, performance testing |
| Frontend/UI Engineer | Streamlit app, audio I/O, comparison table, UX |
| Project Lead | Coordination, docs, prompt disclosure, presentation |

## Milestones

| Checkpoint | Week | Deliverable |
|---|---|---|
| Checkpoint 1 | Week 6 | One-page proposal, data slice, ingestion notebook, related work |
| Checkpoint 2 | Week 8 | Architecture diagram (graph + MCP calls), UI wireframe, RAG eval plan, MCP README |
| Final | Week 10 | Live demo (≤7 min), clean repo, README, build scripts, presentation |

## Status

🚧 Early stage — architecture and team planning are in place; implementation has not started yet (`Code/` is currently empty).

## License

TBD.
