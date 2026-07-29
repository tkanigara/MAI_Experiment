import ClientCard from "../components/ClientCard";

export default function ClientsPage({
  clients,
  industries,
  query,
  industry,
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
        <h1>Clients</h1>
        <p>Select a client to view connected social media platforms and report overview.</p>
      </div>
      <div className="toolbar">
        <div className="toolbar-controls">
          <input className="search-input" placeholder="Search clients" value={query} onChange={(event) => onQueryChange(event.target.value)} />
          <select className="filter-select" value={industry} onChange={(event) => onIndustryChange(event.target.value)}>
            <option value="">All industries</option>
            {industries.map((item) => <option value={item} key={item}>{item}</option>)}
          </select>
        </div>
        <button className="primary-button" onClick={onOpenAddClient}>+ Add New Client</button>
      </div>
      <div className="list-count">{filtered.length} clients</div>
      <div className="client-grid">
        {filtered.length
          ? filtered.map((client) => (
            <ClientCard
              key={client.id}
              client={client}
              onOpen={onOpenClient}
              onEdit={onEditClient}
              onDelete={onDeleteClient}
            />
          ))
          : <div className="empty">No clients found.</div>}
      </div>
    </section>
  );
}
