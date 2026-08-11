import Breadcrumb from "../components/Breadcrumb";
import { PlatformBadge, StatusBadge } from "../components/Badges";
import { ADS_PLATFORM_SOURCES, PLATFORM_LABELS } from "../lib/constants";
import { adsPeriodSlug, clientSlug, formatNumber } from "../lib/format";

export default function AdsPlatformDetailPage({ client, period, platform, onNavigate, onUpdate }) {
  const source = ADS_PLATFORM_SOURCES[platform];
  const available = source?.available && period.import_status === "success";
  const metrics = source?.available ? [["Campaigns", period.campaigns], ["Ad Sets", period.adsets], ["Ads", period.ads], ["Placements", period.placements], ["Demographics", period.demographics], ["Regions", period.regions]] : [];
  return (
    <section className="view active">
      <Breadcrumb items={[{ label: "Clients", path: "/ads/clients" }, { label: client.client_name, path: `/ads/clients/${clientSlug(client)}` }, { label: period.period_label, path: `/ads/clients/${clientSlug(client)}/${adsPeriodSlug(period)}` }, { label: `${PLATFORM_LABELS[platform]} Ads` }]} onNavigate={onNavigate} />
      <div className="page-title-row">
        <div><div className="badge-row"><PlatformBadge platform={platform} /><StatusBadge text={available ? "Ready" : source?.available ? "Missing data" : "Coming soon"} state={available ? "success" : source?.available ? "warning" : "info"} /></div><h1>{PLATFORM_LABELS[platform]} Ads</h1><p>{period.period_label} · Source: {source?.label}</p></div>
        {source?.available && <button className="secondary-button" type="button" onClick={() => onUpdate(period)}>Update Data</button>}
      </div>
      {source?.available ? (
        <><div className="metric-grid ads-platform-metrics">{metrics.map(([label, value]) => <article className="metric-card-container" key={label}><div className="metric-card"><div className="metric-label">{label}</div><div className="metric-value">{formatNumber(value)}</div></div></article>)}</div><div className="import-alert">Instagram and Facebook currently use the shared Meta Ads snapshot. Platform-specific reporting will use placement/platform dimensions without inventing campaign lineage.</div></>
      ) : (
        <div className="empty ads-coming-soon"><PlatformBadge platform={platform} /><h2>{source?.label} connector is ready for the next phase</h2><p>The frontend route and backend platform contract are available, but ingestion endpoints and performance tables have intentionally not been created until the real export is received.</p></div>
      )}
    </section>
  );
}
