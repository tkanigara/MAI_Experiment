import { KPI_METRICS } from "../lib/constants";
import { formatNumber, prettyMetric } from "../lib/format";
import { StatusBadge } from "./Badges";

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
            <th></th>
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
                <td>{formatNumber(row.target_month)}</td>
                <td className={achievement >= 100 ? "status-good" : row.target_month ? "status-bad" : ""}>
                  {formatNumber(row.achievement_month, row.achievement_month ? "%" : "")}
                </td>
                <td><StatusBadge text={status} state={state} /></td>
                <td>
                  <button className="icon-button" type="button" onClick={() => onEdit(row)}>
                    edit
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
