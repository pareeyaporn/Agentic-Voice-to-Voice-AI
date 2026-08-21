import { useEffect, useRef, useState } from 'react'
import { fetchConfig, fetchPromptLog, streamQuery, synthesizeSpeech, transcribeAudio } from './api.js'
import Citations from './components/Citations.jsx'
import ComparisonTable from './components/ComparisonTable.jsx'
import Orb from './components/Orb.jsx'
import Recorder from './components/Recorder.jsx'
import StepLog from './components/StepLog.jsx'
import { meterAudioElement } from './sound.js'
import useRecorder from './useRecorder.js'

// What the orb says while each graph node runs -- the step log card keeps the
// full technical trace; this is the human-readable narration (VUI best
// practice: staged, meaningful status instead of a generic spinner).
const STAGE_MESSAGES = {
  router: 'Understanding your request…',
  planner: 'Planning where to look…',
  retriever: 'Searching the catalog…',
  answerer: 'Writing your answer…',
  safe_refusal: 'That request isn’t safe — writing a careful reply…',
  out_of_scope: 'That’s outside shopping — replying…',
}

function formatSeconds(s) {
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export default function App() {
  const [config, setConfig] = useState(null)
  const [mock, setMock] = useState(true)
  const [transcript, setTranscript] = useState('')
  const [transcribing, setTranscribing] = useState(false)
  const [running, setRunning] = useState(false)
  const [stageMsg, setStageMsg] = useState(null)
  const [speaking, setSpeaking] = useState(false)
  const [steps, setSteps] = useState([])
  const [result, setResult] = useState(null)
  const [lastQuery, setLastQuery] = useState('')
  const [history, setHistory] = useState([])
  const [error, setError] = useState(null)
  const [audioUrl, setAudioUrl] = useState(null)
  const [ttsBusy, setTtsBusy] = useState(false)
  const [ttsError, setTtsError] = useState(null)
  const [revealCount, setRevealCount] = useState(Infinity)
  const [recSeconds, setRecSeconds] = useState(0)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [promptLog, setPromptLog] = useState(null)
  // index.html sets the initial theme (saved choice, else OS preference)
  // before first paint; this state just mirrors and toggles it.
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'light')
  const fileRef = useRef(null)
  const resultsRef = useRef(null)
  const speakMeterRef = useRef(null)

  // Voice-to-voice loop: a query that came in by voice gets its answer spoken
  // back automatically -- the hands-free flow the project brief asks for.
  const recorder = useRecorder({
    onAudio: (blob, name) => handleAudio(blob, name, { fromVoice: true }),
    onError: (m) => setError(m),
  })

  useEffect(() => {
    fetchConfig().then(setConfig).catch(() => setError('Backend not reachable -- is uvicorn running on port 8500?'))
  }, [])

  useEffect(() => {
    if (result) resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [result])

  // Recording timer -- visible feedback that the mic is live (and for how long)
  useEffect(() => {
    if (!recorder.recording) { setRecSeconds(0); return }
    const id = setInterval(() => setRecSeconds((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [recorder.recording])

  const orbState = recorder.recording ? 'listening'
    : (transcribing || running || ttsBusy) ? 'thinking'
    : speaking ? 'speaking'
    : 'idle'

  async function handleAudio(blob, filename, { fromVoice = false } = {}) {
    setTranscribing(true)
    setError(null)
    try {
      const { text } = await transcribeAudio(blob, filename)
      setTranscript(text)
      if (fromVoice && text.trim()) await run(text, { fromVoice: true })
    } catch (e) {
      setError(`Transcription failed: ${e.message}`)
    } finally {
      setTranscribing(false)
    }
  }

  async function run(query, { fromVoice = false } = {}) {
    if (!query?.trim()) return
    const q = query.trim()
    setRunning(true)
    setStageMsg(null)
    setSteps([])
    setResult(null)
    setError(null)
    setAudioUrl(null)
    setTtsError(null)
    setLastQuery(q)
    let finalAnswer = null
    try {
      await streamQuery(q, mock, (event) => {
        if (event.type === 'step') {
          setSteps((prev) => [...prev, event])
          setStageMsg(STAGE_MESSAGES[event.node] ?? null)
        } else if (event.type === 'final') {
          setResult(event)
          finalAnswer = event.final_answer
          if (finalAnswer) setHistory((prev) => [...prev, { query: q, answer: finalAnswer }])
        } else if (event.type === 'error') setError(event.message)
      })
    } catch (e) {
      setError(`Something went wrong running the assistant: ${e.message}`)
    } finally {
      setRunning(false)
      setStageMsg(null)
    }
    // Close the loop: voice in -> voice out (real mode only; mock never spends)
    if (fromVoice && !mock && finalAnswer) await playAnswer(finalAnswer)
  }

  async function playAnswer(text) {
    const answer = text ?? result?.final_answer
    if (!answer) return
    setTtsBusy(true)
    setTtsError(null)
    try {
      const blob = await synthesizeSpeech(answer)
      const url = URL.createObjectURL(blob)
      setRevealCount(0) // words fade in as the voice reads them
      setAudioUrl((old) => {
        if (old) URL.revokeObjectURL(old)
        return url
      })
    } catch (e) {
      setTtsError(e.message)
    } finally {
      setTtsBusy(false)
    }
  }

  function handleAudioPlay(e) {
    setSpeaking(true)
    speakMeterRef.current?.()
    speakMeterRef.current = meterAudioElement(e.target)
  }

  function handleAudioStop() {
    setSpeaking(false)
    setRevealCount(Infinity)
    speakMeterRef.current?.()
    speakMeterRef.current = null
  }

  function handleAudioTime(e) {
    const el = e.target
    if (!result?.final_answer || !el.duration) return
    const words = result.final_answer.split(/\s+/).length
    setRevealCount(Math.ceil((el.currentTime / el.duration) * words) + 2)
  }

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.documentElement.dataset.theme = next
    localStorage.setItem('theme', next)
  }

  async function togglePromptLog() {
    if (promptLog) { setPromptLog(null); return }
    try { setPromptLog(await fetchPromptLog()) } catch { setPromptLog([]) }
  }

  const examples = config?.mock_examples ?? []
  const busy = recorder.recording || transcribing || running

  function handleOrbTap() {
    if (transcribing || running || ttsBusy) return
    if (mock) {
      run(transcript || examples[0])
    } else {
      recorder.toggle()
    }
  }

  const orbHint = recorder.recording ? `Listening ${formatSeconds(recSeconds)} — press the circle again when you’re done`
    : transcribing ? 'Got it, transcribing…'
    : running ? (stageMsg ?? 'Thinking…')
    : ttsBusy ? 'Preparing the answer…'
    : speaking ? 'Answering…'
    : mock ? 'Press the circle to run the selected example'
    : '🎙 Press the circle to start speaking'

  // Follow-up suggestions -- VUI guidance: every answer should hint at the
  // next step. Each chip is a standalone query (the pipeline is single-turn).
  // Real mode only: mock mode can only replay its canned examples.
  const followUps = !mock && result && result.products?.length && lastQuery
    ? [`cheapest ${lastQuery}`, `what's the current price of ${lastQuery}`]
    : []

  const answerWords = result?.final_answer ? result.final_answer.split(/\s+/) : []
  const pastTurns = history.slice(0, -1)

  return (
    <div className="page">
      <header className="topbar">
        <span className="brand">Voice Shopping Assistant</span>
        <div className="topbar-actions">
          <button className="icon-btn" onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-label="Toggle light/dark mode">
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
          <button className="icon-btn" onClick={() => setSettingsOpen((v) => !v)} aria-label="Settings">⋯</button>
        </div>
      </header>

      {settingsOpen && (
        <div className="settings glass">
          <label className="toggle">
            <input type="checkbox" checked={mock} onChange={(e) => setMock(e.target.checked)} />
            <span>🧪 Mock-data mode <small>canned examples, $0 API cost</small></span>
          </label>
          {config && (
            <div className="config-lines">
              <p>LLM&nbsp;&nbsp;{config.llm_provider} / {config.llm_model || '(not set -- mock mode only)'}</p>
              <p>ASR&nbsp;&nbsp;{config.asr}</p>
              <p>TTS&nbsp;&nbsp;{config.tts}</p>
            </div>
          )}
          {!mock && config && !config.llm_configured && (
            <p className="warn-text">No API keys configured -- real mode will fail. Fill in .env.</p>
          )}
          <button className="link-btn" onClick={togglePromptLog}>
            🔍 Prompt disclosure {promptLog ? '▲' : '▼'}
          </button>
          {promptLog && (
            <div className="prompt-log">
              {promptLog.length === 0 && <p className="muted">No real LLM calls yet this session.</p>}
              {promptLog.map((c, i) => (
                <div key={i} className="prompt-entry">
                  <strong>{c.node}</strong> — system prompt: {c.system_prompt_chars} chars
                  <pre>in:  {c.input}{'\n'}out: {c.output}</pre>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <section className="hero">
        <Orb state={orbState} onClick={handleOrbTap} disabled={transcribing || running || ttsBusy} hint={orbHint} />
        <p className="assistant-label">Your shopping assistant{mock ? ' · mock mode' : ''}</p>
        <h1 className="greeting">
          {recorder.recording ? 'Listening…'
            : transcribing ? 'Got it…'
            : running ? 'On it…'
            : speaking ? 'Here’s what I found'
            : 'Hey, what can I find for you today?'}
        </h1>

        <div className="chips">
          {examples.map((q) => (
            <button key={q} className={`chip glass ${transcript === q ? 'chip-active' : ''}`} disabled={busy}
              onClick={() => (mock ? (setTranscript(q), run(q)) : setTranscript(q))}>
              {q}
            </button>
          ))}
        </div>

        <div className="prompt-bar glass">
          <button className="icon-btn" title="Upload a WAV/MP3 recording" disabled={busy || mock}
            onClick={() => fileRef.current?.click()}>＋</button>
          <input ref={fileRef} type="file" accept=".wav,.mp3,.webm,audio/*" hidden
            onChange={(e) => e.target.files[0] && handleAudio(e.target.files[0], e.target.files[0].name)} />
          <input
            type="text"
            className="prompt-input"
            placeholder={mock ? 'Mock mode -- press the circle or pick an example above' : 'Or write here…'}
            value={transcript}
            disabled={mock}
            onChange={(e) => setTranscript(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !busy) run(transcript) }}
          />
          {!mock && (
            <Recorder recording={recorder.recording} onToggle={recorder.toggle}
              disabled={transcribing || running || ttsBusy} />
          )}
          <button className="send-btn" disabled={busy || (!mock && !transcript.trim())}
            onClick={() => run(mock ? (transcript || examples[0]) : transcript)}
            title="Get recommendation" aria-label="Get recommendation">➤</button>
        </div>
      </section>

      {error && <div className="banner banner-error glass">{error}</div>}

      <section className="results" ref={resultsRef}>
        <StepLog steps={steps} running={running} />

        {result && (
          <>
            {result.errors?.length > 0 && (
              <div className="banner banner-warn glass">
                Tool error(s) during retrieval (partial results still used):{' '}
                {result.errors.map((e) => `${e.tool}: ${e.error}`).join('; ')}
              </div>
            )}

            <section className="card glass answer-card">
              <div className="answer-row">
                <p className="answer-text" aria-live="polite">
                  {audioUrl && Number.isFinite(revealCount)
                    ? answerWords.map((w, i) => (
                        <span key={i} className={i < revealCount ? 'w-on' : 'w-off'}>{w} </span>
                      ))
                    : result.final_answer}
                </p>
                {!mock && (
                  <button className="mic-btn play-btn" onClick={() => playAnswer()} disabled={ttsBusy}
                    title="Play answer" aria-label="Play answer">
                    {ttsBusy ? <span className="spinner" /> : '🔊'}
                  </button>
                )}
              </div>
              {mock && <p className="muted">🔊 TTS playback is disabled in mock-data mode (real OpenAI TTS calls cost money).</p>}
              {ttsError && <p className="warn-text">Speech synthesis failed, showing text only: {ttsError}</p>}
              {audioUrl && (
                <audio controls autoPlay src={audioUrl}
                  onPlay={handleAudioPlay}
                  onTimeUpdate={handleAudioTime}
                  onEnded={handleAudioStop}
                  onPause={handleAudioStop} />
              )}
              {followUps.length > 0 && (
                <div className="follow-ups">
                  <span className="muted">Ask a follow-up:</span>
                  {followUps.map((q) => (
                    <button key={q} className="chip glass chip-small" disabled={busy}
                      onClick={() => { setTranscript(q); run(q) }}>
                      {q}
                    </button>
                  ))}
                </div>
              )}
            </section>

            <ComparisonTable products={result.products} />
            <Citations citations={result.citations} />
          </>
        )}

        {pastTurns.length > 0 && (
          <section className="card glass history-card">
            <h2>🕘 Earlier this session</h2>
            <ul className="history">
              {pastTurns.map((t, i) => (
                <li key={i}>
                  <p className="history-q">🗣 {t.query}</p>
                  <p className="history-a">{t.answer}</p>
                </li>
              ))}
            </ul>
          </section>
        )}
      </section>
    </div>
  )
}
