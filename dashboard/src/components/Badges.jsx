import { PLATFORM_LABELS } from "../lib/constants";
import facebookLogo from "./logo/facebook.png";
import instagramLogo from "./logo/instagram.png";
import tiktokLogo from "./logo/tiktok.png";
import youtubeLogo from "./logo/youtube.png";

const PLATFORM_LOGOS = {
  facebook: facebookLogo,
  instagram: instagramLogo,
  tiktok: tiktokLogo,
  youtube: youtubeLogo,
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

export function StatusBadge({ text, state = "partial" }) {
  return <span className={`status-label ${state}`}>{text}</span>;
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
