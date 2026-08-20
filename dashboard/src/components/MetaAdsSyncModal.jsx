import { useMemo, useState } from "react";
import { api } from "../lib/api";
import { adsPlatformFlags } from "../lib/format";
import Modal, { ModalHeader } from "./Modal";

export default function MetaAdsSyncModal({ client, period = null, initialPlatform = null, onClose, onSynced }) {
  const accounts = client.meta_ad_accounts || [];
  const availablePlatforms = adsPlatformFlags(client).filter((item) => ["instagram", "facebook"].includes(item));
  const [selectedAccounts, setSelectedAccounts] = useState(() => accounts.filter((item) => item.is_active).map((item) => item.id));
  const [platforms, setPlatforms] = useState(() => initialPlatform ? [initialPlatform] : availablePlatforms);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");
  const [workingPeriod, setWorkingPeriod] = useState(period);
  const today = useMemo(() => {
    const value = new Date();
    return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
  }, []);
  const [reportMonth, setReportMonth] = useState(() => String(period?.period_start || today).slice(0, 7));
  const [rangePreset, setRangePreset] = useState("month_to_date");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const title = workingPeriod ? `Sync ${workingPeriod.period_label} from Meta` : "Create Report Month from Meta";
  const currencies = useMemo(() => new Set(accounts.filter((item) => selectedAccounts.includes(item.id)).map((item) => item.currency).filter(Boolean)), [accounts, selectedAccounts]);
  const activeMonth = String(workingPeriod?.period_start || (reportMonth ? `${reportMonth}-01` : today)).slice(0, 7);
  const [monthYear, monthNumber] = activeMonth.split("-").map(Number);
  const monthStart = `${activeMonth}-01`;
  const monthEnd = `${activeMonth}-${String(new Date(monthYear, monthNumber, 0).getDate()).padStart(2, "0")}`;
  const availableEnd = monthEnd < today ? monthEnd : today;
  const lastSevenStartDate = new Date(`${availableEnd}T00:00:00`);
  lastSevenStartDate.setDate(lastSevenStartDate.getDate() - 6);
  const lastSevenStart = [lastSevenStartDate.getFullYear(), String(lastSevenStartDate.getMonth() + 1).padStart(2, "0"), String(lastSevenStartDate.getDate()).padStart(2, "0")].join("-");
  const previewRange = rangePreset === "custom"
    ? { start: customStart, end: customEnd }
    : rangePreset === "last_7_days"
      ? { start: lastSevenStart < monthStart ? monthStart : lastSevenStart, end: availableEnd }
      : rangePreset === "full_month"
        ? { start: monthStart, end: monthEnd }
        : { start: monthStart, end: availableEnd };

  function toggle(list, setter, value) {
    setter(list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);
  }

  async function submit(event) {
    event.preventDefault();
    if (!selectedAccounts.length) return setError("Select at least one Meta Ad Account.");
    if (!platforms.length) return setError("Select Instagram, Facebook, or both.");
    if (currencies.size > 1) return setError("Accounts with different currencies cannot be aggregated.");
    setSyncing(true); setError("");
    try {
      let selectedPeriod = workingPeriod;
      if (!selectedPeriod) {
        selectedPeriod = await api(`/api/ads/clients/${client.id}/periods`, {
          method: "POST",
          body: JSON.stringify({ period_start: monthStart, period_end: monthEnd }),
        });
        // Keep the successfully-created month when the following Meta request
        // fails, so Retry resumes the same period instead of creating it again.
        setWorkingPeriod(selectedPeriod);
      }
      const result = await api(`/api/ads/clients/${client.id}/periods/${selectedPeriod.id}/sync`, {
        method: "POST",
        body: JSON.stringify({
          ad_account_ids: selectedAccounts,
          platforms,
          date_range: { preset: rangePreset, start: previewRange.start, end: previewRange.end },
        }),
      });
      await onSynced(result, selectedPeriod);
    } catch (err) {
      setError(err.message); setSyncing(false);
    }
  }

  return <Modal onClose={syncing ? undefined : onClose} wide>
    <ModalHeader title={title} subtitle="Choose the mapped accounts and platform scope. A failed sync will not replace the current snapshot." onClose={syncing ? undefined : onClose} />
    <form className="modal-body" onSubmit={submit}>
      {!workingPeriod && <label>Report month<input name="report_month" type="month" max={today.slice(0, 7)} required value={reportMonth} onChange={(event) => { setReportMonth(event.target.value); setCustomStart(""); setCustomEnd(""); }} /><small className="field-note">The month is only the report container. You choose the actual data range below.</small></label>}
      <fieldset className="sync-range-fieldset"><legend>Data range</legend><div className="sync-range-options">
        {[
          ["month_to_date", "Month to date", "From day 1 through today"],
          ["last_7_days", "Last 7 days", "A rolling 7-day view within this month"],
          ["full_month", "Full month", "Available after the month is complete"],
          ["custom", "Custom range", "Choose any dates within this month"],
        ].map(([value, label, note]) => <label className={`sync-range-option ${rangePreset === value ? "is-selected" : ""} ${value === "full_month" && monthEnd > today ? "is-disabled" : ""}`} key={value}><input type="radio" name="date_range" value={value} checked={rangePreset === value} disabled={syncing || (value === "full_month" && monthEnd > today)} onChange={() => { setRangePreset(value); if (value === "custom" && !customStart) { setCustomStart(lastSevenStart < monthStart ? monthStart : lastSevenStart); setCustomEnd(availableEnd); } }} /><span><strong>{label}</strong><small>{note}</small></span></label>)}
      </div>
      {rangePreset === "custom" && <div className="form-grid sync-custom-range"><label>Start date<input type="date" min={monthStart} max={availableEnd} required value={customStart} onChange={(event) => setCustomStart(event.target.value)} /></label><label>End date<input type="date" min={customStart || monthStart} max={availableEnd} required value={customEnd} onChange={(event) => setCustomEnd(event.target.value)} /></label></div>}
      <div className="sync-range-preview"><span>Data that will be fetched</span><strong>{previewRange.start || "Choose a start date"} → {previewRange.end || "Choose an end date"}</strong></div>
      </fieldset>
      <div className="import-alert info"><strong>Goals &amp; KPI are managed separately.</strong> Sync only refreshes performance data and keeps this report month's existing targets.</div>
      <div><div className="field-label">Meta Ad Accounts</div><div className="field-note">Only accounts connected in Add/Edit Client can be synced.</div>
        <div className="ads-account-list">{accounts.map((account) => <label className={`ads-goal-toggle ${!account.is_active ? "is-disabled" : ""}`} key={account.id}>
          <input type="checkbox" disabled={!account.is_active || syncing} checked={selectedAccounts.includes(account.id)} onChange={() => toggle(selectedAccounts, setSelectedAccounts, account.id)} />
          <span><strong>{account.name || account.id}</strong><small>{account.id} · {account.currency || "Currency unknown"} · {account.timezone_name || "Timezone unknown"}{!account.is_active ? " · Inactive" : ""}</small></span>
        </label>)}</div>
        {!accounts.length && <div className="import-alert danger">No Meta Ad Account is mapped to this client. Add one from Edit Client first.</div>}
      </div>
      <div><div className="field-label">Platforms to sync</div><div className="field-note">Only the selected platforms will receive a new active snapshot.</div><div className="sync-platform-grid">{availablePlatforms.map((platform) => <label className={`sync-platform-option ${platforms.includes(platform) ? "is-selected" : ""}`} key={platform}><input type="checkbox" checked={platforms.includes(platform)} disabled={syncing} onChange={() => toggle(platforms, setPlatforms, platform)} /><span><strong>{platform === "instagram" ? "Instagram Ads" : "Facebook Ads"}</strong><small>{platforms.includes(platform) ? "Included in this sync" : "Not included"}</small></span></label>)}</div></div>
      {error && <div className="import-alert danger">{error}</div>}
      <div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose} disabled={syncing}>Cancel</button><button className="primary-button" type="submit" disabled={syncing || !accounts.length}>{syncing ? "Syncing..." : "Sync from Meta"}</button></div>
    </form>
  </Modal>;
}
