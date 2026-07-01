import { PlatformBadges, StatusBadge } from "./Badges";

export default function MonthCard({ month, platforms, onOpen }) {
  return (
    <article className="month-card">
      <div className="card-main">
        <div className="month-head">
          <div className="month-title">{month.label}</div>
          <StatusBadge text={month.status} state={month.state} />
        </div>
        <PlatformBadges platforms={platforms} />
      </div>
      <div className="card-footer">
        <button className="text-link" type="button" onClick={() => onOpen(month.slug)}>Open report</button>
      </div>
    </article>
  );
}
