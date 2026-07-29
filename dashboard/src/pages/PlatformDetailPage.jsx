import { useState } from "react";
import Breadcrumb from "../components/Breadcrumb";
import CompetitorTable from "../components/CompetitorTable";
import KpiTable from "../components/KpiTable";
import MetricCards from "../components/MetricCards";
import MissingDataModal from "../components/MissingDataModal";
import PostList from "../components/PostList";
import { PLATFORM_LABELS } from "../lib/constants";
import { clientSlug } from "../lib/format";

export default function PlatformDetailPage({
  client,
  month,
  platform,
  data,
  onNavigate,
  onOpenReportKpi,
  onEditKpi,
  onOpenEditor,
}) {
  const [showMissingData, setShowMissingData] = useState(false);
  const report = data?.report || {};
  const missingData = data?.missing_data || {
    items: [{ field: "data_check", label: "Data completeness check is unavailable. Restart the dashboard backend." }],
    missing_count: 1,
    status: "unknown",
  };
  const hasMissingData = (missingData.missing_count || 0) > 0;

  return (
    <section className="view active">
      <Breadcrumb
        items={[
          { label: "Clients", path: "/clients" },
          { label: client.client_name, path: `/clients/${clientSlug(client)}` },
          { label: month.label, path: `/clients/${clientSlug(client)}/${month.slug}` },
          { label: PLATFORM_LABELS[platform] },
        ]}
        onNavigate={onNavigate}
      />
      <div className="page-title-row">
        <div>
          <h1>{PLATFORM_LABELS[platform]} Overview</h1>
          <p>Performance summary, KPI results, and top content for {month.label}.</p>
        </div>
        <div className="page-actions">
          <button className="secondary-button" onClick={onOpenEditor}>
            Edit report data
          </button>
          <button
            className={`secondary-button data-check-button ${hasMissingData ? "has-missing" : ""}`}
            onClick={() => setShowMissingData(true)}
          >
            {hasMissingData ? `${missingData.missing_count} Missing Fields` : "Data Complete"}
          </button>
          <button className="primary-button" onClick={onOpenReportKpi}>Update KPI Targets</button>
        </div>
      </div>
      {showMissingData && (
        <MissingDataModal
          platformLabel={PLATFORM_LABELS[platform]}
          missingData={missingData}
          onClose={() => setShowMissingData(false)}
        />
      )}
      <MetricCards metrics={data?.metrics || []} />
      <section className="content-section">
        <h2>KPI Results</h2>
        <KpiTable platform={platform} rows={data?.kpi_results || []} onEdit={onEditKpi} />
      </section>
      <div className="two-column">
        <section className="content-section">
          <h2>Top Performing Content</h2>
          <PostList posts={data?.top_posts || []} />
        </section>
        <section className="content-section">
          <h2>Low Performing Content</h2>
          <PostList posts={data?.low_posts || []} />
        </section>
      </div>
      <section className="content-section">
        <h2>Competitor Summary</h2>
        <CompetitorTable rows={data?.competitor_profiles || report.competitor_profiles || []} />
      </section>
    </section>
  );
}
