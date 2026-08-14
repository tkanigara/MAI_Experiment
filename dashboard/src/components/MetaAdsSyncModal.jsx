import { useMemo, useState } from "react";
import { api } from "../lib/api";
import { adsPlatformFlags } from "../lib/format";
import AdsPeriodGoalFields, { initialAdsPeriodGoals, serializeAdsPeriodGoals } from "./AdsPeriodGoalFields";
import Modal, { ModalHeader } from "./Modal";

export default function MetaAdsSyncModal({ client, period = null, initialPlatform = null, onClose, onSynced }) {
  const accounts = client.meta_ad_accounts || [];
  const availablePlatforms = adsPlatformFlags(client).filter((item) => ["instagram", "facebook"].includes(item));
  const [selectedAccounts, setSelectedAccounts] = useState(() => accounts.filter((item) => item.is_active).map((item) => item.id));
  const [platforms, setPlatforms] = useState(() => initialPlatform ? [initialPlatform] : availablePlatforms);
  const [goals, setGoals] = useState(() => initialAdsPeriodGoals(client, period));
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");
  const title = period ? `Sync ${period.period_label} from Meta` : "Create Report Month from Meta";
  const currencies = useMemo(() => new Set(accounts.filter((item) => selectedAccounts.includes(item.id)).map((item) => item.currency).filter(Boolean)), [accounts, selectedAccounts]);

  function toggle(list, setter, value) {
    setter(list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);
  }

  async function submit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const adsGoals = serializeAdsPeriodGoals(goals, client);
    if (!selectedAccounts.length) return setError("Select at least one Meta Ad Account.");
    if (!platforms.length) return setError("Select Instagram, Facebook, or both.");
    if (currencies.size > 1) return setError("Accounts with different currencies cannot be aggregated.");
    if (!Object.values(adsGoals).some((items) => items.length)) return setError("Select at least one goal for this report month.");
    setSyncing(true); setError("");
    try {
      let selectedPeriod = period;
      if (!selectedPeriod) {
        selectedPeriod = await api(`/api/ads/clients/${client.id}/periods`, {
          method: "POST",
          body: JSON.stringify({ period_start: form.get("period_start"), period_end: form.get("period_end"), ads_goals: adsGoals }),
        });
      }
      const result = await api(`/api/ads/clients/${client.id}/periods/${selectedPeriod.id}/sync`, {
        method: "POST",
        body: JSON.stringify({ ad_account_ids: selectedAccounts, platforms, goals: adsGoals }),
      });
      await onSynced(result, selectedPeriod);
    } catch (err) {
      setError(err.message); setSyncing(false);
    }
  }

  return <Modal onClose={syncing ? undefined : onClose} wide>
    <ModalHeader title={title} subtitle="Choose the mapped accounts and platform scope. A failed sync will not replace the current snapshot." onClose={syncing ? undefined : onClose} />
    <form className="modal-body" onSubmit={submit}>
      {!period && <div className="form-grid"><label>Start date<input name="period_start" type="date" required /></label><label>End date<input name="period_end" type="date" required /></label></div>}
      {period && <div className="import-alert info">Reporting dates are fixed: {period.period_start} to {period.period_end}.</div>}
      <div><div className="field-label">Meta Ad Accounts</div><div className="field-note">Only accounts connected in Add/Edit Client can be synced.</div>
        <div className="ads-account-list">{accounts.map((account) => <label className={`ads-goal-toggle ${!account.is_active ? "is-disabled" : ""}`} key={account.id}>
          <input type="checkbox" disabled={!account.is_active || syncing} checked={selectedAccounts.includes(account.id)} onChange={() => toggle(selectedAccounts, setSelectedAccounts, account.id)} />
          <span><strong>{account.name || account.id}</strong><small>{account.id} · {account.currency || "Currency unknown"} · {account.timezone_name || "Timezone unknown"}{!account.is_active ? " · Inactive" : ""}</small></span>
        </label>)}</div>
        {!accounts.length && <div className="import-alert danger">No Meta Ad Account is mapped to this client. Add one from Edit Client first.</div>}
      </div>
      <div><div className="field-label">Platform scope</div><div className="goal-chip-row">{availablePlatforms.map((platform) => <label className="goal-chip" key={platform}><input type="checkbox" checked={platforms.includes(platform)} disabled={syncing} onChange={() => toggle(platforms, setPlatforms, platform)} /> {platform === "instagram" ? "Instagram" : "Facebook"}</label>)}</div></div>
      <AdsPeriodGoalFields client={client} goals={goals} onChange={setGoals} />
      {error && <div className="import-alert danger">{error}</div>}
      <div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose} disabled={syncing}>Cancel</button><button className="primary-button" type="submit" disabled={syncing || !accounts.length}>{syncing ? "Syncing..." : "Sync from Meta"}</button></div>
    </form>
  </Modal>;
}
