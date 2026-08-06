import { KPI_METRICS } from "../lib/constants";
import { formatNumber, prettyMetric } from "../lib/format";
import { StatusBadge } from "./Badges";

function PencilIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none">
      <path d="M12 20h9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path
        d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function KpiTable({ platform, rows, onEdit }) {
  const configuredMetrics = KPI_METRICS[platform] || [];
  const rowsByMetric = Object.fromEntries((rows || []).map((row) => [row.metric_name, row]));
  const metrics = configuredMetrics.length
    ? configuredMetrics.map((metric) => rowsByMetric[metric] || { metric_name: metric })
    : rows;

  return (
    <div className="table-card">
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th>Actual (Month / YTD)</th>
            <th>Target (Month / Year)</th>
            <th>Achievement (Month / YTD)</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((row) => {
            const achievement = Number(row.achievement_month);
            const status = !row.target_month
              ? "No Target"
              : achievement >= 100
                ? "On Track"
                : "Below Target";
            const state = status === "On Track"
              ? "success"
              : status === "Below Target"
                ? "danger"
                : "neutral";
            const showProgress = Boolean(row.target_month) && Number.isFinite(achievement);
            const progressValue = Math.min(Math.max(achievement, 0), 100);
            const progressState = state === "success"
              ? "success"
              : state === "warning"
                ? "warning"
                : "danger";
            return (
              <tr key={row.metric_name}>
                <td>{prettyMetric(row.metric_name)}</td>
                <td>{formatNumber(row.actual_month)} / {formatNumber(row.actual_year)}</td>
                <td>
                  <div className="editable-value">
                    <span>{formatNumber(row.target_month)} / {formatNumber(row.target_year)}</span>
                    <button
                      className="edit-icon-button"
                      type="button"
                      title={`Edit ${prettyMetric(row.metric_name)} target`}
                      aria-label={`Edit ${prettyMetric(row.metric_name)} target`}
                      onClick={() => onEdit(row)}
                    >
                      <PencilIcon />
                    </button>
                  </div>
                </td>
                <td className={achievement >= 100 ? "status-good" : row.target_month ? "status-bad" : ""}>
                  <div className="achievement-cell">
                    <span>
                      {formatNumber(row.achievement_month, row.achievement_month !== null && row.achievement_month !== undefined ? "%" : "")}
                      {" / "}
                      {formatNumber(row.achievement_year, row.achievement_year !== null && row.achievement_year !== undefined ? "%" : "")}
                    </span>
                    {showProgress ? (
                      <div
                        className={`achievement-progress ${progressState}`}
                        role="progressbar"
                        aria-label={`${prettyMetric(row.metric_name)} monthly achievement`}
                        aria-valuemin="0"
                        aria-valuemax="100"
                        aria-valuenow={progressValue}
                        aria-valuetext={`${formatNumber(row.achievement_month, "%")} monthly achievement`}
                      >
                        <span style={{ "--progress-value": `${progressValue}%` }} />
                      </div>
                    ) : null}
                  </div>
                </td>
                <td><StatusBadge text={status} state={state} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
