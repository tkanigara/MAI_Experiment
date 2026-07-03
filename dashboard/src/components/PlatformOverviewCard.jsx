import { PLATFORM_LABELS } from "../lib/constants";
import { formatNumber } from "../lib/format";
import { PlatformBadge, StatusBadge } from "./Badges";
import OpenIconButton from "./OpenIconButton";

export default function PlatformOverviewCard({ platform, data, profile, stats, onOpen }) {
  const kpiRows = data?.kpi_results || [];
  const total = kpiRows.length || 3;
  const met = kpiRows.filter((row) => Number(row.achievement_month) >= 100).length;
  const ready = total > 0 && met === total;

  return (
    <article className="platform-overview-card">
      <div className="platform-card-main">
        <div className="platform-card-top">
          <div>
            <div className="badge-row">
              <PlatformBadge platform={platform} />
              <StatusBadge text={ready ? "Ready" : "Partial"} state={ready ? "ready" : "partial"} />
            </div>
            <div className="profile-name">{profile?.profile_name || data?.report?.profile_name || PLATFORM_LABELS[platform]}</div>
            <div className="kpi-preview">{met} of {total} KPI targets met</div>
          </div>
          <div className="platform-card-actions">
            <OpenIconButton label={`View ${PLATFORM_LABELS[platform]} details`} onClick={() => onOpen(platform)} />
          </div>
        </div>
        <div className="platform-stat-grid">
          {stats.map((item) => (
            <div key={item.label}>
              <div className="stat-label">{item.label}</div>
              <div className="stat-value">{formatNumber(item.value)}</div>
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}
