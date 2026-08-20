// The assistant orb -- pure CSS (layered radial gradients + blob morph), no
// assets. `state` doubles as a pipeline indicator:
//   idle      slow breathing              (waiting for input)
//   listening pink pulse                  (mic recording)
//   thinking  fast swirl                  (ASR or the agent graph running)
//   speaking  ripple rings                (TTS audio playing)
export default function Orb({ state = 'idle' }) {
  return (
    <div className={`orb-wrap orb-${state}`} aria-hidden="true">
      <div className="orb-glow" />
      <div className="orb">
        <div className="orb-blob orb-blob-a" />
        <div className="orb-blob orb-blob-b" />
        <div className="orb-blob orb-blob-c" />
      </div>
      <div className="orb-ring orb-ring-1" />
      <div className="orb-ring orb-ring-2" />
    </div>
  )
}
