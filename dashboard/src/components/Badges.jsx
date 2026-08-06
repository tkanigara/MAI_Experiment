import { PLATFORM_LABELS } from "../lib/constants";
import facebookLogo from "./logo/facebook.png";
import instagramLogo from "./logo/instagram.png";
import tiktokLogo from "./logo/tiktok.png";
import youtubeLogo from "./logo/youtube.png";
import linkedinLogo from "./logo/linkedin.png";
import threadsLogo from "./logo/threads.png";

const PLATFORM_LOGOS = {
  facebook: facebookLogo,
  instagram: instagramLogo,
  tiktok: tiktokLogo,
  youtube: youtubeLogo,
  linkedin: linkedinLogo,
  threads: threadsLogo,
};

export function PlatformBadge({ platform, label }) {
  const platformLabel = label || PLATFORM_LABELS[platform] || platform;
  const logo = PLATFORM_LOGOS[platform];
  if (!logo) return <span className={`badge ${platform}`}>{platformLabel}</span>;
  return (
    <span className={`platform-logo-badge ${platform}`} title={platformLabel} aria-label={platformLabel}>
      <img src={logo} alt="" />
    </span>
  );
}

const STATUS_STATE_ALIASES = {
  ready: "success",
  completed: "success",
  partial: "warning",
  missing: "warning",
  queued: "info",
  running: "info",
  retrying: "info",
  failed: "danger",
  cancelled: "danger",
};

export function StatusBadge({ text, state = "neutral" }) {
  const semanticState = STATUS_STATE_ALIASES[state] || state;
  return <span className={`status-label ${semanticState}`}>{text}</span>;
}

export function uploadStatusState(uploadedFiles) {
  const count = Number(uploadedFiles || 0);
  if (count >= 5) return "success";
  if (count > 0) return "warning";
  return "neutral";
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
