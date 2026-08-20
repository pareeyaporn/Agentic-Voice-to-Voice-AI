// Small round mic button for the prompt bar. Purely presentational -- the
// actual MediaRecorder lives in useRecorder (shared with the tappable orb).
export default function Recorder({ recording, onToggle, disabled }) {
  return (
    <button
      className={`mic-btn ${recording ? 'mic-recording' : ''}`}
      onClick={onToggle}
      disabled={disabled}
      title={recording ? 'Stop recording' : 'Speak your request'}
      aria-label={recording ? 'Stop recording' : 'Start recording'}
    >
      {recording ? '⏹' : '🎙️'}
    </button>
  )
}
