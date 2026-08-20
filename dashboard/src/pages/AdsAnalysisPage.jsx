import { Fragment, useEffect, useMemo, useState } from "react";
import AdsPeriodNavigation from "../components/AdsPeriodNavigation";
import Breadcrumb from "../components/Breadcrumb";
import Modal, { ModalHeader } from "../components/Modal";
import { api } from "../lib/api";
import { adsPeriodSlug, clientSlug } from "../lib/format";

const titleCase = (value) => String(value || "").split("_").map((part) => part ? part[0].toUpperCase() + part.slice(1) : "").join(" ");
function filtersFromLocation() {
  const search = new URLSearchParams(window.location.search);
  const requestedPlatform = search.get("platform_scope");
  return {
    platform: ["meta", "instagram", "facebook"].includes(requestedPlatform) ? requestedPlatform : "meta",
    objective: search.get("objective") || "",
    campaign: search.get("campaign_ids") || "",
    adsets: (search.get("adset_ids") || "").split(",").map((value) => value.trim()).filter(Boolean),
  };
}
function formatMetric(value, format) {
  if (value === null || value === undefined) return "—";
  if (format === "currency") return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(value);
  if (format === "percentage") return `${new Intl.NumberFormat("id-ID", { maximumFractionDigits: 2 }).format(value)}%`;
  return new Intl.NumberFormat("id-ID", { maximumFractionDigits: format === "decimal" ? 2 : 0 }).format(value);
}

