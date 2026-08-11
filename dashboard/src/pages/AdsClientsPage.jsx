import { PlatformBadges } from "../components/Badges";
import OpenIconButton from "../components/OpenIconButton";
import { adsPlatformFlags } from "../lib/format";

export default function AdsClientsPage({
  clients,
  query,
  industry,
  industries,
  onQueryChange,
  onIndustryChange,
  onOpenClient,
  onOpenAddClient,
  onEditClient,
  onDeleteClient,
}) {
  const filtered = clients.filter((client) => {
    const matchesQuery = !query || client.client_name.toLowerCase().includes(query.toLowerCase());
    const matchesIndustry = !industry || client.industry === industry;
    return matchesQuery && matchesIndustry;
  });

  return (
    <section className="view active">
      <div className="hero-copy">
        <div className="eyebrow ads">Ads workspace</div>
        <h1>Ads Clients</h1>
        <p>Select a client to view paid media platforms, reporting periods, and Ads data.</p>
      </div>
      <div className="toolbar">
        <div className="toolbar-controls">
          <input className="search-input" placeholder="Search Ads clients" value={query} onChange={(event) => onQueryChange(event.target.value)} />
          <select className="filter-select" value={industry} onChange={(event) => onIndustryChange(event.target.value)}>
            <option value="">All industries</option>
            {industries.map((item) => <option value={item} key={item}>{item}</option>)}
          </select>
        </div>
        <button className="primary-button" onClick={onOpenAddClient}>+ Add New Client</button>
      </div>
      <div className="list-count">{filtered.length} Ads clients</div>
      <div className="client-grid">
        {filtered.length ? filtered.map((client) => {
          const platforms = adsPlatformFlags(client);
          return (
            <article className="client-card ads-client-card" key={client.id}>
              <div className="card-main">
                <div className="client-head">
                  <div><div className="client-title">{client.client_name}</div><div className="client-code">{client.client_code}</div></div>
                  <OpenIconButton label={`Open ${client.client_name}`} onClick={() => onOpenClient(client.id)} />
                </div>
                <PlatformBadges platforms={platforms} />
                <div className="client-meta"><span>{platforms.length} connected platforms</span><span>{client.industry || "No industry"}</span></div>
              </div>
              <div className="card-footer">
                <button className="text-link client-footer-link" type="button" onClick={() => onEditClient(client)}>Edit</button>
                <button className="danger-button" type="button" onClick={() => onDeleteClient(client)}>{(client.products || []).includes("social_media") ? "Remove" : "Delete"}</button>
              </div>
            </article>
          );
        }) : <div className="empty">No Ads clients found.</div>}
      </div>
    </section>
  );
}
