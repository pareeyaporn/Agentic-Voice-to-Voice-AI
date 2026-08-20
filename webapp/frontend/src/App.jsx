import { useEffect, useRef, useState } from 'react'
import { fetchConfig, fetchPromptLog, streamQuery, synthesizeSpeech, transcribeAudio } from './api.js'
import Citations from './components/Citations.jsx'
import ComparisonTable from './components/ComparisonTable.jsx'
import Orb from './components/Orb.jsx'
import Recorder from './components/Recorder.jsx'
import StepLog from './components/StepLog.jsx'

export default function App() {
  const [config, setConfig] = useState(null)
  const [mock, setMock] = useState(true)
  const [transcript, setTranscript] = useState('')
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [running, setRunning] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [steps, setSteps] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [audioUrl, setAudioUrl] = useState(null)
  const [ttsBusy, setTtsBusy] = useState(false)
  const [ttsError, setTtsError] = useState(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [promptLog, setPromptLog] = useState(null)
  const fileRef = useRef(null)
  const resultsRef = useRef(null)

  useEffect(() => {
    fetchConfig().then(setConfig).catch(() => setError('Backend not reachable -- is uvicorn running on port 8500?'))
  }, [])

  useEffect(() => {
    if (result) resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [result])

  const orbState = recording ? 'listening'
    : (transcribing || running) ? 'thinking'
    : speaking ? 'speaking'
    : 'idle'

  async function handleAudio(blob, filename) {
    setTranscribing(true)
    setError(null)
    try {
      const { text } = await transcribeAudio(blob, filename)
      setTranscript(text)
    } catch (e) {
      setError(`Transcription failed: ${e.message}`)
    } finally {
      setTranscribing(false)
    }
  }

  async function run(query) {
    if (!query?.trim()) return
    setRunning(true)
    setSteps([])
    setResult(null)
    setError(null)
    setAudioUrl(null)
    setTtsError(null)
    try {
      await streamQuery(query.trim(), mock, (event) => {
        if (event.type === 'step') setSteps((prev) => [...prev, event])
        else if (event.type === 'final') setResult(event)
        else if (event.type === 'error') setError(event.message)
      })
    } catch (e) {
      setError(`Something went wrong running the assistant: ${e.message}`)
    } finally {
      setRunning(false)
    }
  }

  async function playAnswer() {
    if (!result?.final_answer) return
    setTtsBusy(true)
    setTtsError(null)
    try {
      const blob = await synthesizeSpeech(result.final_answer)
      const url = URL.createObjectURL(blob)
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

  async function togglePromptLog() {
    if (promptLog) { setPromptLog(null); return }
    try { setPromptLog(await fetchPromptLog()) } catch { setPromptLog([]) }
  }

  function pickExample(q) {
    setTranscript(q)
    run(q)
  }

  const examples = config?.mock_examples ?? []
  const busy = recording || transcribing || running

  return (
    <div className="page">
      <header className="topbar">
        <span className="brand">Voice Shopping Assistant</span>
        <button className="icon-btn" onClick={() => setSettingsOpen((v) => !v)} aria-label="Settings">⋯</button>
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
        <Orb state={orbState} />
        <p className="assistant-label">Your shopping assistant{mock ? ' · mock mode' : ''}</p>
        <h1 className="greeting">
          {recording ? 'Listening…'
            : transcribing ? 'Got it, transcribing…'
            : running ? 'On it — checking the catalog…'
            : 'Hey, what can I find for you today?'}
        </h1>

        <div className="chips">
          {examples.map((q) => (
            <button key={q} className="chip glass" disabled={busy} onClick={() => pickExample(q)}>
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
            placeholder={mock ? 'Mock mode -- pick an example above' : 'Write here, or use the mic…'}
            value={transcript}
            disabled={mock}
            onChange={(e) => setTranscript(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !busy) run(transcript) }}
          />
          {!mock && (
            <Recorder onAudio={handleAudio} onRecordingChange={setRecording}
              onError={(m) => setError(m)} disabled={transcribing || running} />
          )}
          <button className="send-btn" disabled={busy || (!mock && !transcript.trim())}
            onClick={() => run(mock ? (transcript || examples[0]) : transcript)}
            title="Get recommendation" aria-label="Get recommendation">➤</button>
        </div>
        {mock && <p className="hint">Mock-data mode is on — tap a suggestion above. Open ⋯ to switch to the live pipeline.</p>}
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
                <p className="answer-text">{result.final_answer}</p>
                {!mock && (
                  <button className="mic-btn play-btn" onClick={playAnswer} disabled={ttsBusy}
                    title="Play answer" aria-label="Play answer">
                    {ttsBusy ? <span className="spinner" /> : '🔊'}
                  </button>
                )}
              </div>
              {mock && <p className="muted">🔊 TTS playback is disabled in mock-data mode (real OpenAI TTS calls cost money).</p>}
              {ttsError && <p className="warn-text">Speech synthesis failed, showing text only: {ttsError}</p>}
              {audioUrl && (
                <audio controls autoPlay src={audioUrl}
                  onPlay={() => setSpeaking(true)}
                  onEnded={() => setSpeaking(false)}
                  onPause={() => setSpeaking(false)} />
              )}
            </section>

            <ComparisonTable products={result.products} />
            <Citations citations={result.citations} />
          </>
        )}
      </section>
    </div>
  )
}
