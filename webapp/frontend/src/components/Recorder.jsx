import { useRef, useState } from 'react'

// Round mic button with MediaRecorder capture -- fragment-based (record the
// whole clip, then hand the blob up), mirroring the project's non-streaming
// ASR design. Chrome/Edge produce audio/webm; faster-whisper decodes it fine.
// Recording state is lifted via onRecordingChange so the orb can react.
export default function Recorder({ onAudio, onRecordingChange, onError, disabled }) {
  const [recording, setRecording] = useState(false)
  const mediaRef = useRef(null)
  const chunksRef = useRef([])

  function setRec(value) {
    setRecording(value)
    onRecordingChange?.(value)
  }

  async function start() {
    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      onError?.('Microphone access denied -- allow it in the browser, or type your request.')
      return
    }
    const recorder = new MediaRecorder(stream)
    chunksRef.current = []
    recorder.ondataavailable = (e) => chunksRef.current.push(e.data)
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop())
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
      onAudio(blob, 'recording.webm')
    }
    recorder.start()
    mediaRef.current = recorder
    setRec(true)
  }

  function stop() {
    mediaRef.current?.stop()
    setRec(false)
  }

  return (
    <button
      className={`mic-btn ${recording ? 'mic-recording' : ''}`}
      onClick={recording ? stop : start}
      disabled={disabled}
      title={recording ? 'Stop recording' : 'Speak your request'}
      aria-label={recording ? 'Stop recording' : 'Start recording'}
    >
      {recording ? '⏹' : '🎙️'}
    </button>
  )
}
