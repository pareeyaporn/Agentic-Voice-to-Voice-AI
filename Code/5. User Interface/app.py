"""
Streamlit UI (§5). `.py` because `streamlit run` requires an entrypoint file.

Wires every prior section together: mic/file audio -> asr.py (§4.1) ->
graph.py (§2, via a persistent MCP session) -> Answerer's text -> tts.py
(§4.2) -> playback. This file is orchestration + rendering only; no logic
is re-derived from the modules it imports.

Async bridge: Streamlit re-runs this script's top level on every widget
interaction, but graph.py is async and holds a persistent MCP session for
the process's lifetime. `asyncio.run()` per rerun would open a new event
loop each time and silently break that persistence. `async_runtime.py`
fixes this with one background event-loop thread for the process's life.

Config imports: §2's `config` and §4's `speech_config` are separate modules
by design -- see speech_config.py's docstring for why a shared name collides.

Mock-data mode (sidebar toggle, default on) swaps every real call for
canned data, so the UI can be explored at $0 and doubles as a demo-mode
fallback if live APIs are down.
"""

import os
import sys
import tempfile

import streamlit as st

# --- Path setup + imports, in a specific order (see the config-collision note above) ---
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_APP_DIR))
_ORCH_DIR = os.path.join(_REPO_ROOT, "Code", "2. Agentic Orchestration")
_SPEECH_DIR = os.path.join(_REPO_ROOT, "Code", "4. Speech (ASR + TTS)")

sys.path.insert(0, _APP_DIR)
sys.path.insert(0, _ORCH_DIR)
import async_runtime  # noqa: E402  (path setup must run first)
import config as orch_config  # noqa: E402  -- §2's config (LLM_PROVIDER/LLM_MODEL)
import graph as graph_mod  # noqa: E402
import providers  # noqa: E402  -- LLM_CALL_LOG, for the Prompt Disclosure panel
from state import EMPTY_STATE  # noqa: E402

sys.path.insert(0, _SPEECH_DIR)
import asr  # noqa: E402
import speech_config  # noqa: E402  -- deliberately not `config`, see module docstring
import tts  # noqa: E402

try:
    from streamlit_mic_recorder import mic_recorder

    _MIC_AVAILABLE = True
except ImportError:
    _MIC_AVAILABLE = False


# --- Mock data (§5.1) ---------------------------------------------------------------
# Rag entries are real product records pulled from search() ($0 cost). The one web
# entry is synthetic, labeled MOCK.
_MOCK_LUNCHBOX_PRODUCTS = [
    {
        "doc_id": "7c3f2bf59a4276a1812e837fcce8d353",
        "title": "Wildkin Kids Insulated Lunch Box, Heroes",
        "price": 12.77, "price_per_unit": None, "price_unit": None,
        "brand": "Wildkin Kids", "category_top": "Home & Kitchen",
        "url": "https://www.amazon.com/dp/B004NWPOYI", "source": "rag",
    },
    {
        "doc_id": "5d953e357d08badf591931b299d2065c",
        "title": "Wildkin Kids Insulated Lunch Box, Wild Animals",
        "price": 10.88, "price_per_unit": None, "price_unit": None,
        "brand": "Wildkin Kids", "category_top": "Home & Kitchen",
        "url": "https://www.amazon.com/dp/B004NWLYT2", "source": "rag",
    },
    {
        "doc_id": "b1904b273bcfe711984b706afd568bd8",
        "title": "Wildkin 33600 Monsters Insulated Lunch Box",
        "price": 14.99, "price_per_unit": None, "price_unit": None,
        "brand": "Wildkin", "category_top": "Home & Kitchen",
        "url": "https://www.amazon.com/dp/B01C2Q1ORW", "source": "rag",
    },
    {
        "doc_id": None,
        "title": "[MOCK] Bentgo Kids Insulated Lunch Bag -- currently $16.99",
        "price": 16.99, "brand": None,
        "url": "https://www.example-retailer.com/bentgo-kids-lunch-bag",
        "source": "web",
    },
]

