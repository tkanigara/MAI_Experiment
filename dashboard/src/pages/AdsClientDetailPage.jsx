import AdsMonthCard from "../components/AdsMonthCard";
import Breadcrumb from "../components/Breadcrumb";
import { PlatformBadges } from "../components/Badges";
import { adsPeriodSlug, adsPlatformFlags } from "../lib/format";

export default function AdsClientDetailPage({ client, periods, onNavigate, onUpload, onSync, onOpenPeriod, onEditClient, onEditGoals, onDeleteClient, onDeletePeriod }) {
  const platforms = adsPlatformFlags(client);
  const latestReport = periods[0]?.period_label || "-";
  return (
    <section className="view active">
      <Breadcrumb items={[{ label: "Clients", path: "/ads/clients" }, { label: client.client_name }]} onNavigate={onNavigate} />
      <div className="page-title-row">
        <div><h1>{client.client_name}</h1><p>Manage paid media report data and connected Ads platforms.</p></div>
        <div className="page-actions">
          <button className="secondary-button" type="button" onClick={() => onEditClient(client)}>Edit Client</button>
          <button className="danger-button" type="button" onClick={() => onDeleteClient(client)}>{(client.products || []).includes("social_media") ? "Remove from Ads" : "Delete Client"}</button>
        </div>
      </div>
      <section className="summary-strip">
        <div className="summary-item"><div className="summary-label">Industry</div><div className="summary-value">{client.industry || "-"}</div></div>
        <div className="summary-item"><div className="summary-label">Connected Platforms</div><PlatformBadges platforms={platforms} /></div>
        <div className="summary-item"><div className="summary-label">Report Months</div><div className="summary-value">{periods.length} configured</div></div>
        <div className="summary-item"><div className="summary-label">Latest Report</div><div className="summary-value">{latestReport}</div></div>
      </section>
      <div className="section-row">
        <div><h2>Report Months</h2><p>Select a report month to view performance for each connected Ads platform.</p></div>
        <div className="page-actions"><button className="secondary-button" type="button" onClick={() => onSync(null)}>Sync New Month from Meta</button><button className="primary-button" type="button" onClick={() => onUpload(null)}>Import CSV for New Month</button></div>
      </div>
      <div className="month-grid">
        {periods.length ? periods.map((period) => (
          <AdsMonthCard key={period.id} period={period} platforms={platforms} onOpen={() => onOpenPeriod(adsPeriodSlug(period))} onUpdate={onUpload} onSync={onSync} onEditGoals={onEditGoals} onDelete={onDeletePeriod} />
        )) : <div className="empty report-empty">No Ads report data has been imported for this client yet. Add report data to create the first report month.</div>}
      </div>
    </section>
  );
}
