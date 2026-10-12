import { useEffect, useRef, useState } from "react";

function MenuItem({ title, description, ...props }) {
  return (
    <button role="menuitem" type="button" {...props}>
      <span className="menu-item-title">{title}</span>
      {description && <span className="menu-item-description">{description}</span>}
    </button>
  );
}

function HeaderMenu({ label, panelLabel, icon, className = "", children }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const close = (event) => {
      if (event.key === "Escape" || (event.type === "mousedown" && !ref.current?.contains(event.target))) setOpen(false);
    };
    document.addEventListener("keydown", close);
    document.addEventListener("mousedown", close);
    return () => {
      document.removeEventListener("keydown", close);
      document.removeEventListener("mousedown", close);
    };
  }, []);
  return <div className={`header-menu ${className}`.trim()} ref={ref}>
    <button className="menu-trigger" type="button" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
      {icon}
      <span>{label}</span>
      <span className="dropdown-chevron" aria-hidden="true" />
    </button>
    {open && <div className="header-menu-panel menu-panel" role="menu" aria-label={panelLabel || label} onClick={() => setOpen(false)}>
      {panelLabel && <div className="menu-panel-label" role="presentation">{panelLabel}</div>}
      {children}
    </div>}
  </div>;
}

export default function Header({ activeSection, workspace, currentClient, onNavigate, onOpenMetricSettings, user, onSignOut }) {
  const isAds = workspace === "ads";
  const homePath = isAds ? "/ads/clients" : "/social/clients";
  const title = workspace
    ? `MAI ${isAds ? "Ads" : "Social Media"} Dashboard`
    : "MAI Reporting";
  const clientPath = currentClient ? `${homePath}/${currentClient.client_code || currentClient.id}` : homePath;
  return (
    <header className="app-header">
      <button type="button" className="brand-title" onClick={() => onNavigate(workspace ? homePath : "/")}>
        {title}
      </button>
      <nav className="header-navigation" aria-label="Main navigation">
        {workspace && (
          <>
            <button type="button" className={activeSection === "clients" ? "active" : ""} onClick={() => onNavigate(homePath)}>
              Clients
            </button>
            {currentClient && <HeaderMenu label={currentClient.client_name} panelLabel={currentClient.client_name}>
              <MenuItem title="Client Overview" description="View platforms and reporting periods" onClick={() => onNavigate(clientPath)} />
              <MenuItem title="Report Months" description="Open this client's monthly reports" onClick={() => onNavigate(clientPath)} />
              {isAds && <MenuItem title="Metric Display Settings" description="Choose metrics shown across reports" onClick={onOpenMetricSettings} />}
            </HeaderMenu>}
            <button
              type="button"
              className={activeSection === "report-jobs" ? "active" : ""}
              onClick={() => onNavigate(`/${isAds ? "ads" : "social"}/report-jobs`)}
            >
              Report Queue
            </button>
            <HeaderMenu label="Workspace" panelLabel="Switch workspace">
              <MenuItem title="Ads" description="Paid campaign reporting" onClick={() => onNavigate("/ads/clients")} />
              <MenuItem title="Social Media" description="Organic content reporting" onClick={() => onNavigate("/social/clients")} />
            </HeaderMenu>
          </>
        )}
        {user && <HeaderMenu
          className="user-menu"
          label={user.name?.split(" ")[0] || "Account"}
          panelLabel="Signed in account"
          icon={user.picture
            ? <img className="header-user-avatar" src={user.picture} alt="" referrerPolicy="no-referrer" />
            : <span className="header-user-avatar fallback" aria-hidden="true">{(user.name || user.email || "M").slice(0, 1).toUpperCase()}</span>}
        >
          <div className="user-menu-identity" role="presentation">
            <strong>{user.name || "MAI User"}</strong>
            <span>{user.email}</span>
          </div>
          <MenuItem title="Sign out" description="End this dashboard session" onClick={onSignOut} />
        </HeaderMenu>}
      </nav>
    </header>
  );
}
