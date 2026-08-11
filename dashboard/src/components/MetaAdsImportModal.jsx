import { useState } from "react";
import { api } from "../lib/api";
import Modal, { ModalHeader } from "./Modal";

const FILES = [
  ["campaign", "Campaign"],
  ["adset", "Ad Set"],
  ["ad", "Ads"],
  ["placement", "Ads Placement"],
  ["demographic", "Ads Age/Gender"],
  ["region", "Ads Region"],
];

export default function MetaAdsImportModal({ client, period, onClose, onImported }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const source = new FormData(event.currentTarget);
    const body = new FormData();
    body.append("client_id", client.id);
    if (period?.id) body.append("period_id", period.id);
    FILES.forEach(([slot]) => body.append(slot, source.get(slot)));
    try {
      const result = await api("/api/ads/imports", { method: "POST", body });
      await onImported(result);
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <Modal onClose={onClose} wide>
      <ModalHeader
        title={period ? `Replace ${period.period_label} Ads Data` : "Add Meta Ads Data"}
        subtitle="Upload all six exports from the same Meta Ads reporting period."
        onClose={onClose}
      />
      <form className="modal-body" onSubmit={submit}>
        <div className="ads-upload-grid">
          {FILES.map(([slot, label]) => (
            <label className="ads-upload-field" key={slot}>
              <span>{label} CSV</span>
              <input type="file" name={slot} accept=".csv,text/csv" required />
            </label>
          ))}
        </div>
        <div className="import-alert">
          Summary rows are retained as validation metadata and excluded from entity rows. Re-import replaces this Ads snapshot atomically.
        </div>
        {error && <div className="import-alert danger">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Cancel</button>
          <button type="submit" className="primary-button" disabled={saving}>{saving ? "Importing..." : "Import Ads Data"}</button>
        </div>
      </form>
    </Modal>
  );
}
