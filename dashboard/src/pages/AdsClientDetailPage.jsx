import { StatusBadge } from "../components/Badges";

export default function AdsClientDetailPage({ client, periods, onNavigate, onUpload }) {
  return (
    <section className="view active">
      <button className="text-link back-link" type="button" onClick={() => onNavigate("/ads/clients")}>← Ads Clients</button>
      <div className="page-title-row ads-detail-title">
        <div>
          <div className="eyebrow ads">Meta Ads workspace</div>
          <h1>{client.client_name}</h1>
          <p>Campaign data and import history are separate from Social Media reporting.</p>
        </div>
        <button className="primary-button" type="button" onClick={() => onUpload(null)}>+ Add Ads Data</button>
      </div>

      <div className="section-row ads-period-heading">
        <div>
          <h2>Reporting periods</h2>
          <p>Each period is one atomic snapshot of all six Meta Ads exports.</p>
        </div>
      </div>
      <div className="month-grid">
        {periods.length ? periods.map((period) => (
          <article className="month-card ads-period-card" key={period.id}>
            <div className="card-main">
              <div className="month-head">
                <div>
                  <div className="client-title">{period.period_label}</div>
                  <div className="client-code">{period.period_start} – {period.period_end}</div>
                </div>
                <StatusBadge
                  state={period.import_status === "success" ? "success" : "neutral"}
                  text={period.import_status || "No import"}
                />
              </div>
              <div className="ads-count-grid">
                <span><strong>{period.campaigns || 0}</strong> Campaigns</span>
                <span><strong>{period.adsets || 0}</strong> Ad sets</span>
                <span><strong>{period.ads || 0}</strong> Ads</span>
                <span><strong>{period.placements || 0}</strong> Placements</span>
                <span><strong>{period.demographics || 0}</strong> Demographics</span>
                <span><strong>{period.regions || 0}</strong> Regions</span>
              </div>
            </div>
            <div className="card-footer">
              <button className="secondary-button" type="button" onClick={() => onUpload(period)}>
                Replace CSV Snapshot
              </button>
            </div>
          </article>
        )) : <div className="empty">No Ads reporting periods yet. Upload the six CSV exports to begin.</div>}
      </div>
    </section>
  );
}