export default function AdsAnalysisPage({ client, period, dimension, refreshKey = 0, onNavigate, onReviewObjectives, onGoals, onMetrics, onSync, onImport, onSources }) {
  const initialFilters = useMemo(filtersFromLocation, []);
  const [platform, setPlatform] = useState(initialFilters.platform);
  const [objective, setObjective] = useState(initialFilters.objective);
  const [campaign, setCampaign] = useState(initialFilters.campaign);
  const [adsets, setAdsets] = useState(initialFilters.adsets);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState("");
  const [selectedCreative, setSelectedCreative] = useState(null);
  const endpoint = dimension === "creative" ? "creative-performance" : "adset-performance";
  const params = useMemo(() => new URLSearchParams({ platform_scope: platform, ...(objective ? { objective } : {}), ...(campaign ? { campaign_ids: campaign } : {}), ...(adsets.length ? { adset_ids: adsets.join(",") } : {}) }).toString(), [platform, objective, campaign, adsets]);
  useEffect(() => {
    setData(null); setError("");
    api(`/api/ads/clients/${client.id}/periods/${period.id}/${endpoint}?${params}`).then((response) => { setData(response); if (response.objective && response.objective !== objective) setObjective(response.objective); }).catch((err) => setError(err.message));
  }, [client.id, period.id, endpoint, params, refreshKey]);
  const base = `/ads/clients/${clientSlug(client)}/${adsPeriodSlug(period)}`;
  useEffect(() => {
    const nextUrl = `${window.location.pathname}${params ? `?${params}` : ""}`;
    const currentUrl = `${window.location.pathname}${window.location.search}`;
    if (nextUrl !== currentUrl) window.history.replaceState({}, "", nextUrl);
  }, [params]);
  const filters = data?.available_filters || { campaigns: [], adsets: [] };
  return <section className="view active ads-analysis-page">
    <Breadcrumb items={[{ label: "Clients", path: "/ads/clients" }, { label: client.client_name, path: `/ads/clients/${clientSlug(client)}` }, { label: period.period_label, path: base }, { label: dimension === "creative" ? "Creative Performance" : "Ad Set Performance" }]} onNavigate={onNavigate} />
    <div className="page-title-row"><div><span className="eyebrow ads">{period.period_label}</span><h1>{dimension === "creative" ? "Creative Performance" : "Ad Set Performance"}</h1><p>{dimension === "creative" ? "Compare Ads in their Campaign and Ad Set context." : "Compare Ad Sets and expand one to inspect its creatives."}</p></div></div>
    <AdsPeriodNavigation client={client} period={period} active={dimension === "creative" ? "creative" : "adsets"} search={`?${params}`} onNavigate={onNavigate} onReviewObjectives={onReviewObjectives} onGoals={onGoals} onMetrics={onMetrics} onSync={onSync} onImport={onImport} onSources={onSources} />
    <section className="analysis-filter-bar" aria-label="Analysis filters">
      <label><span>Platform</span><select value={platform} onChange={(event) => { setPlatform(event.target.value); setCampaign(""); setAdsets([]); }}><option value="meta">All Meta</option><option value="instagram">Instagram</option><option value="facebook">Facebook</option></select></label>
      <label><span>Objective</span><select value={objective} disabled={!data?.objectives?.length} onChange={(event) => { setObjective(event.target.value); setCampaign(""); setAdsets([]); }}>{!data?.objectives?.length && <option value="">Confirm objectives first</option>}{(data?.objectives || []).map((item) => <option key={item} value={item}>{titleCase(item)}</option>)}</select></label>
      <label><span>Campaign</span><select value={campaign} onChange={(event) => { setCampaign(event.target.value); setAdsets([]); }}><option value="">All Campaigns</option>{filters.campaigns.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label><span>Ad Sets</span><select multiple value={adsets} disabled={!filters.adsets.length} onChange={(event) => setAdsets([...event.target.selectedOptions].map((option) => option.value))}>{!filters.adsets.length && <option value="">No Ad Sets available</option>}{filters.adsets.filter((item) => !campaign || item.campaign_id === campaign).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    </section>
    {error && <div className="import-alert danger">{error}</div>}
    {!data && !error && <div className="empty">Loading performance...</div>}
    {data?.unconfirmed_count > 0 && <div className="import-alert warning"><strong>{data.unconfirmed_count} Campaign objectives need confirmation.</strong> Unconfirmed Campaigns are excluded from KPI and analysis. <button type="button" className="inline-action" onClick={onReviewObjectives}>Review now</button></div>}
    {(data?.warnings || []).map((warning) => <div className="import-alert warning" key={warning}>{warning}</div>)}
    {data?.data_status === "missing_data" && <div className="empty"><h2>No active Meta data</h2><p>Sync from Meta or import CSV for this period.</p><button type="button" className="primary-button" onClick={onSync}>Sync from Meta</button></div>}
    {data?.data_status === "source_mismatch" && <div className="empty"><h2>All Meta is unavailable</h2><p>Instagram and Facebook are using different active snapshots.</p><button type="button" className="secondary-button" onClick={onSources}>Manage data sources</button></div>}
    {data?.data_status === "needs_mapping" && <div className="empty"><h2>Confirm Campaign objectives first</h2><p>Only confirmed and included Campaigns appear in analysis.</p><button type="button" className="primary-button" onClick={onReviewObjectives}>Review Campaign objectives</button></div>}
    {data?.data_status === "ready" && <>
      {data.display_metrics.length ? <div className="analysis-metric-grid">{data.display_metrics.map((metric) => <article key={metric.key}><span>{metric.label}</span><strong>{formatMetric(data.summary?.[metric.key], metric.format)}</strong></article>)}</div> : <div className="empty compact-empty"><h2>No displayed metrics</h2><p>Choose metrics in Metric Display Settings.</p><button type="button" className="secondary-button" onClick={onMetrics}>Open settings</button></div>}
      <section className="content-card analysis-table-card"><div className="section-heading"><div><h2>{data.rows.length} {dimension === "creative" ? "Creatives" : "Ad Sets"}</h2><p>{titleCase(data.objective)} · {platform === "meta" ? "All Meta" : titleCase(platform)}</p></div><small>Source: {titleCase(data.source?.type)} · {data.source?.updated_at ? new Date(data.source.updated_at).toLocaleString("id-ID") : "—"}</small></div>
        <div className="table-scroll analysis-table-scroll"><table className="ads-detail-table analysis-table"><colgroup><col className="analysis-col-entity" /><col className="analysis-col-campaign" /><col className={dimension === "creative" ? "analysis-col-adset" : "analysis-col-count"} />{data.display_metrics.map((metric) => <col className="analysis-col-metric" key={metric.key} />)}</colgroup><thead><tr><th>{dimension === "creative" ? "Creative" : "Ad Set"}</th><th>Campaign</th>{dimension === "creative" && <th>Ad Set</th>}{dimension === "adset" && <th>Ads</th>}{data.display_metrics.map((metric) => <th key={metric.key}>{metric.label}</th>)}</tr></thead><tbody>{data.rows.map((row) => <Fragment key={row.id}><tr className="clickable-row" onClick={() => dimension === "adset" ? setExpanded(expanded === row.id ? "" : row.id) : setSelectedCreative(row)}><td><div className="entity-cell">{dimension === "creative" ? <CreativePreview src={row.thumbnail_url || row.image_url} /> : <span className="creative-placeholder">AS</span>}<span><strong>{row.name}</strong><small>{dimension === "adset" ? (expanded === row.id ? "Hide creatives" : "View creatives") : "View breakdown"}</small></span></div></td><td className="analysis-text-cell">{row.campaign_name}</td>{dimension === "creative" && <td className="analysis-text-cell">{row.adset_name || "—"}</td>}{dimension === "adset" && <td className="analysis-number-cell">{row.ads_count}</td>}{data.display_metrics.map((metric) => <td className="analysis-number-cell" key={metric.key}>{formatMetric(row.metrics?.[metric.key], metric.format)}</td>)}</tr>{dimension === "adset" && expanded === row.id && <tr className="drilldown-row"><td colSpan={3 + data.display_metrics.length}><AdSetDrilldown client={client} period={period} adsetId={row.id} platform={platform} objective={objective} /></td></tr>}</Fragment>)}</tbody></table></div>
      </section>
    </>}
    {selectedCreative && <CreativeDetailModal client={client} period={period} creative={selectedCreative} platform={platform} onClose={() => setSelectedCreative(null)} onSync={onSync} />}
  </section>;
}

function AdSetDrilldown({ client, period, adsetId, platform, objective }) {
  const [data, setData] = useState(null);
  useEffect(() => { const params = new URLSearchParams({ platform_scope: platform, objective }); api(`/api/ads/clients/${client.id}/periods/${period.id}/adsets/${encodeURIComponent(adsetId)}/creatives?${params}`).then(setData); }, [client.id, period.id, adsetId, platform, objective]);
  if (!data) return <div className="empty compact-empty">Loading creative breakdown...</div>;
  return <div className="drilldown-grid">{data.rows.length ? data.rows.map((row) => <article key={row.id}><CreativePreview src={row.thumbnail_url || row.image_url} large /><div><strong>{row.name}</strong><small>{data.display_metrics.slice(0, 3).map((metric) => `${metric.label}: ${formatMetric(row.metrics?.[metric.key], metric.format)}`).join(" · ")}</small></div></article>) : <div className="empty compact-empty">No creatives found for this Ad Set.</div>}</div>;
}

function CreativePreview({ src, large = false, showMessage = false, onSync }) {
  const [failed, setFailed] = useState(!src);
  if (failed) return <div className="creative-preview-fallback"><div className={`creative-placeholder ${large ? "large" : ""}`}>AD</div>{showMessage && <small>Preview unavailable. The Meta URL may have expired. <button type="button" className="inline-action" onClick={onSync}>Sync again</button></small>}</div>;
  return <img src={src} alt="Creative preview" onError={() => setFailed(true)} />;
}

function BreakdownTable({ title, rows, columns }) {
  return <section><h3>{title}</h3>{rows.length ? <div className="table-scroll"><table className="ads-detail-table compact-breakdown"><thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={`${title}-${index}`}>{columns.map((column) => <td key={column.key}>{column.metric ? formatMetric(row[column.key], "number") : row[column.key]}</td>)}</tr>)}</tbody></table></div> : <div className="empty compact-empty">Breakdown not available.</div>}</section>;
}

