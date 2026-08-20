import { useEffect, useMemo, useState } from "react";
import Modal, { ModalHeader } from "./Modal";
import { api } from "../lib/api";

const title = (value) => value.split("_").map((part) => part[0].toUpperCase() + part.slice(1)).join(" ");
const emptyValues = () => ({ target_monthly: "", budget_monthly: "", target_cost_per_result: "", adset_targets: [] });

export default function ObjectiveKpiModal({ client, period, onClose, onSave, onReviewObjectives }) {
  const [campaigns, setCampaigns] = useState([]);
  const [configs, setConfigs] = useState(() => period.objective_configs?.meta || {});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => { api(`/api/ads/clients/${client.id}/periods/${period.id}/campaign-mappings`).then((data) => setCampaigns(data.campaigns || [])).catch((err) => setError(err.message)); }, [client.id, period.id]);
  const objectives = useMemo(() => [...new Set(campaigns.filter((item) => item.is_confirmed && item.is_included).map((item) => item.reporting_objective))], [campaigns]);
  function change(objective, field, value) { setConfigs((all) => ({ ...all, [objective]: { ...(all[objective] || emptyValues()), [field]: value } })); }
  function changeAdset(objective, adset, field, value) {
    const rows = [...(configs[objective]?.adset_targets || [])];
    const index = rows.findIndex((item) => item.adset_id === adset.id);
    const next = { ...(index >= 0 ? rows[index] : { adset_id: adset.id, adset_name: adset.name }), [field]: value };
    if (index >= 0) rows[index] = next; else rows.push(next);
    change(objective, "adset_targets", rows);
  }
  async function submit(event) {
    event.preventDefault(); setSaving(true); setError("");
    try { await onSave({ objective_model: "canonical", objective_configs: { meta: configs } }); }
    catch (err) { setError(err.message); setSaving(false); }
  }
  return <Modal onClose={onClose} wide><ModalHeader title={`${period.period_label} Goals & KPI`} subtitle="Monthly KPI by confirmed objective. Ad Set targets are optional and are never divided automatically." onClose={onClose} /><form className="modal-body" onSubmit={submit}>
    {error && <div className="import-alert danger">{error}</div>}
    {!campaigns.length ? <div className="empty compact-empty">Loading Campaign objectives...</div> : !objectives.length ? <div className="empty"><h3>Confirm Campaign objectives first</h3><p>KPI is only available for confirmed, included Campaigns.</p><button type="button" className="primary-button" onClick={onReviewObjectives}>Review Campaign Objectives</button></div> : objectives.map((objective) => {
      const value = configs[objective] || emptyValues();
      const adsets = campaigns.filter((item) => item.is_confirmed && item.is_included && item.reporting_objective === objective).flatMap((item) => item.adsets || []);
      return <section className="objective-kpi-section" key={objective}><div><span className="eyebrow ads">Meta objective</span><h3>{title(objective)}</h3><small>{campaigns.filter((item) => item.is_confirmed && item.is_included && item.reporting_objective === objective).length} included Campaigns</small></div><div className="kpi-input-grid"><label>Monthly target<input type="number" min="0" value={value.target_monthly ?? ""} onChange={(event) => change(objective, "target_monthly", event.target.value)} /></label><label>Monthly budget<input type="number" min="0" value={value.budget_monthly ?? ""} onChange={(event) => change(objective, "budget_monthly", event.target.value)} /></label><label>Target cost / result<input type="number" min="0" value={value.target_cost_per_result ?? ""} onChange={(event) => change(objective, "target_cost_per_result", event.target.value)} /></label></div>{adsets.length > 0 && <details><summary>Optional Ad Set KPI ({adsets.length})</summary><div className="adset-target-list">{adsets.map((adset) => { const target = value.adset_targets?.find((item) => item.adset_id === adset.id) || {}; return <div key={adset.id}><strong>{adset.name}</strong><input aria-label={`${adset.name} target`} type="number" min="0" placeholder="Target" value={target.target ?? ""} onChange={(event) => changeAdset(objective, adset, "target", event.target.value)} /><input aria-label={`${adset.name} budget`} type="number" min="0" placeholder="Budget" value={target.budget ?? ""} onChange={(event) => changeAdset(objective, adset, "budget", event.target.value)} /></div>; })}</div></details>}</section>;
    })}
    <div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button type="submit" className="primary-button" disabled={saving || !objectives.length}>{saving ? "Saving..." : "Save Goals & KPI"}</button></div>
  </form></Modal>;
}
