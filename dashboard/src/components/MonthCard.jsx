import { PlatformBadges, StatusBadge } from "./Badges";

export default function MonthCard({ month, platforms, onOpen }) {
  return (
    <article className="month-card" onClick={() => onOpen(month.slug)}>
      <div className="card-main">
        <div className="month-head">
          <div className="month-title">{month.label}</div>
          <StatusBadge text={month.status} state={month.state} />
        </div>
        <PlatformBadges platforms={platforms} />
      </div>
      <div className="card-footer">
        <button className="text-link" type="button">Open report</button>
      </div>
    </article>
  );
}
