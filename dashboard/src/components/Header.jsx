export default function Header({ activeSection, workspace, onNavigate }) {
  const isAds = workspace === "ads";
  const homePath = isAds ? "/ads/clients" : "/social/clients";
  const title = workspace
    ? `MAI ${isAds ? "Meta Ads" : "Social Media"} Dashboard`
    : "MAI Reporting";
  return (
    <header className="app-header">
      <button
        type="button"
        className="brand-title"
        onClick={() => onNavigate(workspace ? homePath : "/")}
      >
        {title}
      </button>
      <nav className="header-navigation" aria-label="Main navigation">
        {workspace && (
          <>
            <button
              type="button"
              className={activeSection === "clients" ? "active" : ""}
              onClick={() => onNavigate(homePath)}
            >
              Clients
            </button>
            {!isAds && (
              <button
                type="button"
                className={activeSection === "report-jobs" ? "active" : ""}
                onClick={() => onNavigate("/social/report-jobs")}
              >
                Report Queue
              </button>
            )}
            <button type="button" onClick={() => onNavigate("/")}>Switch Workspace</button>
          </>
        )}
      </nav>
    </header>
  );
}
