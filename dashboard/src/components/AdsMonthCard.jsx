import { PlatformBadges, StatusBadge } from "./Badges";
import { formatDateTime } from "../lib/format";
import OpenIconButton from "./OpenIconButton";

export default function AdsMonthCard({ period, platforms, onOpen, onUpdate, onDelete }) {
  const ready = period.import_status === "success";
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
        <div className="month-updated">
          <span>Last updated</span>
          <strong>{formatDateTime(period.imported_at)}</strong>
        </div>
      </div>
      <div className="card-footer">
        <button className="danger-link" type="button" onClick={() => onDelete(period)}>Delete</button>
        <button className="text-link" type="button" onClick={() => onUpdate(period)}>Update Data</button>
      </div>
    </article>
  );
}
