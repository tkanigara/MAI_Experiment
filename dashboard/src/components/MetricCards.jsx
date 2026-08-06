import { formatNumber } from "../lib/format";
import MetricDelta from "./MetricDelta";

export default function MetricCards({ metrics }) {
  if (!metrics.length) return <div className="empty">No metrics available.</div>;
  const growthMetric = metrics.find((metric) => metric.label === "Growth Rate");
  const audienceMetric = metrics.find(
    (metric) => ["Followers", "Subscribers"].includes(metric.label),
  );
  const canGroupGrowth = Boolean(
    audienceMetric
    && growthMetric
    && growthMetric.value !== null
    && growthMetric.value !== undefined
    && growthMetric.value !== "",
  );
  const displayMetrics = metrics
    .filter((metric) => !canGroupGrowth || metric !== growthMetric)
    .map((metric) => (
      canGroupGrowth && metric === audienceMetric
        ? {
          ...metric,
          delta: growthMetric.value,
          deltaSuffix: growthMetric.suffix || "%",
        }
        : metric
    ));

  return (
    <section className="metric-card-container" aria-label="Platform metrics">
      <div className="metric-grid">
        {displayMetrics.map((metric) => (
          <article className="metric-card" key={metric.label}>
            <div className="metric-label">{metric.label}</div>
            <div className="metric-value">{formatNumber(metric.value, metric.suffix || "")}</div>
            <MetricDelta value={metric.delta} suffix={metric.deltaSuffix} />
          </article>
        ))}
      </div>
    </section>
  );
}
