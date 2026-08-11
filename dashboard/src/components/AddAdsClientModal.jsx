import { useMemo, useState } from "react";
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
  const industryOptions = useMemo(
    () => [...new Set([...DEFAULT_INDUSTRIES, ...industries].filter(Boolean))].sort((a, b) => a.localeCompare(b)),
    [industries],
  );

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const adsPlatforms = form.getAll("ads_platforms");
    if (!adsPlatforms.length) {
      setError("Select at least one Ads platform.");
      setSaving(false);
      return;
    }
    const industry = industryMode === "__custom__"
      ? String(form.get("custom_industry") || "").trim()
      : String(form.get("industry") || "").trim();
    try {
      await onSave(mode === "edit"
        ? { existing_client_id: client.id, ads_platforms: adsPlatforms }
        : mode === "existing"
          ? { existing_client_id: form.get("existing_client_id"), ads_platforms: adsPlatforms }
        : {
            client_name: String(form.get("client_name") || "").trim(),
            industry,
            ads_platforms: adsPlatforms,
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
          ? "Update the paid media platforms connected to this Ads client."
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
              {clients.map((client) => (
                <option key={client.id} value={client.id}>{client.client_name}</option>
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
              const defaults = client ? adsPlatformFlags(client) : ADS_PLATFORMS;
              return (
                <label className="ads-platform-option" key={platform}>
                  <input type="checkbox" name="ads_platforms" value={platform} defaultChecked={defaults.includes(platform)} />
                  <PlatformBadge platform={platform} />
                  <span><strong>{PLATFORM_LABELS[platform]} Ads</strong><small>{source.label}</small></span>
                  <StatusBadge text={source.available ? "Available" : "Coming soon"} state={source.available ? "success" : "info"} />
                </label>
              );
            })}
          </div>
          <div className="field-note">YouTube and TikTok can be configured now; ingestion and performance storage will be connected later.</div>
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
