// Data lineage: private-catalog citations show their doc_id, live-web
// citations link out -- same split the Streamlit app renders.
export default function Citations({ citations }) {
  return (
    <section className="card glass">
      <h2>🔗 Citations &amp; data lineage</h2>
      {!citations.length && <p className="muted">No citations for this answer.</p>}
      <ul className="citations">
        {citations.map((c, i) => (
          <li key={i}>
            {c.source === 'web' ? (
              <>🌐 <strong>web</strong> — <a href={c.url} target="_blank" rel="noreferrer">{c.title || 'source'}</a></>
            ) : (
              <>🗂️ <strong>catalog</strong> (<code>doc_id={c.doc_id}</code>) — {c.title}</>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
