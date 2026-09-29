import { useEffect, useMemo, useState } from "react";
import Modal, { ModalHeader } from "./Modal";
import { api } from "../lib/api";

const title = (value) => value.split("_").map((part) => part[0].toUpperCase() + part.slice(1)).join(" ");
const emptyValues = () => ({
  target_monthly: "",
  budget_monthly: "",
  target_cost_per_result: "",
  adset_targets: [],
  ad_targets: [],
});

function TargetRows({ kind, rows, targets, onChange }) {
  if (!rows.length) return null;
  const noun = kind === "ad" ? "Ad" : "Ad Set";
  const idKey = `${kind}_id`;
  return <details className="entity-kpi-details">
    <summary>Optional {noun} KPI ({rows.length})</summary>
    <p className="entity-kpi-help">Set only the rows that need their own KPI. Blank rows are not saved.</p>
    <div className="entity-target-list">
      <div className="entity-target-head" aria-hidden="true"><span>{noun}</span><span>Target</span><span>Budget</span></div>
      {rows.map((row) => {
        const target = targets?.find((item) => item[idKey] === row.id) || {};
        return <div className="entity-target-row" key={`${kind}-${row.id}`}>
          <span className="entity-target-name"><strong>{row.name}</strong>{row.context && <small>{row.context}</small>}</span>
          <input aria-label={`${row.name} target`} type="number" min="0" placeholder="Target" value={target.target ?? ""} onChange={(event) => onChange(row, "target", event.target.value)} />
          <input aria-label={`${row.name} budget`} type="number" min="0" placeholder="Budget" value={target.budget ?? ""} onChange={(event) => onChange(row, "budget", event.target.value)} />
        </div>;
      })}
    </div>
  </details>;
}

export default function ObjectiveKpiModal({ client, period, onClose, onSave, onReviewObjectives }) {
  const [campaigns, setCampaigns] = useState([]);
  const [configs, setConfigs] = useState(() => period.objective_configs?.meta || {});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api(`/api/ads/clients/${client.id}/periods/${period.id}/campaign-mappings`)
      .then((data) => setCampaigns(data.campaigns || []))
      .catch((err) => setError(err.message));
  }, [client.id, period.id]);

  const objectives = useMemo(
    () => [...new Set(campaigns.filter((item) => item.is_confirmed && item.is_included).map((item) => item.reporting_objective))],
    [campaigns],
  );

  function change(objective, field, value) {
    setConfigs((all) => ({ ...all, [objective]: { ...(all[objective] || emptyValues()), [field]: value } }));
  }

  function changeEntity(objective, kind, entity, field, value) {
    const listKey = kind === "ad" ? "ad_targets" : "adset_targets";
    const idKey = `${kind}_id`;
    const nameKey = `${kind}_name`;
    const rows = [...(configs[objective]?.[listKey] || [])];
    const index = rows.findIndex((item) => item[idKey] === entity.id);
    const base = { [idKey]: entity.id, [nameKey]: entity.name };
    if (kind === "ad") Object.assign(base, { adset_id: entity.adset_id, adset_name: entity.adset_name });
    const next = { ...(index >= 0 ? rows[index] : base), [field]: value };
    if (index >= 0) rows[index] = next;
    else rows.push(next);
    change(objective, listKey, rows);
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await onSave({ objective_model: "canonical", objective_configs: { meta: configs } });
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return <Modal onClose={onClose} wide>
    <ModalHeader title={`${period.period_label} Goals & KPI`} subtitle="Set monthly KPI by objective, or add optional targets for individual Ad Sets and Ads." onClose={onClose} />
    <form className="modal-body" onSubmit={submit}>
      {error && <div className="import-alert danger">{error}</div>}
      {!campaigns.length ? <div className="empty compact-empty">Loading Campaign objectives...</div> : !objectives.length ? <div className="empty"><h3>Confirm Campaign objectives first</h3><p>KPI is only available for confirmed, included Campaigns.</p><button type="button" className="primary-button" onClick={onReviewObjectives}>Review Campaign Objectives</button></div> : objectives.map((objective) => {
        const value = configs[objective] || emptyValues();
        const objectiveCampaigns = campaigns.filter((item) => item.is_confirmed && item.is_included && item.reporting_objective === objective);
        const adsets = objectiveCampaigns.flatMap((campaign) => (campaign.adsets || []).map((adset) => ({ ...adset, context: campaign.campaign_name })));
        const ads = objectiveCampaigns.flatMap((campaign) => (campaign.adsets || []).flatMap((adset) => (adset.ads || []).map((ad) => ({
          ...ad,
          adset_id: adset.id,
          adset_name: adset.name,
          context: `${adset.name} · ${campaign.campaign_name}`,
        }))));
        return <section className="objective-kpi-section" key={objective}>
          <div><span className="eyebrow ads">Meta objective</span><h3>{title(objective)}</h3><small>{objectiveCampaigns.length} included Campaigns · {adsets.length} Ad Sets · {ads.length} Ads</small></div>
          <div className="kpi-input-grid">
            <label>Monthly target<input type="number" min="0" value={value.target_monthly ?? ""} onChange={(event) => change(objective, "target_monthly", event.target.value)} /></label>
            <label>Monthly budget<input type="number" min="0" value={value.budget_monthly ?? ""} onChange={(event) => change(objective, "budget_monthly", event.target.value)} /></label>
            <label>Target cost / result<input type="number" min="0" value={value.target_cost_per_result ?? ""} onChange={(event) => change(objective, "target_cost_per_result", event.target.value)} /></label>
          </div>
          <TargetRows kind="adset" rows={adsets} targets={value.adset_targets} onChange={(row, field, nextValue) => changeEntity(objective, "adset", row, field, nextValue)} />
          <TargetRows kind="ad" rows={ads} targets={value.ad_targets} onChange={(row, field, nextValue) => changeEntity(objective, "ad", row, field, nextValue)} />
        </section>;
      })}
      <div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button type="submit" className="primary-button" disabled={saving || !objectives.length}>{saving ? "Saving..." : "Save Goals & KPI"}</button></div>
    </form>
  </Modal>;
}
