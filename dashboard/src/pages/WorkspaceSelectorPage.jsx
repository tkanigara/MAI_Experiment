export default function WorkspaceSelectorPage({ counts, onNavigate }) {
  const workspaces = [
    {
      key: "social_media",
      title: "Social Media",
      description: "Organic social performance, content, competitors, KPI, and social media reports.",
      path: "/social/clients",
      accent: "social",
    },
    {
      key: "meta_ads",
      title: "Ads",
      description: "Paid media reporting for Instagram, Facebook, YouTube, and TikTok Ads.",
      path: "/ads/clients",
      accent: "ads",
    },
  ];

  return (
    <section className="view active workspace-view">
      <div className="hero-copy workspace-hero">
        <div className="eyebrow">MAI Reporting</div>
        <h1>Choose a workspace</h1>
        <p>Social Media and Ads have separate clients, data periods, and report workflows.</p>
      </div>
      <div className="workspace-grid">
        {workspaces.map((workspace) => (
          <button
            type="button"
            className={`workspace-card ${workspace.accent}`}
            key={workspace.key}
            onClick={() => onNavigate(workspace.path)}
          >
            <span className="workspace-card-kicker">Workspace</span>
            <strong>{workspace.title}</strong>
            <span className="workspace-card-description">{workspace.description}</span>
            <span className="workspace-card-footer">
              {counts?.[workspace.key] || 0} clients
              <span aria-hidden="true">→</span>
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
