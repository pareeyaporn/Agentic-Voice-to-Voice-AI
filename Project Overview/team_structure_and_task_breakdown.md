# Voice-to-Voice E-Commerce Assistant: Team Structure & Work Breakdown

## Team Structure (4 People)

No dedicated Project Lead — at 4 people, coordination/documentation/presentation duties are
folded into the 4 core roles rather than carved out as a 5th (part-time) person. Each role
owns the docs/coordination closest to its own domain, which is also just how the work has
actually landed in practice — whoever builds a section is who ends up documenting it.

### 1. **Orchestration Lead** (1 person)
**Responsible for:** LangGraph pipeline, agent routing logic, prompt engineering, tool-call orchestration — **plus prompts/graph documentation**
**Key Tasks:**
- Design & implement 4-node graph (Router → Planner → Retriever → Answerer)
- Write all node prompts & decision logic
- Handle conflict resolution (live price vs. private data)
- Implement citation tracking & safety checks
- Own the end-to-end reasoning flow
- Collect & organize all prompts in `prompts/` folder; write the graph-design write-up; own safety-notes documentation (refusal behavior)

**Timeline:** Week 1-10 (iterative refinement)  
**Deliverables:** graph.py, prompts/ folder, conflict handler, test results, graph design write-up

---

### 2. **Data Engineer** (1 person)
**Responsible for:** Data pipeline, vector DB indexing, hybrid retrieval, RAG quality — **plus data documentation**
**Key Tasks:**
- Download & explore Amazon Product Dataset 2020
- Preprocess & normalize data (price per unit, units, categories)
- Index products with embeddings (title + features + review snippets)
- Build hybrid retrieval (vector + metadata filters)
- Conduct RAG eval (precision/recall audits)
- Write the data preprocessing & indexing write-up, RAG eval plan/report

**Timeline:** Week 1-10 (data pipeline → optimization)  
**Deliverables:** indexing scripts, rag.search tool, eval reports, data schema & licensing doc

---

### 3. **Voice/Integration Engineer** (1 person)
**Responsible for:** ASR, TTS, MCP server, web-search tool, performance testing — **plus MCP/tool documentation**
**Key Tasks:**
- Implement Whisper (or comparable) ASR (fragment-based transcription)
- Build MCP server with two tools: `web.search` & `rag.search`
- Implement TTS (fragment-based synthesis, provider-swappable)
- Integrate web-search API (decided: Tavily — see [detailed_task_backlog.md](detailed_task_backlog.md) §3.3) with caching
- Performance & reliability testing (latency, error handling)
- Write the MCP server/tool schema write-up, domain-allowlist/ToS safety notes

**Timeline:** Week 1-10 (tools → polish → stress test)  
**Deliverables:** asr.py, tts.py, MCP server, web_search_tool.py, performance report, MCP README

---

### 4. **Frontend/UI Engineer** (1 person)
**Responsible for:** Streamlit app, audio I/O, visualization, UX — **plus overall README, setup instructions, and demo coordination**
**Key Tasks:**
- Build Streamlit scaffolding (mic input, transcript, agent log, comparison table)
- Wire ASR → graph → TTS pipeline
- Display citations & data lineage (doc IDs + live URLs)
- Create comparison table (products, price, brand, source)
- Polish UI/UX (loading states, error messages, responsive design)
- Own root README.md, `.env.example`/setup instructions, demo script + presentation slides, dry-run coordination
- **Added, not in the original plan:** a React + FastAPI alternative UI (`webapp/`) — voice-first tappable orb, hands-free voice-to-voice loop, streamed step log. Streamlit remains the reference UI; the React app became the primary UI for the recorded live demo

**Timeline:** Week 1-10 (scaffold → integrate → polish)  
**Deliverables:** app.py (Streamlit), webapp/ (React + FastAPI), README.md, demo script, slides.pdf, usability test notes

---

## Dependency Graph & Critical Path

```
Week 1-3 (Foundation - can work in parallel):
├─ Data Engineer: Download & explore data
├─ Orchestration: Design graph & prompts
├─ Voice: MCP skeleton + tool schemas
└─ Frontend: UI scaffold

Week 4-6 (Checkpoint 1 - milestones):
├─ Data: Index products, test retrieval
├─ Orchestration: Finalize prompts, node logic; compile proposal + related work
├─ Voice: Finalize MCP schemas, web.search skeleton
└─ Frontend: Connect to mock data

Week 7-8 (Checkpoint 2 - integration):
├─ Data: Build rag.search, test hybrid retrieval; write data write-up + eval plan
├─ Orchestration: Implement graph, test with mocks; architecture & data-flow docs
├─ Voice: Implement ASR, TTS, web.search, MCP server; MCP README
└─ Frontend: Integrate ASR → graph → TTS → UI; `.env.example` + setup instructions

Week 9-10 (Final - polish):
├─ Data: RAG quality audit, optimization
├─ Orchestration: Refine safety, conflicts, citations; safety notes doc
├─ Voice: Performance testing, stress tests
└─ Frontend: UI polish, usability testing; demo script, root README, slides, dry run
```

**Critical Path:** Data indexing → Orchestration → Frontend integration → Demo  
**Slack:** Voice tools can be swapped easily (Whisper/OpenAI TTS are drop-in)

---

## Key Coordination Points

### Weekly Syncs (15–30 min each)
1. **Tool & Data Format Contracts** (Week 1)
   - Agree on `rag.search` input/output schema
   - Agree on `web.search` response format
   - Agree on graph state schema

2. **MCP Tool Finalization** (Week 3)
   - Voice engineer presents tool schemas (JSON)
   - Data engineer confirms rag.search returns expected fields
   - Orchestration lead confirms tool outputs feed into graph

3. **Integration Testing** (Week 7)
   - Frontend engineer demos UI with mock data
   - Orchestration leads graph walkthrough (node behavior)
   - Voice engineer explains ASR/TTS latency & error handling

4. **Demo Prep** (Week 9)
   - Dry run with all components live
   - Fix last-minute bugs collaboratively
   - Finalize demo script & examples

---

## Deliverables Checklist

### Checkpoint 1 (Week 6)
- ✅ Proposal (1 page) + related work
- ✅ Data exploration notebook & schema definition
- ✅ Indexed products in Vector DB (FAISS/Chroma)
- ✅ Graph architecture & prompt examples
- ✅ MCP server skeleton + tool schemas
- ✅ Streamlit UI scaffold (mock data)

### Checkpoint 2 (Week 8)
- ✅ LangGraph implementation (end-to-end with mocks)
- ✅ ASR, TTS, web.search working
- ✅ rag.search tool integrated
- ✅ UI with live graph integration
- ✅ Architecture diagram, MCP README, eval plan
- ✅ Setup instructions (.env.example, dependencies)

### Final (Week 10)
- ✅ Clean repository with all code
- ✅ Comprehensive README (installation, running, troubleshooting)
- ✅ Prompts folder with all system/tool prompts
- ✅ 7-minute demo script + demo videos/screenshots
- ✅ Performance & reliability reports
- ✅ Presentation slides (problem, approach, results, limitations)
- ✅ Safety notes & limitations documentation
