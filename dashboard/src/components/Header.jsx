export default function Header({ activeSection, onNavigate }) {
  return (
    <header className="app-header">
      <button
        type="button"
        className="brand-title"
        onClick={() => onNavigate("/clients")}
      >
        MAI Social Media Report Dashboard
      </button>
      <nav className="header-navigation" aria-label="Main navigation">
        <button
          type="button"
          className={activeSection === "clients" ? "active" : ""}
          onClick={() => onNavigate("/clients")}
        >
          Clients
        </button>
        <button
          type="button"
          className={activeSection === "report-jobs" ? "active" : ""}
          onClick={() => onNavigate("/report-jobs")}
        >
          Report Queue
        </button>
      </nav>
    </header>
  );
}
