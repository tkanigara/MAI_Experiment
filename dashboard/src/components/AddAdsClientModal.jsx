import { useMemo, useState } from "react";
import Modal, { ModalHeader } from "./Modal";

export default function AddAdsClientModal({ clients, industries, onClose, onSave }) {
  const [mode, setMode] = useState(clients.length ? "existing" : "new");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const industryOptions = useMemo(
    () => [...new Set(industries.filter(Boolean))].sort((a, b) => a.localeCompare(b)),
    [industries],
  );

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await onSave(mode === "existing"
        ? { existing_client_id: form.get("existing_client_id") }
        : {
            client_name: String(form.get("client_name") || "").trim(),
            industry: String(form.get("industry") || "").trim(),
          });
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <Modal onClose={onClose}>
      <ModalHeader
        title="Add Ads Client"
        subtitle="Enable Meta Ads for an existing client or create a new client master."
        onClose={onClose}
      />
      <form className="modal-body" onSubmit={submit}>
        {clients.length > 0 && (
          <div className="segmented-control">
            <button type="button" className={mode === "existing" ? "active" : ""} onClick={() => setMode("existing")}>Existing client</button>
            <button type="button" className={mode === "new" ? "active" : ""} onClick={() => setMode("new")}>New client</button>
          </div>
        )}
        {mode === "existing" ? (
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
            <label>
              Industry
              <input name="industry" list="ads-industry-options" required placeholder="e.g. FMCG" />
              <datalist id="ads-industry-options">
                {industryOptions.map((item) => <option value={item} key={item} />)}
              </datalist>
            </label>
          </>
        )}
        {error && <div className="import-alert danger">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Cancel</button>
          <button type="submit" className="primary-button" disabled={saving}>{saving ? "Saving..." : "Add Ads Client"}</button>
        </div>
      </form>
    </Modal>
  );
}
