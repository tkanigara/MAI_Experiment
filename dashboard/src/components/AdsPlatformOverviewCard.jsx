import { ADS_PLATFORM_SOURCES, PLATFORM_LABELS } from "../lib/constants";
import { formatNumber } from "../lib/format";
import { PlatformBadge, StatusBadge } from "./Badges";
import OpenIconButton from "./OpenIconButton";

export default function AdsPlatformOverviewCard({ platform, period, definition, configured = true, onOpen }) {
  const source = ADS_PLATFORM_SOURCES[platform];
  const available = Boolean(source?.available && configured && period?.import_status === "success");
  const status = !configured
    ? { text: "Not connected", state: "neutral" }
    : source?.available
      ? (available ? { text: "Ready", state: "success" } : { text: "Missing data", state: "warning" })
      : { text: "Coming soon", state: "info" };
  const stats = source?.available
    ? [
        ["Campaigns", period?.campaigns],
        ["Ads", period?.ads],
        ["Placements", period?.placements],
        ["Breakdowns", Number(period?.demographics || 0) + Number(period?.regions || 0)],
      ]
    : [["Campaigns", null], ["Ads", null], ["Spend", null], ["Results", null]];

  return (
    <article className={`platform-overview-card ads-platform-card ${available ? "" : "is-pending"}`}>
      <div className="platform-card-main">
        <div className="platform-card-top">
          <div>
            <div className="badge-row">
              <PlatformBadge platform={platform} />
              <StatusBadge text={status.text} state={status.state} />
            </div>
            <div className="profile-name">{PLATFORM_LABELS[platform]} Ads</div>
            <div className="kpi-preview">
              {source?.available
                ? `Source: ${source.label}`
                : `${source?.label} ingestion and storage are not connected yet`}
            </div>
            <div className="goal-chip-row">
              {(definition?.active_goals || []).map((goal) => (
                <span className="goal-chip" key={goal.key}>{goal.key.replaceAll("_", " ")}</span>
              ))}
            </div>
          </div>
          <OpenIconButton label={`View ${PLATFORM_LABELS[platform]} Ads details`} onClick={() => onOpen(platform)} />
        </div>
        <div className="platform-stat-grid">
          {stats.map(([label, value]) => (
            <div key={label}>
              <div className="stat-label">{label}</div>
              <div className="stat-value">{formatNumber(value)}</div>
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}
