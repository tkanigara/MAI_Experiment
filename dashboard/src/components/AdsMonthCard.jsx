import { PlatformBadges, StatusBadge } from "./Badges";
import { formatDateTime } from "../lib/format";
import { PLATFORM_LABELS } from "../lib/constants";
import OpenIconButton from "./OpenIconButton";

export default function AdsMonthCard({ period, platforms, onOpen, onUpdate, onSync, onEditGoals, onDelete }) {
  const ready = period.import_status === "success";
  const goals = Object.entries(period.ads_configuration?.goals || {}).flatMap(([platform, items]) => (
    (items || []).map((goal) => `${PLATFORM_LABELS[platform]} · ${goal.key.replaceAll("_", " ")}`)
  ));
  return (
    <article className="month-card">
      <div className="card-main">
        <div className="month-head">
          <div>
            <div className="month-title">{period.period_label}</div>
            <StatusBadge text={ready ? "Data imported" : "No data"} state={ready ? "success" : "neutral"} />
          </div>
          <OpenIconButton label={`Open ${period.period_label} Ads report`} onClick={() => onOpen(period)} />
        </div>
        <PlatformBadges platforms={platforms} />
        <div className="goal-chip-row month-goal-chips">
          {goals.slice(0, 4).map((goal) => <span className="goal-chip" key={goal}>{goal}</span>)}
          {goals.length > 4 && <span className="goal-chip">+{goals.length - 4} more</span>}
        </div>
        <div className="month-updated">
          <span>Last updated</span>
          <strong>{formatDateTime(period.imported_at)}</strong>
        </div>
      </div>
      <div className="card-footer">
        <button className="danger-link" type="button" onClick={() => onDelete(period)}>Delete</button>
        <button className="text-link" type="button" onClick={() => onEditGoals(period)}>Edit Goals &amp; KPI</button>
        <button className="text-link" type="button" onClick={() => onUpdate(period)}>Update Data</button>
        <button className="text-link" type="button" onClick={() => onSync(period)}>Sync from Meta</button>
      </div>
    </article>
  );
}