function CreativeDetailModal({ client, period, creative, platform, onClose, onSync }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api(`/api/ads/clients/${client.id}/periods/${period.id}/creatives/${encodeURIComponent(creative.id)}?platform_scope=${platform}`).then(setDetail).catch((err) => setError(err.message)); }, [client.id, period.id, creative.id, platform]);
  return <Modal onClose={onClose} wide><ModalHeader title={creative.name} subtitle={`${creative.campaign_name} · ${creative.adset_name || "No Ad Set"}`} onClose={onClose} /><div className="modal-body creative-detail-body">
    {error && <div className="import-alert danger">{error}</div>}
    {!detail && !error ? <div className="empty compact-empty">Loading Creative details...</div> : detail && <><div className="creative-detail-hero"><CreativePreview src={detail.creative.image_url || detail.creative.thumbnail_url} large showMessage onSync={() => { onClose(); onSync(); }} /><div><h3>{detail.creative.ad_name}</h3><p>{detail.creative.campaign_name}<br />{detail.creative.adset_name}</p>{detail.creative.permalink_url && <a href={detail.creative.permalink_url} target="_blank" rel="noreferrer">Open destination</a>}</div></div><div className="import-alert warning">{detail.caveat}</div><div className="creative-breakdown-grid"><BreakdownTable title="Placement" rows={detail.placements} columns={[{key:"publisher_platform",label:"Platform"},{key:"placement",label:"Placement"},{key:"device",label:"Device"},{key:"impressions",label:"Impressions",metric:true}]} /><BreakdownTable title="Age & Gender" rows={detail.demographics} columns={[{key:"age",label:"Age"},{key:"gender",label:"Gender"},{key:"impressions",label:"Impressions",metric:true}]} /><BreakdownTable title="Regions" rows={detail.regions} columns={[{key:"region",label:"Region"},{key:"impressions",label:"Impressions",metric:true}]} /></div></>}
    <div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>Close</button><button type="button" className="primary-button" onClick={onClose}>Done</button></div>
  </div></Modal>;
}
