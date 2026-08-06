import { formatNumber } from "../lib/format";

export default function MetricDelta({ value, suffix = "%", label = "growth" }) {
  if (value === null || value === undefined || value === "") return null;
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return null;

  const direction = numericValue > 0
    ? "positive"
    : numericValue < 0
      ? "negative"
      : "neutral";
  const arrow = numericValue > 0 ? "↑" : numericValue < 0 ? "↓" : "→";
  const magnitude = Math.abs(numericValue);

  return (
    <div
      className={`metric-delta ${direction}`}
      aria-label={`${label} ${numericValue > 0 ? "increased" : numericValue < 0 ? "decreased" : "unchanged"} by ${formatNumber(magnitude, suffix)}`}
    >
      <span aria-hidden="true">{arrow}</span>
      <span>{formatNumber(magnitude, suffix)} {label}</span>
    </div>
  );
}
