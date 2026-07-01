import { PLATFORM_LABELS } from "../lib/constants";

export function PlatformBadge({ platform, label }) {
  return <span className={`badge ${platform}`}>{label || PLATFORM_LABELS[platform] || platform}</span>;
}

export function StatusBadge({ text, state = "partial" }) {
  return <span className={`badge ${state}`}>{text}</span>;
}

export function PlatformBadges({ platforms }) {
  return (
    <div className="badge-row">
      {platforms.map((platform) => (
        <PlatformBadge key={platform} platform={platform} />
      ))}
    </div>
  );
}
