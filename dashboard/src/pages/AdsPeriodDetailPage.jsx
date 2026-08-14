import AdsPlatformOverviewCard from "../components/AdsPlatformOverviewCard";
import Breadcrumb from "../components/Breadcrumb";
import { StatusBadge } from "../components/Badges";
import { ADS_PLATFORMS } from "../lib/constants";
import { adsPeriodSlug, clientSlug, formatCurrency, formatNumber } from "../lib/format";

function OverviewTable({ rows, cumulative = false }) {
  const actualKey = cumulative ? "actual_total" : "actual_monthly";
  const targetKey = cumulative ? "target_total" : "target_monthly";
  const achievementKey = cumulative ? "achievement_total" : "achievement_monthly";
  const budgetKey = cumulative ? "budget_total" : "budget_monthly";
  const spendKey = cumulative ? "spend_total" : "spend_monthly";
  const budgetUseKey = cumulative ? "budget_use_total" : "budget_use_monthly";
  return <div className="table-scroll"><table className="ads-detail-table ads-overview-table"><thead><tr><th>Channel / Goal</th><th>Target</th><th>Actual</th><th>Achievement</th><th>Budget</th><th>Spend</th><th>Budget Use</th></tr></thead><tbody>{rows.map((row) => <tr key={`${row.platform}-${row.goal_key}`}><td><strong>{row.platform_label} · {row.goal_label}</strong><small>{row.status === "coming_soon" ? "Coming soon" : row.status === "missing_data" ? "Missing data" : "Ready"}</small></td><td>{formatNumber(row[targetKey])}</td><td>{formatNumber(row[actualKey])}</td><td>{row[achievementKey] === null ? "-" : formatNumber(row[achievementKey], "%")}</td><td>{formatCurrency(row[budgetKey])}</td><td>{formatCurrency(row[spendKey])}</td><td>{row[budgetUseKey] === null ? "-" : formatNumber(row[budgetUseKey], "%")}</td></tr>)}</tbody></table></div>;
}

export default function AdsPeriodDetailPage({ client, period, platformCatalog, overview, onNavigate, onOpenPlatform, onUpdate, onSync, onEditGoals }) {
  const configured = new Set(client.ads_platforms || client.ads_configuration?.platforms || ADS_PLATFORMS);
  const monthlyCatalog = period.platform_catalog || platformCatalog;
  return (
    <section className="view active">
      <Breadcrumb items={[{ label: "Clients", path: "/ads/clients" }, { label: client.client_name, path: `/ads/clients/${clientSlug(client)}` }, { label: period.period_label }]} onNavigate={onNavigate} />
      <div className="page-title-row">
        <div><h1>{period.period_label} Report</h1><p>Overview of paid media data availability for this reporting period.</p></div>
        <div className="page-actions"><button className="secondary-button" type="button" onClick={() => onEditGoals(period)}>Edit Goals &amp; KPI</button><button className="secondary-button" type="button" disabled title="Ads report generation will be added after the reporting template is finalized">Generate report — coming soon</button></div>
      </div>
      <section className="upload-summary">
        <div><StatusBadge text={period.import_status === "success" ? "Report data imported" : "Missing data"} state={period.import_status === "success" ? "success" : "warning"} /><span>{period.uploaded_files || 0} Meta CSV files available</span></div>
        <div className="page-actions"><button className="secondary-button" type="button" onClick={() => onUpdate(period)}>Import CSV</button><button className="primary-button" type="button" onClick={() => onSync(period)}>Sync from Meta</button></div>
      </section>
      <div className="ads-period-overviews">
        <section className="content-card ads-section-card"><div className="section-heading"><div><span className="eyebrow">Campaign Overview</span><h2>Campaign to Date</h2></div><span className="source-note">Through {period.period_label}</span></div>{overview ? <OverviewTable rows={overview.rows || []} cumulative /> : <div className="empty compact-empty">Loading campaign totals...</div>}</section>
        <section className="content-card ads-section-card"><div className="section-heading"><div><span className="eyebrow">Monthly Overview</span><h2>{period.period_label}</h2></div><span className="source-note">KPI and budget pacing</span></div>{overview ? <OverviewTable rows={overview.rows || []} /> : <div className="empty compact-empty">Loading monthly performance...</div>}</section>
      </div>
      <div className="platform-overview-grid">
        {ADS_PLATFORMS.map((platform) => {
          const definition = monthlyCatalog.find((item) => item.key === platform);
          return <AdsPlatformOverviewCard key={platform} platform={platform} period={period} definition={definition} configured={configured.has(platform) && definition?.configured !== false} onOpen={() => onOpenPlatform(`${clientSlug(client)}/${adsPeriodSlug(period)}/${platform}`)} />;
        })}
      </div>
    </section>
  );
}
