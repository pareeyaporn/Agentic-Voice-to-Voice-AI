// rating/ingredients columns deliberately absent -- 100% empty in this
// dataset (§1.1); "features" was never stored as retrievable metadata (§3.2).
export default function ComparisonTable({ products }) {
  if (!products.length) {
    return (
      <section className="card glass">
        <h2>📊 Comparison</h2>
        <p className="muted">No products retrieved for this query.</p>
      </section>
    )
  }
  return (
    <section className="card glass">
      <h2>📊 Comparison</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>Source</th><th>Title</th><th>Price</th><th>Brand</th></tr>
          </thead>
          <tbody>
            {products.map((p, i) => (
              <tr key={i}>
                <td>{(p.source || 'rag') === 'rag' ? '🗂️ catalog' : '🌐 web'}</td>
                <td>{p.title}</td>
                <td>{p.price != null ? `$${p.price.toFixed(2)}` : 'unknown'}</td>
                <td>{p.brand || 'unknown'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
