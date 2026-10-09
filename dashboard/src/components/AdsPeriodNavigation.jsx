import { useEffect, useRef, useState } from "react";
import { adsPeriodSlug, clientSlug } from "../lib/format";

export default function AdsPeriodNavigation({ client, period, active, search = "", onNavigate, onReviewObjectives, onGoals, onMetrics, onEditData, onSync, onImport, onSources }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const base = `/ads/clients/${clientSlug(client)}/${adsPeriodSlug(period)}`;
  useEffect(() => {
    const close = (event) => { if (event.key === "Escape" || (event.type === "mousedown" && !ref.current?.contains(event.target))) setOpen(false); };
    document.addEventListener("keydown", close); document.addEventListener("mousedown", close);
    return () => { document.removeEventListener("keydown", close); document.removeEventListener("mousedown", close); };
  }, []);
  return <div className="period-navigation">
    <div className="period-tabs" role="tablist">
      <button type="button" role="tab" aria-selected={active === "overview"} className={active === "overview" ? "active" : ""} onClick={() => onNavigate(base)}>Overview</button>
      <button type="button" role="tab" aria-selected={active === "creative"} className={active === "creative" ? "active" : ""} onClick={() => onNavigate(`${base}/creative${search}`)}>Creative Performance</button>
      <button type="button" role="tab" aria-selected={active === "adsets"} className={active === "adsets" ? "active" : ""} onClick={() => onNavigate(`${base}/adsets${search}`)}>Ad Set Performance</button>
    </div>
    <div className="manage-menu" ref={ref}>
      <button type="button" className="secondary-button menu-trigger manage-trigger" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        <span>Manage</span>
        <span className="dropdown-chevron" aria-hidden="true" />
      </button>
      {open && <div className="manage-menu-panel menu-panel" role="menu" aria-label="Manage reporting period" onClick={() => setOpen(false)}>
        <div className="menu-panel-label" role="presentation">Report setup</div>
        <button type="button" role="menuitem" onClick={onReviewObjectives}>
          <span className="menu-item-title">Review Campaign Objectives</span>
          <span className="menu-item-description">Confirm how campaigns are grouped</span>
        </button>
        <button type="button" role="menuitem" onClick={onGoals}>
          <span className="menu-item-title">Goals &amp; KPI</span>
          <span className="menu-item-description">Set monthly targets and budgets</span>
        </button>
        <button type="button" role="menuitem" onClick={onMetrics}>
          <span className="menu-item-title">Metric Display Settings</span>
          <span className="menu-item-description">Customize visible report metrics</span>
        </button>
        <div className="menu-panel-separator" role="separator" />
        <div className="menu-panel-label" role="presentation">Report data</div>
        <button type="button" role="menuitem" onClick={onEditData || (() => onNavigate(`${base}/edit`))}>
          <span className="menu-item-title">Edit Ads Data</span>
          <span className="menu-item-description">Correct active snapshot values</span>
        </button>
        <button type="button" role="menuitem" onClick={onSync}>
          <span className="menu-item-title">Sync from Meta</span>
          <span className="menu-item-description">Fetch the latest API snapshot</span>
        </button>
        <button type="button" role="menuitem" onClick={onImport}>
          <span className="menu-item-title">Import CSV</span>
          <span className="menu-item-description">Upload an exported data file</span>
        </button>
        <button type="button" role="menuitem" onClick={onSources}>
          <span className="menu-item-title">Data Sources</span>
          <span className="menu-item-description">Choose the active snapshot</span>
        </button>
      </div>}
    </div>
  </div>;
}
