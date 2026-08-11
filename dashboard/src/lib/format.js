import { ADS_PLATFORMS, PLATFORMS } from "./constants";

export function formatNumber(value, suffix = "") {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (!Number.isFinite(number)) return `${value}${suffix}`;
  return `${number.toLocaleString("en-US", {
    maximumFractionDigits: Math.abs(number) < 10 ? 2 : 0,
  })}${suffix}`;
}

export function prettyMetric(metric) {
  if (metric === "followers") return "Followers Growth";
  if (metric === "subscribers") return "Subscriber Growth";
  return String(metric || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function platformFlags(client) {
  return PLATFORMS.filter((platform) => client?.[`has_${platform}`]);
}

export function adsPlatformFlags(client) {
  const configured = client?.ads_platforms || client?.ads_configuration?.platforms;
  if (!Array.isArray(configured) || configured.length === 0) return ADS_PLATFORMS;
  return ADS_PLATFORMS.filter((platform) => configured.includes(platform));
}

export function adsPeriodSlug(period) {
  if (period?.slug) return period.slug;
  return String(period?.period_label || period?.label || period?.id || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function clientSlug(client) {
  return client?.client_code || client?.id;
}

export function captionText(post) {
  const text = post?.caption || post?.post_id || "Untitled content";
  return text.length > 74 ? `${text.slice(0, 71)}...` : text;
}