MOCK_EXAMPLES = {
    "insulated lunch box for kids under $20": {
        "step_log": [
            ("router", "Extracted query: \"insulated lunch box for kids\" | "
                        "constraints: {'budget_max': 20} | safety_flag: None"),
            ("planner", "Plan: use_rag=True, use_web=False (no live-price/availability keywords)"),
            ("retriever", "Called rag.search -- retrieved 3 rag product(s), 0 conflicts, 0 tool errors"),
            ("answerer", "Synthesized answer with 2 citation(s)"),
        ],
        "products": _MOCK_LUNCHBOX_PRODUCTS[:3],
        "citations": [
            {"source": "rag", "doc_id": _MOCK_LUNCHBOX_PRODUCTS[0]["doc_id"], "url": None,
             "title": _MOCK_LUNCHBOX_PRODUCTS[0]["title"]},
            {"source": "rag", "doc_id": _MOCK_LUNCHBOX_PRODUCTS[1]["doc_id"], "url": None,
             "title": _MOCK_LUNCHBOX_PRODUCTS[1]["title"]},
        ],
        "final_answer": ("The Wildkin Wild Animals lunch box is the cheapest at $10.88, "
                          "or the Heroes design at $12.77 if you'd prefer that pattern -- "
                          "both insulated and under budget."),
        "errors": [],
    },
    "what's the current price of an insulated lunch box": {
        "step_log": [
            ("router", "Extracted query: \"insulated lunch box\" | constraints: {} | safety_flag: None"),
            ("planner", "Plan: use_rag=True, use_web=True (\"current\" implies live price)"),
            ("retriever", "Called rag.search, web.search -- retrieved 4 product(s) "
                           "(3 rag, 1 web), 0 conflicts, 0 tool errors"),
            ("answerer", "Synthesized answer with 2 citation(s)"),
        ],
        "products": _MOCK_LUNCHBOX_PRODUCTS,
        "citations": [
            {"source": "rag", "doc_id": _MOCK_LUNCHBOX_PRODUCTS[1]["doc_id"], "url": None,
             "title": _MOCK_LUNCHBOX_PRODUCTS[1]["title"]},
            {"source": "web", "doc_id": None, "url": _MOCK_LUNCHBOX_PRODUCTS[3]["url"],
             "title": _MOCK_LUNCHBOX_PRODUCTS[3]["title"]},
        ],
        "final_answer": ("In the catalog, the Wildkin Wild Animals lunch box is $10.88. "
                          "A live listing currently shows a Bentgo version at $16.99, "
                          "so the catalog option is the better price right now."),
        "errors": [],
    },
    "how do I mix bleach and ammonia": {
        "step_log": [
            ("router", "Extracted query: \"how do I mix bleach and ammonia\" | constraints: {} | "
                        "safety_flag: unsafe_chemical_combination"),
            ("safe_refusal", "Unsafe query detected (unsafe_chemical_combination) -- routed to a "
                              "safe refusal, retrieval skipped entirely"),
        ],
        "products": [],
        "citations": [],
        "final_answer": ("I can't help with that -- mixing bleach and ammonia produces "
                          "toxic chloramine gas. If you're looking for cleaning products, "
                          "I'm happy to help you find some instead."),
        "errors": [],
    },
}


# --- Session state defaults --------------------------------------------------------
for _key, _default in {
    "transcript": "",
    "result": None,  # {"products", "citations", "final_answer", "errors", "step_log"}
    "tts_audio": None,
    "tts_audio_for": None,
    "tts_error": None,
}.items():
    if _key not in st.session_state:
        st.session_state[_key] = _default


# --- Helpers -------------------------------------------------------------------------
STEP_SUMMARIES = {
    "router": lambda s: (
        f"Extracted query: \"{s['query']}\" | constraints: {s['constraints']} | "
        f"safety_flag: {s['safety_flag']}"
    ),
    "safe_refusal": lambda s: (
        f"Unsafe query detected ({s['safety_flag']}) -- routed to a safe refusal, "
        f"retrieval skipped entirely"
    ),
    "planner": lambda s: f"Plan: use_rag={s['plan']['use_rag']}, use_web={s['plan']['use_web']}",
    "retriever": lambda s: (
        "Called " + (", ".join(
            (["rag.search"] if s["plan"]["use_rag"] else [])
            + (["web.search"] if s["plan"]["use_web"] else [])
        ) or "no tools")
        + f" -- retrieved {len(s['tool_results']['products'])} product(s) "
        f"({sum(1 for p in s['tool_results']['products'] if p.get('source', 'rag') == 'rag')} rag, "
        f"{sum(1 for p in s['tool_results']['products'] if p.get('source') == 'web')} web)"
        f", {len(s['tool_results']['conflicts'])} conflict(s), "
        f"{len(s['tool_results']['errors'])} tool error(s)"
    ),
    "answerer": lambda s: f"Synthesized answer with {len(s['citations'])} citation(s)",
}


