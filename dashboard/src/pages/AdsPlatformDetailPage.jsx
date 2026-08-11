import { useEffect, useState } from "react";
import Breadcrumb from "../components/Breadcrumb";
import { PlatformBadge, StatusBadge } from "../components/Badges";
import { ADS_PLATFORM_SOURCES, PLATFORM_LABELS } from "../lib/constants";
import { adsPeriodSlug, clientSlug, formatCurrency, formatNumber } from "../lib/format";

function percentage(value) {
  return value === null || value === undefined ? "-" : formatNumber(value, "%");
}

function goalCards(goal) {
  const common = [
    [goal.label, formatNumber(goal.metrics.result_value)],
    ["Monthly Target", formatNumber(goal.targets.target_monthly)],
    ["Achievement", percentage(goal.achievement)],
    ["Amount Spent", formatCurrency(goal.metrics.spend)],
  ];
  if (goal.key === "reach") return [
    ...common,
    ["Cost / 1,000 Reached", formatCurrency(goal.metrics.cost_per_thousand_reached)],
    ["Frequency", formatNumber(goal.metrics.frequency)],
  ];
  if (goal.key === "engagement") return [
    ...common,
    ["Cost / Engagement", formatCurrency(goal.metrics.cost_per_result)],
    ["Engagement Rate", percentage(goal.metrics.engagement_rate)],
  ];
  if (goal.key === "profile_visits") return [
    ...common,
    ["Cost / Profile Visit", formatCurrency(goal.metrics.cost_per_result)],
    ["Visit to Follow", percentage(goal.metrics.visit_to_follow_rate)],
  ];
  return [
    ...common,
    ["Cost / Result", formatCurrency(goal.metrics.cost_per_result)],
    ["Budget Use", percentage(goal.budget_use)],
  ];
}

function PerformanceTable({ rows, resultLabel }) {
  if (!rows.length) return <div className="empty compact-empty">No performance rows match this goal.</div>;
  return (
    <div className="table-scroll"><table className="ads-detail-table"><thead><tr><th>Creative</th><th>{resultLabel}</th><th>Reach</th><th>Impressions</th><th>Engagements</th><th>Link Clicks</th><th>Spend</th></tr></thead><tbody>
      {rows.map((row) => <tr key={row.label}><td>{row.label}</td><td>{formatNumber(row.result_value)}</td><td>{formatNumber(row.reach)}</td><td>{formatNumber(row.impressions)}</td><td>{formatNumber(row.engagements)}</td><td>{formatNumber(row.link_clicks)}</td><td>{formatCurrency(row.spend)}</td></tr>)}
    </tbody></table></div>
  );
}

function BreakdownList({ rows, valueLabel = "Results" }) {
  if (!rows.length) return <div className="empty compact-empty">No breakdown data available.</div>;
  const maximum = Math.max(...rows.map((row) => Number(row.result_value || 0)), 1);
  return <div className="ads-ranking-list">{rows.map((row) => <div className="ads-ranking-row" key={`${row.label}-${row.age}-${row.gender}`}><div><strong>{row.label || `${row.age} · ${row.gender}`}</strong><small>{valueLabel}</small></div><div className="ads-ranking-bar"><span style={{ width: `${Math.max(3, Number(row.result_value || 0) / maximum * 100)}%` }} /></div><b>{formatNumber(row.result_value)}</b></div>)}</div>;
}

