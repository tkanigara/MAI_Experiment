import { useEffect, useState } from "react";
import AdsPeriodNavigation from "../components/AdsPeriodNavigation";
import AdsPlatformOverviewCard from "../components/AdsPlatformOverviewCard";
import Breadcrumb from "../components/Breadcrumb";
import { StatusBadge } from "../components/Badges";
import { api } from "../lib/api";
import { ADS_PLATFORMS } from "../lib/constants";
import { adsPeriodSlug, clientSlug, formatCurrency, formatNumber } from "../lib/format";

function OverviewTable({ rows, cumulative = false }) {
  const actualKey = cumulative ? "actual_total" : "actual_monthly";
  const targetKey = cumulative ? "target_total" : "target_monthly";
  const achievementKey = cumulative ? "achievement_total" : "achievement_monthly";
  const budgetKey = cumulative ? "budget_total" : "budget_monthly";
  const spendKey = cumulative ? "spend_total" : "spend_monthly";
  const budgetUseKey = cumulative ? "budget_use_total" : "budget_use_monthly";
  return <div className="table-scroll"><table className="ads-detail-table ads-overview-table"><thead><tr><th>Channel / Objective</th><th>Target</th><th>Actual</th><th>Achievement</th><th>Budget</th><th>Spend</th><th>Budget Use</th></tr></thead><tbody>{rows.map((row) => <tr key={`${row.platform}-${row.goal_key}`}><td><strong>{row.platform_label} · {row.goal_label}</strong><small>{row.status === "coming_soon" ? "Coming soon" : row.status === "missing_data" ? "Missing data" : "Ready"}</small></td><td>{formatNumber(row[targetKey])}</td><td>{formatNumber(row[actualKey])}</td><td>{row[achievementKey] == null ? "—" : formatNumber(row[achievementKey], "%")}</td><td>{formatCurrency(row[budgetKey])}</td><td>{formatCurrency(row[spendKey])}</td><td>{row[budgetUseKey] == null ? "—" : formatNumber(row[budgetUseKey], "%")}</td></tr>)}</tbody></table></div>;
}

export default function AdsPeriodDetailPage({ client, period, platformCatalog, overview, onNavigate, onOpenPlatform, onUpdate, onSync, onGenerateReport, onEditGoals, onReviewObjectives, onMetricSettings, onSources }) {
  const configured = new Set(client.ads_platforms || client.ads_configuration?.platforms || ADS_PLATFORMS);
  const monthlyCatalog = period.platform_catalog || platformCatalog;
  const [mapping, setMapping] = useState(null);
  useEffect(() => { api(`/api/ads/clients/${client.id}/periods/${period.id}/campaign-mappings`).then(setMapping).catch(() => setMapping({ campaigns: [], unconfirmed_count: 0 })); }, [client.id, period.id]);
  const accounts = (client.meta_ad_accounts || []).filter((account) => (period.selected_ad_account_ids || []).includes(account.id)).map((account) => `${account.name} (${account.id})`);
  const base = `/ads/clients/${clientSlug(client)}/${adsPeriodSlug(period)}`;
  return <section className="view active">
    <Breadcrumb items={[{ label: "Clients", path: "/ads/clients" }, { label: client.client_name, path: `/ads/clients/${clientSlug(client)}` }, { label: period.period_label }]} onNavigate={onNavigate} />
    <div className="page-title-row"><div><span className="eyebrow ads">Reporting period</span><h1>{period.period_label}</h1><p>Choose an analysis model, review objectives, and monitor the active data snapshot.</p></div><div className="page-actions"><button className="secondary-button" type="button" onClick={() => onGenerateReport?.(period)}>Generate report</button><button className="primary-button" type="button" onClick={() => onSync(period)}>Sync from Meta</button></div></div>
    <AdsPeriodNavigation client={client} period={period} active="overview" onNavigate={onNavigate} onReviewObjectives={onReviewObjectives} onGoals={() => onEditGoals(period)} onMetrics={onMetricSettings} onSync={() => onSync(period)} onImport={() => onUpdate(period)} onSources={onSources} />
    <section className="upload-summary source-summary"><div><StatusBadge text={period.import_status === "success" ? "Active data ready" : "Missing data"} state={period.import_status === "success" ? "success" : "warning"} /><span><strong>{period.active_source === "api" ? "Meta API" : period.active_source === "csv" ? "CSV import" : "No active source"}</strong>{period.sync_completed_at || period.imported_at ? ` · Updated ${new Date(period.sync_completed_at || period.imported_at).toLocaleString("id-ID")}` : ""}<small>{accounts.length ? accounts.join(", ") : "No Ad Account recorded for this snapshot"}</small></span></div><button className="secondary-button" type="button" onClick={onSources}>Data Sources</button></section>
    {mapping?.unconfirmed_count > 0 && <div className="import-alert warning"><strong>{mapping.unconfirmed_count} Campaign objectives need confirmation.</strong> They remain outside KPI and analysis until reviewed. <button type="button" className="inline-action" onClick={onReviewObjectives}>Review Campaigns</button></div>}
    <div className="analysis-choice-grid"><button type="button" onClick={() => onNavigate(`${base}/creative`)}><span className="eyebrow ads">Analyze by Ad</span><strong>Creative Performance</strong><small>Compare creatives while keeping Campaign and Ad Set context.</small><span>Open analysis →</span></button><button type="button" onClick={() => onNavigate(`${base}/adsets`)}><span className="eyebrow ads">Analyze by Ad Set</span><strong>Ad Set Performance</strong><small>Compare targeting groups, then expand to their creatives.</small><span>Open analysis →</span></button></div>
    <div className="ads-period-overviews"><section className="content-card ads-section-card"><div className="section-heading"><div><span className="eyebrow">Campaign Overview</span><h2>Campaign to Date</h2></div><span className="source-note">Through {period.period_label}</span></div>{overview ? <OverviewTable rows={overview.rows || []} cumulative /> : <div className="empty compact-empty">Loading campaign totals...</div>}</section><section className="content-card ads-section-card"><div className="section-heading"><div><span className="eyebrow">Monthly Overview</span><h2>{period.period_label}</h2></div><span className="source-note">KPI and budget pacing</span></div>{overview ? <OverviewTable rows={overview.rows || []} /> : <div className="empty compact-empty">Loading monthly performance...</div>}</section></div>
    <div className="platform-overview-grid">{ADS_PLATFORMS.map((platform) => { const definition = monthlyCatalog.find((item) => item.key === platform); return <AdsPlatformOverviewCard key={platform} platform={platform} period={period} definition={definition} configured={configured.has(platform) && definition?.configured !== false} onOpen={() => onOpenPlatform(`${clientSlug(client)}/${adsPeriodSlug(period)}/${platform}`)} />; })}</div>
  </section>;
}