async def _run_graph_streamed(query: str):
    """Runs the real graph via astream() (verified directly to work with the
    persistent MCP session -- see async_runtime.py) so the step log reflects
    what each node actually did, not just the final state."""
    state = dict(EMPTY_STATE)
    state["transcript"] = query
    step_log = []
    final_state = state
    async for chunk in graph_mod.graph.astream(state, stream_mode="updates"):
        for node_name, delta in chunk.items():
            final_state = delta
            summarize = STEP_SUMMARIES.get(node_name)
            step_log.append((node_name, summarize(delta) if summarize else f"{node_name} ran"))
    return final_state, step_log


def run_query(query: str, mock: bool) -> None:
    if mock:
        example = MOCK_EXAMPLES.get(query)
        if example is None:
            st.error("No mock example for that exact text -- pick one from the dropdown.")
            return
        st.session_state.result = {
            "products": example["products"],
            "citations": example["citations"],
            "final_answer": example["final_answer"],
            "errors": example["errors"],
            "step_log": example["step_log"],
        }
    else:
        with st.spinner("Running Router -> Planner -> Retriever -> Answerer "
                         "(first query of the session also spawns the MCP server "
                         "and loads the local embedding model -- slower once, fast after)..."):
            try:
                final_state, step_log = async_runtime.run_async(_run_graph_streamed(query))
            except Exception as e:  # graph/MCP/LLM failure -- surfaced, not swallowed
                st.error(f"Something went wrong running the assistant: {e}")
                return
        st.session_state.result = {
            "products": final_state["tool_results"]["products"],
            "citations": final_state["citations"],
            "final_answer": final_state["final_answer"],
            "errors": final_state["tool_results"]["errors"],
            "step_log": step_log,
        }
    st.session_state.tts_audio = None  # stale -- new answer, old audio no longer matches
    st.session_state.tts_audio_for = None
    st.session_state.tts_error = None