export default function AdsPlatformDetailPage({ client, period, platform, detail, onNavigate, onUpdate, onEditGoals }) {
  const [activeGoalKey, setActiveGoalKey] = useState("");
  const source = ADS_PLATFORM_SOURCES[platform];
  const available = detail?.data_status === "ready";
  const goals = detail?.goals || [];
  useEffect(() => {
    if (goals.length && !goals.some((goal) => goal.key === activeGoalKey)) setActiveGoalKey(goals[0].key);
  }, [goals, activeGoalKey]);
  const activeGoal = goals.find((goal) => goal.key === activeGoalKey) || goals[0];
  const configuredGoals = detail?.platform?.active_goals || period?.ads_configuration?.goals?.[platform] || [];

  return (
    <section className="view active">
      <Breadcrumb items={[{ label: "Clients", path: "/ads/clients" }, { label: client.client_name, path: `/ads/clients/${clientSlug(client)}` }, { label: period.period_label, path: `/ads/clients/${clientSlug(client)}/${adsPeriodSlug(period)}` }, { label: `${PLATFORM_LABELS[platform]} Ads` }]} onNavigate={onNavigate} />
      <div className="page-title-row">
        <div><div className="badge-row"><PlatformBadge platform={platform} /><StatusBadge text={available ? "Ready" : source?.available ? detail ? "Missing data" : "Loading" : "Coming soon"} state={available ? "success" : source?.available ? "warning" : "info"} /></div><h1>{PLATFORM_LABELS[platform]} Ads</h1><p>{period.period_label} · Source: {source?.label}</p></div>
        {source?.available && <button className="secondary-button" type="button" onClick={() => onUpdate(period)}>Update Data</button>}
      </div>

      {!detail ? <div className="empty"><h2>Loading platform performance...</h2></div> : detail.data_status === "not_configured" ? (
        <div className="empty"><h2>No {PLATFORM_LABELS[platform]} goal selected for {period.period_label}</h2><p>This platform is connected to the client, but it is not part of this month's Ads plan.</p><button className="primary-button" type="button" onClick={() => onEditGoals(period)}>Edit Goals &amp; KPI</button></div>
      ) : detail.data_status === "coming_soon" ? (
        <div className="empty ads-coming-soon"><PlatformBadge platform={platform} /><h2>{source?.label} connector is ready for the next phase</h2><p>The goal configuration and report sections are ready. Ingestion and performance tables will be connected after the real export is received.</p><div className="goal-chip-row">{configuredGoals.map((goal) => <span className="goal-chip" key={goal.key}>{goal.key.replaceAll("_", " ")}</span>)}</div></div>
      ) : detail.data_status !== "ready" ? (
        <div className="empty"><h2>No {PLATFORM_LABELS[platform]} Ads data for {period.period_label}</h2><p>Import the six Meta Ads CSV files to populate goal performance.</p></div>
      ) : (
        <>
          <div className="ads-goal-tabs" role="tablist" aria-label="Ads performance goals">{goals.map((goal) => <button type="button" role="tab" aria-selected={goal.key === activeGoal?.key} className={goal.key === activeGoal?.key ? "active" : ""} key={goal.key} onClick={() => setActiveGoalKey(goal.key)}><span>{goal.label}</span><small>{goal.family.replaceAll("_", " ")}</small></button>)}</div>
          {activeGoal && <>
            <section className="metric-grid ads-goal-metrics">{goalCards(activeGoal).map(([label, value]) => <article className="metric-card-container" key={label}><div className="metric-card"><div className="metric-label">{label}</div><div className="metric-value">{value}</div></div></article>)}</section>
            <section className="content-card ads-section-card"><div className="section-heading"><div><span className="eyebrow">Performance Overview</span><h2>{activeGoal.label} by Creative</h2></div><span className="source-note">Meta placement export</span></div><PerformanceTable rows={activeGoal.creatives || []} resultLabel={activeGoal.label} /></section>
            <div className="ads-analysis-grid">
              <section className="content-card ads-section-card"><div className="section-heading"><div><span className="eyebrow">Placement Analysis</span><h2>Top Placements</h2></div></div><BreakdownList rows={activeGoal.placements || []} valueLabel={activeGoal.label} /></section>
              <section className="content-card ads-section-card"><div className="section-heading"><div><span className="eyebrow">Audience Demographics</span><h2>Age and Gender</h2></div></div><BreakdownList rows={activeGoal.demographics || []} valueLabel={activeGoal.label} /><p className="data-caveat">Meta demographic exports do not include publisher platform, so this breakdown uses the shared Meta scope.</p></section>
              <section className="content-card ads-section-card"><div className="section-heading"><div><span className="eyebrow">Region Breakdown</span><h2>Top Regions</h2></div></div><BreakdownList rows={activeGoal.regions || []} valueLabel={activeGoal.region_metric === "link_clicks_proxy" ? "Link clicks proxy" : activeGoal.label} />{activeGoal.region_metric === "link_clicks_proxy" && <p className="data-caveat">Profile Visits are unavailable by region in Meta reporting. Link Clicks are shown as a proxy.</p>}</section>
              <section className="content-card ads-section-card"><div className="section-heading"><div><span className="eyebrow">Optimization Action</span><h2>What to do next</h2></div></div><ul className="ads-action-list"><li>{activeGoal.creatives?.[0] ? `Prioritize or retest “${activeGoal.creatives[0].label}”, the current top creative for ${activeGoal.label.toLowerCase()}.` : "Collect more delivery before selecting a winning creative."}</li><li>{activeGoal.placements?.[0] ? `Use ${activeGoal.placements[0].label} as the placement benchmark while monitoring cost efficiency.` : "Placement performance is not available yet."}</li><li>{activeGoal.achievement === null ? "Add a monthly KPI target to enable achievement tracking." : activeGoal.achievement >= 100 ? "Monthly KPI has been achieved; evaluate whether budget can scale efficiently." : "KPI is below target; review creative allocation and audience delivery."}</li><li>{activeGoal.budget_use === null ? "Add a monthly budget to enable pacing alerts." : activeGoal.budget_use > 100 ? "Monthly spend is over budget; review pacing before scaling." : "Monthly spend remains within the configured budget."}</li></ul></section>
            </div>
          </>}
        </>
      )}
    </section>
  );
}
