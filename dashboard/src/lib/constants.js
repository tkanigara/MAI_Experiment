export const PLATFORMS = ["instagram", "facebook", "tiktok", "youtube"];

export const PLATFORM_LABELS = {
  instagram: "Instagram",
  facebook: "Facebook",
  tiktok: "TikTok",
  youtube: "YouTube",
};

export const KPI_METRICS = {
  instagram: ["followers", "engagement", "reach"],
  facebook: ["followers", "engagement", "reach"],
  tiktok: ["followers", "engagement", "views"],
  youtube: ["subscribers", "engagement", "views"],
};

export const CSV_TYPES = [
  { key: "account", title: "Account Data", description: "General account/profile data for all platforms." },
  { key: "competitor", title: "Competitor Data", description: "Competitor analysis data per platform in one CSV." },
  { key: "ig_post", title: "Instagram Posts", description: "Instagram post performance data." },
  { key: "ig_story", title: "Instagram Stories", description: "Instagram story performance data." },
  { key: "fb_post", title: "Facebook Posts", description: "Facebook post performance data." },
  { key: "tt_post", title: "TikTok Posts", description: "TikTok post performance data." },
  { key: "yt_post", title: "YouTube Posts", description: "YouTube post performance data." },
];

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export function buildReportMonths() {
  const currentYear = new Date().getFullYear();
  const years = [currentYear - 1, currentYear, currentYear + 1];
  return years.flatMap((year) => MONTH_NAMES.map((month) => ({
    label: `${month} ${year}`,
    slug: `${month.toLowerCase()}-${year}`,
  })));
}

export const REPORT_MONTHS = buildReportMonths();
