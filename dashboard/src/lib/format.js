import { PLATFORMS } from "./constants";

export function formatNumber(value, suffix = "") {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (!Number.isFinite(number)) return `${value}${suffix}`;
  return `${number.toLocaleString("en-US", {
    maximumFractionDigits: Math.abs(number) < 10 ? 2 : 0,
  })}${suffix}`;
}

export function prettyMetric(metric) {
  return String(metric || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function platformFlags(client) {
  return PLATFORMS.filter((platform) => client?.[`has_${platform}`]);
}

export function clientSlug(client) {
  return client?.client_code || client?.id;
}

export function captionText(post) {
  const text = post?.caption || post?.post_id || "Untitled content";
  return text.length > 74 ? `${text.slice(0, 71)}...` : text;
}
