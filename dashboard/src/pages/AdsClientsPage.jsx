import OpenIconButton from "../components/OpenIconButton";

export default function AdsClientsPage({
  clients,
  query,
  industry,
  industries,
  onQueryChange,
  onIndustryChange,
  onOpenClient,
  onOpenAddClient,
}) {
  const filtered = clients.filter((client) => {
    const matchesQuery = !query || client.client_name.toLowerCase().includes(query.toLowerCase());
    const matchesIndustry = !industry || client.industry === industry;
    return matchesQuery && matchesIndustry;
  });

  return (
    <section className="view active">
      <div className="hero-copy">
        <div className="eyebrow ads">Meta Ads workspace</div>
        <h1>Ads Clients</h1>
        <p>Clients enabled for paid campaign ingestion and Meta Ads reporting.</p>
      </div>
      <div className="toolbar">
        <div className="toolbar-controls">
          <input className="search-input" placeholder="Search Ads clients" value={query} onChange={(event) => onQueryChange(event.target.value)} />
          <select className="filter-select" value={industry} onChange={(event) => onIndustryChange(event.target.value)}>
            <option value="">All industries</option>
            {industries.map((item) => <option value={item} key={item}>{item}</option>)}
          </select>
        </div>
        <button className="primary-button" onClick={onOpenAddClient}>+ Add Ads Client</button>
      </div>
      <div className="list-count">{filtered.length} Ads clients</div>
      <div className="client-grid">
        {filtered.length ? filtered.map((client) => (
          <article className="client-card ads-client-card" key={client.id}>
            <div className="card-main">
              <div className="client-head">
                <div>
                  <div className="client-title">{client.client_name}</div>
                  <div className="client-code">{client.client_code}</div>
                </div>
                <OpenIconButton label={`Open ${client.client_name}`} onClick={() => onOpenClient(client.id)} />
              </div>
              <div className="product-badge ads">Meta Ads</div>
              <div className="client-meta">
                <span>{client.industry || "No industry"}</span>
                <span>Independent Ads reports</span>
              </div>
            </div>
            <div className="card-footer">
              <button className="secondary-button" type="button" onClick={() => onOpenClient(client.id)}>
                Open Ads Data
              </button>
            </div>
          </article>
        )) : <div className="empty">No Meta Ads clients found.</div>}
      </div>
    </section>
  );
}
