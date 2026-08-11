export const PLATFORMS = ["instagram", "facebook", "tiktok", "youtube", "linkedin", "threads"];
export const ADS_PLATFORMS = ["instagram", "facebook", "youtube", "tiktok"];

export const ADS_PLATFORM_SOURCES = {
  instagram: { key: "meta", label: "Meta Ads", available: true },
  facebook: { key: "meta", label: "Meta Ads", available: true },
  youtube: { key: "google_ads", label: "Google Ads", available: false },
  tiktok: { key: "tiktok_ads", label: "TikTok Ads", available: false },
};

export const ADS_GOALS = {
  instagram: [
    { key: "reach", label: "Reach", family: "Awareness" },
    { key: "engagement", label: "Engagement", family: "Engagement" },
    { key: "profile_visits", label: "Profile Visits", family: "Profile Growth" },
  ],
  facebook: [
    { key: "reach", label: "Reach", family: "Awareness" },
    { key: "engagement", label: "Engagement", family: "Engagement" },
    { key: "page_likes", label: "Page Likes", family: "Profile Growth" },
  ],
  youtube: [
    { key: "impressions", label: "Impressions", family: "Awareness" },
    { key: "video_views", label: "Video Views", family: "Awareness" },
  ],
  tiktok: [
    { key: "video_views", label: "Video Views", family: "Awareness" },
    { key: "follows", label: "Paid Follows", family: "Profile Growth" },
  ],
};

export const PLATFORM_LABELS = {
  instagram: "Instagram",
  facebook: "Facebook",
  tiktok: "TikTok",
  youtube: "YouTube",
  linkedin: "LinkedIn",
  threads: "Threads",
};

export const KPI_METRICS = {
  instagram: ["followers", "engagement", "reach"],
  facebook: ["followers", "engagement", "reach"],
  tiktok: ["followers", "views", "likes"],
  youtube: ["subscribers", "engagement", "views"],
  linkedin: ["followers", "engagement", "impressions"],
  threads: ["followers", "engagement", "views"],
};

export const CSV_TYPES = [
  { key: "account", title: "Account Data", description: "General account/profile data for all platforms." },
  { key: "competitor", title: "Competitor Data", description: "Competitor analysis data per platform in one CSV." },
  { key: "competitor_content", title: "Competitor Content", description: "Post-level competitor content for best-content analysis.", optional: true },
  { key: "all_content", title: "All Platform Content", description: "Post data for all connected platforms in one CSV." },
  { key: "ig_story", title: "Instagram Stories", description: "Instagram story performance data." },
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
