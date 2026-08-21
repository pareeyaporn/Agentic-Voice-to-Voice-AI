import { useRef, useState } from 'react'
import { meterMicStream, playEarcon } from './sound.js'

// One MediaRecorder shared by every mic control (the orb and the prompt-bar
// button), so two controls can't double-record. Fragment-based: record the
// whole clip, then hand the blob up — mirroring the project's non-streaming
// ASR design. Chrome/Edge produce audio/webm; faster-whisper decodes it fine.
// Recording plays start/stop earcons and feeds the orb's level meter.
export default function useRecorder({ onAudio, onError }) {
  const [recording, setRecording] = useState(false)
  const mediaRef = useRef(null)
  const chunksRef = useRef([])
  const stopMeterRef = useRef(null)

  async function start() {
    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      onError?.('Microphone access denied -- allow it in the browser, or type your request.')
      return
    }
    playEarcon('start')
    stopMeterRef.current = meterMicStream(stream)
    const recorder = new MediaRecorder(stream)
    chunksRef.current = []
    recorder.ondataavailable = (e) => chunksRef.current.push(e.data)
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop())
      stopMeterRef.current?.()
      stopMeterRef.current = null
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
      onAudio(blob, 'recording.webm')
    }
    recorder.start()
    mediaRef.current = recorder
    setRecording(true)
  }

  function stop() {
    playEarcon('stop')
    mediaRef.current?.stop()
    setRecording(false)
  }

  function toggle() {
    if (recording) stop()
    else start()
  }

  return { recording, start, stop, toggle }
}
