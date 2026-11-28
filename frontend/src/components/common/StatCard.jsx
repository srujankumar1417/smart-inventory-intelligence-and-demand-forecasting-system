/** StatCard — label, big number, optional kpi-meta line.
 *  Stat cards are numbers: label, figure, comparison. No sparklines. */
export function StatCard({ label, value, meta, className = '' }) {
  return (
    <div className={`card card-compact kpi-card ${className}`}>
      <span className="eyebrow">{label}</span>
      <div>
        <div className="kpi-value">{value}</div>
        {meta && <div className="kpi-meta" style={{ marginTop: 6 }}>{meta}</div>}
      </div>
    </div>
  );
}
