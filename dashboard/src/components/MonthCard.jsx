import { PlatformBadges, StatusBadge } from "./Badges";
import { formatDateTime } from "../lib/format";
import OpenIconButton from "./OpenIconButton";

export default function MonthCard({ month, platforms, onOpen, onGenerateReport, onDelete, isGenerating }) {
  return (
    <article className="month-card">
      <div className="card-main">
        <div className="month-head">
          <div>
            <div className="month-title">{month.label}</div>
            <StatusBadge text={month.status} state={month.state} />
          </div>
          <div className="card-head-actions">
            <OpenIconButton label={`Open ${month.label} report`} onClick={() => onOpen(month.slug)} />
          </div>
        </div>
        <PlatformBadges platforms={platforms} />
        <div className="month-updated">
          <span>Last updated</span>
          <strong>{formatDateTime(month.last_updated)}</strong>
        </div>
      </div>
      <div className="card-footer">
        <button
          className="danger-link"
          type="button"
          disabled={isGenerating}
          onClick={() => onDelete?.(month)}
        >
          Delete
        </button>
        <button
          className="text-link"
          type="button"
          disabled={isGenerating}
          onClick={() => onGenerateReport?.(month)}
        >
          {isGenerating ? "Generating..." : "Generate report"}
        </button>
      </div>
    </article>
  );
}
