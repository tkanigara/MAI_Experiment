import Breadcrumb from "../components/Breadcrumb";
import MonthCard from "../components/MonthCard";
import { PlatformBadges } from "../components/Badges";
import { clientSlug, platformFlags } from "../lib/format";

export default function ClientDetailPage({
  client,
  profiles,
  reportMonths,
  onNavigate,
  onOpenMonth,
  onOpenAddReport,
  onOpenKpiTargets,
  onDeleteClient,
  onGenerateReport,
  generatingReportId,
}) {
  const platforms = platformFlags(client);
  const profileCount = Math.max(profiles.length, platforms.length, client.connected_profiles || 0);
  const latestReport = reportMonths[0]?.label || "-";
  return (
    <section className="view active">
      <Breadcrumb
        items={[{ label: "Clients", path: "/clients" }, { label: client.client_name }]}
        onNavigate={onNavigate}
      />
      <div className="page-title-row">
        <div>
          <h1>{client.client_name}</h1>
          <p>Manage monthly report data and connected social media platforms.</p>
        </div>
        <button className="danger-button" type="button" onClick={() => onDeleteClient(client)}>
          Delete Client
        </button>
      </div>
      <section className="summary-strip">
        <div className="summary-item">
          <div className="summary-label">Industry</div>
          <div className="summary-value">{client.industry || "-"}</div>
        </div>
        <div className="summary-item">
          <div className="summary-label">Connected Platforms</div>
          <PlatformBadges platforms={platforms} />
        </div>
        <div className="summary-item">
          <div className="summary-label">Profiles</div>
          <div className="summary-value">{profileCount} connected</div>
        </div>
        <div className="summary-item">
          <div className="summary-label">Latest Report</div>
          <div className="summary-value">{latestReport}</div>
        </div>
      </section>
      <div className="section-row">
        <div>
          <h2>Report Months</h2>
          <p>Select a report month to view platform performance overview.</p>
        </div>
        <div className="page-actions">
          <button className="secondary-button" onClick={onOpenKpiTargets}>Manage KPI Targets</button>
          <button className="primary-button" onClick={onOpenAddReport}>Add Report Data</button>
        </div>
      </div>
      {reportMonths.length ? (
        <div className="month-grid">
          {reportMonths.map((month) => (
            <MonthCard
              key={month.slug}
              month={month}
              platforms={platforms}
              onOpen={(slug) => onOpenMonth(`${clientSlug(client)}/${slug}`)}
              onGenerateReport={onGenerateReport}
              isGenerating={generatingReportId === month.id}
            />
          ))}
        </div>
      ) : (
        <div className="empty report-empty">
          No report data has been imported for this client yet. Add report data to create the first report month.
        </div>
      )}
    </section>
  );
}