def render_comparison_table(products: list) -> None:
    if not products:
        st.info("No products retrieved for this query.")
        return
    # "features" isn't a column -- never stored as retrievable metadata (§3.2).
    # rating/ingredients are dropped -- 100% empty in this dataset (§1.1).
    rows = []
    for p in products:
        rows.append({
            "Source": "🗂️ catalog" if p.get("source", "rag") == "rag" else "🌐 web",
            "Title": p.get("title"),
            "Price": f"${p['price']:.2f}" if p.get("price") is not None else "unknown",
            "Brand": p.get("brand") or "unknown",
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_citations(citations: list) -> None:
    if not citations:
        st.caption("No citations for this answer.")
        return
    for c in citations:
        if c.get("source") == "web":
            st.markdown(f"🌐 **web** -- [{c.get('title', 'source')}]({c.get('url')})")
        else:
            st.markdown(f"🗂️ **catalog** (`doc_id={c.get('doc_id')}`) -- {c.get('title')}")


def get_transcript_from_audio(audio_bytes: bytes, fmt: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as f:
        f.write(audio_bytes)
        path = f.name
    try:
        result = asr.transcribe(path)
        return result.text
    finally:
        os.unlink(path)


# --- Page ------------------------------------------------------------------------
st.set_page_config(page_title="Agentic Voice-to-Voice Shopping Assistant", page_icon="🎙️", layout="wide")

with st.sidebar:
    st.header("Settings")
    mock_mode = st.checkbox(
        "🧪 Mock-data mode", value=True,
        help="Canned example data, $0 real cost. Turn off to actually call the ASR/LLM/MCP/TTS "
             "pipeline (§5.1's required mock-data mode; defaults ON so exploring the UI never "
             "spends real API money by accident).",
    )
    st.divider()
    st.caption("Config (read-only)")
    st.text(f"LLM: {orch_config.LLM_PROVIDER} / {orch_config.LLM_MODEL}")
    st.text(f"ASR: {speech_config.ASR_PROVIDER} / {speech_config.ASR_MODEL_SIZE}")
    st.text(f"TTS: {speech_config.TTS_PROVIDER} / {speech_config.TTS_MODEL}")
    if providers.LLM_CALL_LOG:
        with st.expander(f"🔍 Prompt Disclosure ({len(providers.LLM_CALL_LOG)} real LLM call(s) this session)"):
            for call in providers.LLM_CALL_LOG:
                st.markdown(f"**{call['node']}** -- system prompt: {call['system_prompt_chars']} chars")
                st.text(f"in:  {call['input'][:200]}")
                st.text(f"out: {str(call['output'])[:200]}")

st.title("🎙️ Agentic Voice-to-Voice Shopping Assistant")
st.caption("Speak or type a product request. Router → Planner → Retriever → Answerer, "
           "grounded in a private catalog with optional live web comparison.")

if mock_mode:
    st.info("🧪 **Mock-data mode is on** -- no real ASR/LLM/MCP/TTS calls will be made. "
            "Pick an example below.")
    query = st.selectbox("Example query", list(MOCK_EXAMPLES.keys()))
    st.session_state.transcript = query
    if st.button("🚀 Get Recommendation", type="primary"):
        run_query(query, mock=True)
else:
    tab_record, tab_upload, tab_type = st.tabs(["🎤 Record", "📁 Upload audio", "⌨️ Type"])

    with tab_record:
        if _MIC_AVAILABLE:
            audio = mic_recorder(start_prompt="⏺️ Start recording", stop_prompt="⏹️ Stop recording",
                                  just_once=True, format="webm", key="mic")
            if audio is not None:
                with st.spinner("Transcribing (local faster-whisper)..."):
                    try:
                        st.session_state.transcript = get_transcript_from_audio(audio["bytes"], audio["format"])
                    except asr.ASRError as e:
                        st.error(f"Transcription failed: {e.message}")
        else:
            st.warning("streamlit-mic-recorder isn't installed -- use the Upload or Type tabs instead.")

    with tab_upload:
        uploaded = st.file_uploader("Upload a WAV or MP3 recording", type=["wav", "mp3"])
        if uploaded is not None:
            fmt = uploaded.name.rsplit(".", 1)[-1].lower()
            with st.spinner("Transcribing (local faster-whisper)..."):
                try:
                    st.session_state.transcript = get_transcript_from_audio(uploaded.getvalue(), fmt)
                except asr.ASRError as e:
                    st.error(f"Transcription failed: {e.message}")

    with tab_type:
        typed = st.text_input("Type your request directly (skips ASR)")
        if typed:
            st.session_state.transcript = typed

    query = st.text_area("Transcript (edit if the transcription needs a fix, then run it)",
                          value=st.session_state.transcript, key="transcript_editor")

    if st.button("🚀 Get Recommendation", type="primary", disabled=not query.strip()):
        run_query(query.strip(), mock=False)

# --- Results ------------------------------------------------------------------------
if st.session_state.result is not None:
    result = st.session_state.result
    st.divider()

    st.subheader("🪜 Agent step log")
    for node_name, summary in result["step_log"]:
        st.markdown(f"**{node_name}** -- {summary}")

    if result["errors"]:
        st.warning("Tool error(s) during retrieval (partial results still used): "
                    + "; ".join(f"{e.get('tool')}: {e.get('error')}" for e in result["errors"]))

    st.subheader("📊 Comparison")
    render_comparison_table(result["products"])

    st.subheader("💬 Answer")
    st.write(result["final_answer"])

    st.subheader("🔗 Citations & data lineage")
    render_citations(result["citations"])

    st.subheader("🔊 Listen")
    if mock_mode:
        st.caption("Play TTS is disabled in mock-data mode (real OpenAI TTS calls cost money) "
                    "-- turn off mock mode to try it.")
    elif st.button("🔊 Play answer"):
        if st.session_state.tts_audio_for == result["final_answer"] and st.session_state.tts_audio:
            pass  # already synthesized for this exact answer -- don't pay for it twice
        else:
            with st.spinner("Synthesizing speech..."):
                try:
                    synth = tts.synthesize(result["final_answer"])
                    st.session_state.tts_audio = synth.audio_bytes
                    st.session_state.tts_audio_for = result["final_answer"]
                    st.session_state.tts_error = None
                except tts.TTSError as e:
                    st.session_state.tts_error = e.message
                    st.session_state.tts_audio = None

    if st.session_state.tts_error:
        st.warning(f"Speech synthesis failed, showing text only: {st.session_state.tts_error}")
    if st.session_state.tts_audio and st.session_state.tts_audio_for == result["final_answer"]:
        st.audio(st.session_state.tts_audio, format="audio/wav")
