import AdsPlatformOverviewCard from "../components/AdsPlatformOverviewCard";
import Breadcrumb from "../components/Breadcrumb";
import { StatusBadge } from "../components/Badges";
import { ADS_PLATFORMS } from "../lib/constants";
import { adsPeriodSlug, clientSlug } from "../lib/format";

export default function AdsPeriodDetailPage({ client, period, platformCatalog, onNavigate, onOpenPlatform, onUpdate }) {
  const configured = new Set(client.ads_platforms || client.ads_configuration?.platforms || ADS_PLATFORMS);
  return (
    <section className="view active">
      <Breadcrumb items={[{ label: "Clients", path: "/ads/clients" }, { label: client.client_name, path: `/ads/clients/${clientSlug(client)}` }, { label: period.period_label }]} onNavigate={onNavigate} />
      <div className="page-title-row">
        <div><h1>{period.period_label} Report</h1><p>Overview of paid media data availability for this reporting period.</p></div>
        <button className="secondary-button" type="button" disabled title="Ads report generation will be added after the reporting template is finalized">Generate report — coming soon</button>
      </div>
      <section className="upload-summary">
        <div><StatusBadge text={period.import_status === "success" ? "Report data imported" : "Missing data"} state={period.import_status === "success" ? "success" : "warning"} /><span>{period.uploaded_files || 0} Meta CSV files available</span></div>
        <button className="secondary-button" type="button" onClick={() => onUpdate(period)}>Update Data</button>
      </section>
      <div className="platform-overview-grid">
        {ADS_PLATFORMS.map((platform) => {
          const definition = platformCatalog.find((item) => item.key === platform);
          return <AdsPlatformOverviewCard key={platform} platform={platform} period={period} configured={configured.has(platform) && definition?.configured !== false} onOpen={() => onOpenPlatform(`${clientSlug(client)}/${adsPeriodSlug(period)}/${platform}`)} />;
        })}
      </div>
    </section>
  );
}
