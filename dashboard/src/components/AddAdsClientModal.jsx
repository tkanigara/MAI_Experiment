import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { ADS_PLATFORMS, ADS_PLATFORM_SOURCES, PLATFORM_LABELS } from "../lib/constants";
import { adsPlatformFlags } from "../lib/format";
import { PlatformBadge, StatusBadge } from "./Badges";
import Modal, { ModalHeader } from "./Modal";

const DEFAULT_INDUSTRIES = ["Automotive", "Retail & E-Commerce", "Technology"];
export default function AddAdsClientModal({ client = null, clients, industries, onClose, onSave }) {
  const [mode, setMode] = useState(client ? "edit" : clients.length ? "existing" : "new");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [industryMode, setIndustryMode] = useState("");
  const [selectedPlatforms, setSelectedPlatforms] = useState(() => (
    client ? adsPlatformFlags(client) : ADS_PLATFORMS
  ));
  const [accounts, setAccounts] = useState([]);
  const [accountSearch, setAccountSearch] = useState("");
  const [selectedAccounts, setSelectedAccounts] = useState(() => (
    (client?.meta_ad_accounts || []).map((item) => item.id)
  ));
  useEffect(() => {
    api("/api/ads/meta/ad-accounts").then(setAccounts).catch((err) => setError(err.message));
  }, []);
  const industryOptions = useMemo(
    () => [...new Set([...DEFAULT_INDUSTRIES, ...industries].filter(Boolean))].sort((a, b) => a.localeCompare(b)),
    [industries],
  );

  function togglePlatform(platform) {
    setSelectedPlatforms((current) => (
      current.includes(platform)
        ? current.filter((item) => item !== platform)
        : ADS_PLATFORMS.filter((item) => [...current, platform].includes(item))
    ));
  }

  function toggleAccount(accountId) {
    setSelectedAccounts((current) => current.includes(accountId) ? current.filter((item) => item !== accountId) : [...current, accountId]);
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const form = new FormData(event.currentTarget);
    if (!selectedPlatforms.length) {
      setError("Select at least one Ads platform.");
      setSaving(false);
      return;
    }
    const industry = industryMode === "__custom__"
      ? String(form.get("custom_industry") || "").trim()
      : String(form.get("industry") || "").trim();
    try {
      await onSave(mode === "edit"
        ? { existing_client_id: client.id, ads_platforms: selectedPlatforms, meta_ad_account_ids: selectedAccounts }
        : mode === "existing"
          ? { existing_client_id: form.get("existing_client_id"), ads_platforms: selectedPlatforms, meta_ad_account_ids: selectedAccounts }
          : {
              client_name: String(form.get("client_name") || "").trim(),
              industry,
              ads_platforms: selectedPlatforms,
              meta_ad_account_ids: selectedAccounts,
            });
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <Modal onClose={onClose}>
      <ModalHeader
        title={client ? "Edit Ads Client" : "Add New Client"}
        subtitle={client
          ? "Choose the paid media platforms connected to this client."
          : "Create an Ads client or enable Ads for an existing client master."}
        onClose={onClose}
      />
      <form className="modal-body" onSubmit={submit}>
        {!client && clients.length > 0 && (
          <div className="segmented-control">
            <button type="button" className={mode === "existing" ? "active" : ""} onClick={() => setMode("existing")}>Existing client</button>
            <button type="button" className={mode === "new" ? "active" : ""} onClick={() => setMode("new")}>New client</button>
          </div>
        )}
        {mode === "edit" ? (
          <label>Client Name <input value={client.client_name} disabled /></label>
        ) : mode === "existing" ? (
          <label>
            Client
            <select name="existing_client_id" required defaultValue="">
              <option value="" disabled>Select a client</option>
              {clients.map((item) => (
                <option key={item.id} value={item.id}>{item.client_name}</option>
              ))}
            </select>
          </label>
        ) : (
          <>
            <label>Client Name <input name="client_name" required placeholder="e.g. Bourbon" /></label>
            <label>Industry
              <select name="industry" required value={industryMode} onChange={(event) => setIndustryMode(event.target.value)}>
                <option value="">Select industry</option>
                {industryOptions.map((item) => <option value={item} key={item}>{item}</option>)}
                <option value="__custom__">Add new industry</option>
              </select>
            </label>
            {industryMode === "__custom__" && <label>New Industry <input name="custom_industry" required placeholder="e.g. Logistics" /></label>}
          </>
        )}
        <div>
          <div className="field-label">Connected Ads Platforms</div>
          <div className="ads-platform-picker">
            {ADS_PLATFORMS.map((platform) => {
              const source = ADS_PLATFORM_SOURCES[platform];
              const checked = selectedPlatforms.includes(platform);
              return (
                <div className={`ads-platform-config ${checked ? "is-selected" : ""}`} key={platform}>
                  <label className="ads-platform-option">
                    <input type="checkbox" checked={checked} onChange={() => togglePlatform(platform)} />
                    <PlatformBadge platform={platform} />
                    <span><strong>{PLATFORM_LABELS[platform]} Ads</strong><small>{source.label}</small></span>
                    <StatusBadge text={source.available ? "Available" : "Coming soon"} state={source.available ? "success" : "info"} />
                  </label>
                </div>
              );
            })}
          </div>
          <div className="field-note">Goals, monthly KPI, and budget are selected when creating each report month.</div>
        </div>
        <div>
          <div className="field-label">Meta Ad Accounts</div>
          <input type="search" value={accountSearch} onChange={(event) => setAccountSearch(event.target.value)} placeholder="Search account name or ID" />
          <div className="ads-account-list">
            {accounts.filter((account) => `${account.name} ${account.id}`.toLowerCase().includes(accountSearch.toLowerCase())).map((account) => (
              <label className={`ads-goal-toggle ${!account.is_active ? "is-disabled" : ""}`} key={account.id}>
                <input type="checkbox" disabled={!account.is_active} checked={selectedAccounts.includes(account.id)} onChange={() => toggleAccount(account.id)} />
                <span><strong>{account.name}</strong><small>{account.id} · {account.currency || "-"} · {account.timezone_name || "-"}{!account.is_active ? " · Inactive" : ""}</small></span>
              </label>
            ))}
          </div>
          <div className="field-note">The token stays on the backend. Inactive accounts are visible but cannot be selected.</div>
        </div>
        {error && <div className="import-alert danger">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Cancel</button>
          <button type="submit" className="primary-button" disabled={saving}>{saving ? "Saving..." : client ? "Save Changes" : "Save Client"}</button>
        </div>
      </form>
    </Modal>
  );
}
