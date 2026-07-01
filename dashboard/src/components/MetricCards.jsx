import { formatNumber } from "../lib/format";

export default function MetricCards({ metrics }) {
  if (!metrics.length) return <div className="empty">No metrics available.</div>;
  return (
    <div className="metric-grid">
      {metrics.map((metric) => (
        <article className="metric-card" key={metric.label}>
          <div className="metric-label">{metric.label}</div>
          <div className="metric-value">{formatNumber(metric.value, metric.suffix || "")}</div>
        </article>
      ))}
    </div>
  );
}
