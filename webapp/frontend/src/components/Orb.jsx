// The assistant orb -- pure CSS (layered radial gradients + blob morph), no
// assets. It is the primary control: press to start/stop speaking. The orb
// itself stays clean (no icon); the CTA note below it says what to do, and
// `state` doubles as a pipeline indicator:
//   idle      slow breathing                   (press to speak)
//   listening pink glow + expanding ripples    (recording; press to stop)
//   thinking  fast swirl, violet glow          (ASR or the agent graph running)
//   speaking  ripple rings                     (TTS audio playing)
export default function Orb({ state = 'idle', onClick, disabled, hint }) {
  return (
    <div className="orb-area">
      <button
        className={`orb-btn orb-${state}`}
        onClick={onClick}
        disabled={disabled}
        aria-label={state === 'listening' ? 'Stop recording' : 'Press to speak'}
      >
        <span className="orb-glow" />
        <span className="orb">
          <span className="orb-blob orb-blob-a" />
          <span className="orb-blob orb-blob-b" />
          <span className="orb-blob orb-blob-c" />
        </span>
        <span className="orb-ring orb-ring-1" />
        <span className="orb-ring orb-ring-2" />
        <span className="orb-ring orb-ring-3" />
      </button>
      {hint && <p className="orb-hint">{hint}</p>}
    </div>
  )
}
