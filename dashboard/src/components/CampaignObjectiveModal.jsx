import { useEffect, useState } from "react";
import Modal, { ModalHeader } from "./Modal";
import { api } from "../lib/api";

const OBJECTIVES = ["reach", "engagement", "views", "link_clicks", "leads"];
const label = (value) => value.split("_").map((part) => part[0].toUpperCase() + part.slice(1)).join(" ");

export default function CampaignObjectiveModal({ client, period, onClose, onSaved }) {
  const [campaigns, setCampaigns] = useState([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => { api(`/api/ads/clients/${client.id}/periods/${period.id}/campaign-mappings`).then((data) => setCampaigns((data.campaigns || []).map((item) => ({ ...item, reporting_objective: item.reporting_objective || item.suggested_objective })))).catch((err) => setError(err.message)); }, [client.id, period.id]);
  function change(index, patch) { setCampaigns((items) => items.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item)); }
  async function save() {
    setSaving(true); setError("");
    try {
      await api(`/api/ads/clients/${client.id}/periods/${period.id}/campaign-mappings`, { method: "PUT", body: JSON.stringify({ campaigns }) });
      await onSaved?.(); onClose();
    } catch (err) { setError(err.message); setSaving(false); }
  }
  return <Modal onClose={onClose} wide>
    <ModalHeader title="Review Campaign Objectives" subtitle="Suggestions come from Campaign objective, Ad Set optimization goal, and Meta result types. Confirmed API Campaign IDs remain mapped across months." onClose={onClose} />
    <div className="modal-body">
      {error && <div className="import-alert danger">{error}</div>}
      {!campaigns.length && !error ? <div className="empty compact-empty">No campaigns are available in the active snapshot.</div> : <div className="table-scroll"><table className="ads-detail-table mapping-table"><thead><tr><th>Include</th><th>Campaign</th><th>Meta signals</th><th>Reporting objective</th><th>Status</th></tr></thead><tbody>{campaigns.map((item, index) => <tr key={`${item.meta_ad_account_id}:${item.campaign_key}`}><td><input type="checkbox" checked={item.is_included !== false} onChange={(event) => change(index, { is_included: event.target.checked })} /></td><td><strong>{item.campaign_name}</strong><small>{item.campaign_external_id || "CSV mapping · this month only"}</small></td><td><small>{item.detected_objective || "No Campaign objective"}<br />{(item.optimization_goals || []).join(", ") || "No optimization goal"}</small></td><td><select value={item.reporting_objective || ""} onChange={(event) => change(index, { reporting_objective: event.target.value })}>{OBJECTIVES.map((objective) => <option key={objective} value={objective}>{label(objective)}</option>)}</select></td><td><span className={`status-pill ${item.is_confirmed ? "success" : "warning"}`}>{item.is_confirmed ? "Confirmed" : `${label(item.suggestion_confidence)} suggestion`}</span></td></tr>)}</tbody></table></div>}
      <div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button type="button" className="primary-button" disabled={saving || !campaigns.length} onClick={save}>{saving ? "Saving..." : "Confirm objectives"}</button></div>
    </div>
  </Modal>;
}
