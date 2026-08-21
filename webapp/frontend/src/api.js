// Thin fetch layer over the FastAPI backend (webapp/backend/main.py).
// All paths are relative -- Vite's dev proxy (vite.config.js) forwards /api/*.

export async function fetchConfig() {
  const res = await fetch('/api/config')
  if (!res.ok) throw new Error(`config failed: ${res.status}`)
  return res.json()
}

export async function fetchPromptLog() {
  const res = await fetch('/api/prompt-log')
  if (!res.ok) throw new Error(`prompt-log failed: ${res.status}`)
  return res.json()
}

export async function transcribeAudio(blob, filename) {
  const form = new FormData()
  form.append('file', blob, filename)
  const res = await fetch('/api/transcribe', { method: 'POST', body: form })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `transcription failed: ${res.status}`)
  }
  return res.json()
}

// Streams NDJSON events from POST /api/query, invoking onEvent per line as
// each arrives -- this is what makes the step log render live.
// lastTurn ({query, answer} or null): small memory feature -- only the
// immediately preceding turn, held client-side in App.jsx's own history
// state (never localStorage), sent back explicitly since the backend is
// otherwise stateless per-request. Ignored server-side in mock mode.
export async function streamQuery(query, mock, lastTurn, onEvent) {
  const res = await fetch('/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      mock,
      last_query: lastTurn?.query ?? null,
      last_answer: lastTurn?.answer ?? null,
    }),
  })
  if (!res.ok || !res.body) throw new Error(`query failed: ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let newline
    while ((newline = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, newline).trim()
      buffer = buffer.slice(newline + 1)
      if (line) onEvent(JSON.parse(line))
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer.trim()))
}

export async function synthesizeSpeech(text) {
  const res = await fetch('/api/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `TTS failed: ${res.status}`)
  }
  return res.blob()
}
