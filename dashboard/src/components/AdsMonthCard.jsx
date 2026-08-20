import { PlatformBadges, StatusBadge } from "./Badges";
import { formatDateTime } from "../lib/format";
import { PLATFORM_LABELS } from "../lib/constants";
import OpenIconButton from "./OpenIconButton";

export default function AdsMonthCard({ period, platforms, accounts = [], onOpen, onUpdate, onSync, onEditGoals, onDelete }) {
  const ready = period.import_status === "success";
  const goals = Object.entries(period.ads_configuration?.goals || {}).flatMap(([platform, items]) => (
    (items || []).map((goal) => `${PLATFORM_LABELS[platform]} · ${goal.key.replaceAll("_", " ")}`)
  ));
  const objectiveGoals = Object.keys(period.objective_configs?.meta || {}).map((objective) => `All Meta · ${objective.replaceAll("_", " ")}`);
  const visibleGoals = objectiveGoals.length ? objectiveGoals : goals;
  const usedAccounts = accounts.filter((account) => (period.selected_ad_account_ids || []).includes(account.id));
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
          {visibleGoals.slice(0, 4).map((goal) => <span className="goal-chip" key={goal}>{goal}</span>)}
          {visibleGoals.length > 4 && <span className="goal-chip">+{visibleGoals.length - 4} more</span>}
        </div>
        <div className="month-updated">
          <span>{period.active_source === "api" ? "Last synced" : "Last updated"}</span>
          <strong>{formatDateTime(period.sync_completed_at || period.imported_at)}</strong>
          {usedAccounts.length > 0 && <small>{usedAccounts.map((account) => `${account.name} (${account.id})`).join(", ")}</small>}
        </div>
      </div>
      <div className="card-footer">
        <button className="danger-link" type="button" onClick={() => onDelete(period)}>Delete</button>
        <button className="text-link" type="button" onClick={() => onEditGoals(period)}>Edit Goals &amp; KPI</button>
        <button className="text-link" type="button" onClick={() => onUpdate(period)}>Import CSV</button>
        <button className="text-link" type="button" onClick={() => onSync(period)}>Sync Meta</button>
      </div>
    </article>
  );
}
