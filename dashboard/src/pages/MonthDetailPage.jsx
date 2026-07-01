import Breadcrumb from "../components/Breadcrumb";
import PlatformOverviewCard from "../components/PlatformOverviewCard";
import { clientSlug, platformFlags } from "../lib/format";

function platformStats(platform, report = {}) {
  if (platform === "youtube") {
    return [
      { label: "Subscribers", value: report.total_subscribers },
      { label: "Views", value: report.total_views },
      { label: "Engagement", value: report.total_engagement },
      { label: "Videos", value: report.total_posts },
    ];
  }
  if (platform === "tiktok") {
    return [
      { label: "Followers", value: report.total_followers },
      { label: "Views", value: report.total_views },
      { label: "Engagement", value: report.total_engagement },
      { label: "Posts", value: report.total_posts },
    ];
  }
  return [
    { label: "Followers", value: report.total_followers },
    { label: "Reach", value: report.reach },
    { label: "Engagement", value: report.total_engagement },
    { label: "Posts", value: report.total_posts },
  ];
}

export default function MonthDetailPage({ client, month, profiles, platformData, onNavigate, onOpenPlatform, onOpenAddReport }) {
  const platforms = platformFlags(client);
  return (
    <section className="view active">
      <Breadcrumb
        items={[
          { label: "Clients", path: "/clients" },
          { label: client.client_name, path: `/clients/${clientSlug(client)}` },
          { label: month.label },
        ]}
        onNavigate={onNavigate}
      />
      <div className="page-title-row">
        <div>
          <h1>{month.label} Report</h1>
          <p>Overview of connected social media performance for this report period.</p>
        </div>
      </div>
      <section className="upload-summary">
        <div>
          <strong>{month.status || "Report data imported"}</strong>
          <span>{month.platform_reports || 0} platform reports available</span>
        </div>
        <button className="secondary-button" onClick={onOpenAddReport}>Update Data</button>
      </section>
      <div className="platform-overview-grid">
        {platforms.map((platform) => (
          <PlatformOverviewCard
            key={platform}
            platform={platform}
            data={platformData[platform]}
            profile={profiles.find((item) => item.platform === platform)}
            stats={platformStats(platform, platformData[platform]?.report)}
            onOpen={(selected) => onOpenPlatform(`${clientSlug(client)}/${month.slug}/${selected}`)}
          />
        ))}
      </div>
    </section>
  );
}
