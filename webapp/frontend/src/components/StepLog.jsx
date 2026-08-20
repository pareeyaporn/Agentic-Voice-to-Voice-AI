const NODE_ICONS = {
  router: '🧭',
  planner: '🗺️',
  retriever: '🔎',
  answerer: '💬',
  safe_refusal: '🛑',
  out_of_scope: '↩️',
}

// Streamed agent step log: each entry appears as its NDJSON event lands, so
// the user watches the graph progress node by node instead of a blank spinner.
export default function StepLog({ steps, running }) {
  if (!steps.length && !running) return null
  return (
    <section className="card glass">
      <h2>🪜 Agent step log</h2>
      <ol className="step-log">
        {steps.map((s, i) => (
          <li key={i} className="step">
            <span className="step-icon">{NODE_ICONS[s.node] || '⚙️'}</span>
            <div>
              <span className="step-node">{s.node}</span>
              <span className="step-summary">{s.summary}</span>
            </div>
          </li>
        ))}
        {running && (
          <li className="step step-pending">
            <span className="step-icon spinner" />
            <div><span className="step-summary">running…</span></div>
          </li>
        )}
      </ol>
    </section>
  )
}
