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
  const metrics = rows.length
    ? rows
    : (KPI_METRICS[platform] || []).map((metric) => ({ metric_name: metric }));

  return (
    <div className="table-card">
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th>Actual</th>
            <th>Target</th>
            <th>Achievement</th>
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
            const state = status === "On Track" ? "ready" : status === "Below Target" ? "danger" : "partial";
            return (
              <tr key={row.metric_name}>
                <td>{prettyMetric(row.metric_name)}</td>
                <td>{formatNumber(row.actual_month)}</td>
                <td>
                  <div className="editable-value">
                    <span>{formatNumber(row.target_month)}</span>
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
                  {formatNumber(row.achievement_month, row.achievement_month ? "%" : "")}
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
