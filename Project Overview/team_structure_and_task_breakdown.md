# Voice-to-Voice E-Commerce Assistant: Team Structure & Work Breakdown

## Recommended Team Structure (4-5 People)

### 1. **Orchestration Lead** (1 person)
**Responsible for:** LangGraph pipeline, agent routing logic, prompt engineering, tool-call orchestration  
**Key Tasks:**
- Design & implement 4-node graph (Router → Planner → Retriever → Answerer)
- Write all node prompts & decision logic
- Handle conflict resolution (live price vs. private data)
- Implement citation tracking & safety checks
- Own the end-to-end reasoning flow

**Timeline:** Week 1-10 (iterative refinement)  
**Deliverables:** graph.py, prompts.md, conflict handler, test results

---

### 2. **Data Engineer** (1 person)
**Responsible for:** Data pipeline, vector DB indexing, hybrid retrieval, RAG quality  
**Key Tasks:**
- Download & explore Amazon Product Dataset 2020
- Preprocess & normalize data (price per unit, units, categories)
- Index products with embeddings (title + features + review snippets)
- Build hybrid retrieval (vector + metadata filters)
- Conduct RAG eval (precision/recall audits)

**Timeline:** Week 1-10 (data pipeline → optimization)  
**Deliverables:** indexing scripts, rag.search tool, eval reports

---

### 3. **Voice/Integration Engineer** (1-1.5 people)
**Responsible for:** ASR, TTS, MCP server, web-search tool, performance testing  
**Key Tasks:**
- Implement Whisper ASR (fragment-based transcription)
- Build MCP server with two tools: `web.search` & `rag.search`
- Implement TTS (fragment-based synthesis, OpenAI/ElevenLabs/Coqui)
- Integrate web-search API (Brave/Serper) with caching
- Performance & reliability testing (latency, error handling)

**Timeline:** Week 1-10 (tools → polish → stress test)  
**Deliverables:** asr.py, tts.py, MCP server, web_search.py, performance report

---

### 4. **Frontend/UI Engineer** (1 person)
**Responsible for:** Streamlit/React app, audio I/O, visualization, UX  
**Key Tasks:**
- Build Streamlit scaffolding (mic input, transcript, agent log, comparison table)
- Wire ASR → graph → TTS pipeline
- Display citations & data lineage (doc IDs + live URLs)
- Create comparison table (products, price, rating, ingredients, source)
- Polish UI/UX (loading states, error messages, responsive design)

**Timeline:** Week 1-10 (scaffold → integrate → polish)  
**Deliverables:** main.py (Streamlit), UI mockups, usability test notes

---

### 5. **Project Lead** (0.5 person, often overlaps with one role)
**Responsible for:** Coordination, documentation, presentation, final integration  
**Key Tasks:**
- Write Checkpoint 1 proposal & related work
- Compile architecture & data-flow docs
- Collect & organize all prompts in `prompts/` folder
- Write README, setup instructions, safety guidelines
- Prepare demo script & presentation slides
- Coordinate dry run & final integration

**Timeline:** Week 1, 6, 8, 10 (milestones)  
**Deliverables:** proposal.md, architecture.md, README.md, prompts/ folder, slides.pdf

---

## Why This Separation Works

| Aspect | Benefit |
|--------|---------|
| **Parallel Work** | Data engineer indexes while orchestration lead designs prompts; Voice engineer builds tools while frontend builds UI |
| **Minimal Dependencies** | Each role has clear I/O contracts; MCP tool schemas & data formats defined early |
| **Specialization** | Each person plays to their strength (ML infra, LLMs, voice systems, UX) |
| **Clear Handoffs** | Data indexing → planner can test locally; MCP tools finalized → UI can integrate |
| **Scalability** | Easy to add more people (e.g., a second data engineer for reranking) |

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
├─ Orchestration: Finalize prompts, node logic
├─ Voice: Finalize MCP schemas, web.search skeleton
├─ Frontend: Connect to mock data
└─ Project Lead: Compile proposal

Week 7-8 (Checkpoint 2 - integration):
├─ Data: Build rag.search, test hybrid retrieval
├─ Orchestration: Implement graph, test with mocks
├─ Voice: Implement ASR, TTS, web.search, MCP server
├─ Frontend: Integrate ASR → graph → TTS → UI
└─ Project Lead: Document architecture, MCP README

Week 9-10 (Final - polish):
├─ Data: RAG quality audit, optimization
├─ Orchestration: Refine safety, conflicts, citations
├─ Voice: Performance testing, stress tests
├─ Frontend: UI polish, usability testing
└─ Project Lead: Demo script, final docs, dry run
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

---

## Communication & Collaboration Tools

**Recommended:**
- **Slack/Discord:** Daily async updates, quick questions
- **Shared GitHub repo:** Code coordination, PR reviews
- **Shared Google Doc:** Prompts, schemas, decisions log
- **Weekly Zoom:** 30 min sync (design decisions, blocker resolution)
- **Notion/Asana:** Task tracking (can use the provided task list above)

---

## Tips for Success

1. **Nail the Contracts Early**
   - Finalize tool I/O schemas by end of Week 1
   - Agree on graph state structure & prompt format
   - This unblocks parallel work

2. **Build MVP First**
   - Fragment-based ASR/TTS (not streaming) = faster development
   - Mock tools first, integrate real ones later
   - Test with 5-10 diverse queries, not 100s

3. **Prioritize the Critical Path**
   - Data indexing → Orchestration → UI integration
   - Voice tools are less critical (can be swapped)
   - Demo rehearsal in Week 9 catches last-minute issues

4. **Document as You Go**
   - Prompts folder should be updated each week
   - README updated at each checkpoint
   - Saves time at the end

5. **Contingency Plans**
   - If ASR/TTS latency is high: simplify prompt, add caching
   - If RAG quality is low: add reranker or manual feature tuning
   - If graph routing fails: add explicit planner rules
   - Have a stripped-down "demo mode" in case live tools fail

---

## Team Size Variations

**4 people (Recommended):**
- Orchestration Lead, Data Engineer, Voice/Integration Engineer, Frontend Engineer

**5 people (Ideal):**
- Add dedicated Project Lead (full-time coordination & documentation)

**3 people (Tight):**
- Combine Orchestration + Frontend (one person does graph + UI)
- Combine Data + Voice (one person does RAG + tools)
- Project Lead = one of the above (part-time)

**6+ people (Scaling):**
- Add second Data Engineer (reranking, data cleaning)
- Add QA Engineer (testing, stress tests, demo validation)
- Add dedicated DevOps (MCP server deployment, env management)

---

## Next Steps

1. **Assign roles** based on team strengths & interest
2. **Set up shared repo** with folder structure:
   ```
   voice-assistant/
   ├── data/            (data engineer)
   ├── graph/           (orchestration)
   ├── tools/           (voice/integration)
   ├── ui/              (frontend)
   ├── prompts/         (all)
   ├── README.md        (project lead)
   └── .env.example
   ```
3. **Week 1 sync:** Finalize tool schemas & contracts
4. **Start tasks** from Checkpoint 1 in parallel
5. **Weekly syncs** to align & unblock

Good luck! 🚀
