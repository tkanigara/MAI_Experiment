import { useState } from "react";
import { api } from "../lib/api";
import { ADS_PLATFORMS, ADS_PLATFORM_SOURCES, PLATFORM_LABELS } from "../lib/constants";
import { adsPlatformFlags } from "../lib/format";
import { PlatformBadge, StatusBadge } from "./Badges";
import Modal, { ModalHeader } from "./Modal";

const FILES = [
  ["campaign", "Campaign Data", "Campaign-level delivery and performance."],
  ["adset", "Ad Set Data", "Ad set budget, delivery, and performance."],
  ["ad", "Ads Data", "Creative/ad-level delivery and performance."],
  ["placement", "Placement Breakdown", "Platform, placement, and device breakdown."],
  ["demographic", "Age & Gender Breakdown", "Audience demographic breakdown."],
  ["region", "Region Breakdown", "Geographic performance breakdown."],
];

export default function MetaAdsImportModal({ client, period, onClose, onImported }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [files, setFiles] = useState({});
  const [draggingSlot, setDraggingSlot] = useState("");
  const selectedCount = FILES.filter(([slot]) => files[slot]).length;
  const configuredPlatforms = adsPlatformFlags(client);

  function selectFile(slot, file) {
    if (!file) return;
    setError("");
    setFiles((current) => ({ ...current, [slot]: file }));
  }

  function removeFile(slot) {
    setError("");
    setFiles((current) => {
      const next = { ...current };
      delete next[slot];
      return next;
    });
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const body = new FormData();
    body.append("client_id", client.id);
    if (period?.id) body.append("period_id", period.id);
    FILES.forEach(([slot]) => body.append(slot, files[slot]));
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
        title={period ? `Import CSV for ${period.period_label}` : "Import CSV for New Report Month"}
        subtitle="Upload one complete Meta Ads snapshot for Instagram and Facebook."
        onClose={onClose}
      />
      <form className="modal-body" onSubmit={submit}>
        <div className="modal-context">
          <div><span>Client</span><strong>{client?.client_name}</strong></div>
          <div><span>Reporting period</span><strong>{period?.period_label || "Detected from CSV files"}</strong></div>
        </div>
        <div className="ads-source-grid">
          {ADS_PLATFORMS.map((platform) => {
            const source = ADS_PLATFORM_SOURCES[platform];
            const configured = configuredPlatforms.includes(platform);
            return (
              <div className={`ads-source-card ${source.available && configured ? "active" : "pending"}`} key={platform}>
                <PlatformBadge platform={platform} />
                <div><strong>{PLATFORM_LABELS[platform]} Ads</strong><span>{source.label}</span></div>
                <StatusBadge text={!configured ? "Not connected" : source.available ? "CSV available" : "Coming soon"} state={!configured ? "neutral" : source.available ? "success" : "info"} />
              </div>
            );
          })}
        </div>
        <div className="import-alert info"><strong>Goals &amp; KPI are managed separately.</strong> This upload only updates the CSV data snapshot and will not change monthly targets.</div>
        <div className="csv-action-bar">
          <div><strong>{selectedCount} of {FILES.length} CSV files selected</strong><span>All six Meta exports are required and must cover the same period.</span></div>
          <button type="submit" className="primary-button" disabled={saving || selectedCount !== FILES.length}>{saving ? "Importing..." : period ? "Import New CSV Snapshot" : "Import CSV Data"}</button>
        </div>
        <div className="upload-list">
          {FILES.map(([slot, label, description]) => {
            const selected = files[slot];
            const existing = period?.filenames?.[slot];
            return (
              <div
                className={`upload-row ${draggingSlot === slot ? "is-dragging" : ""}`}
                key={slot}
                onDragEnter={(event) => { event.preventDefault(); setDraggingSlot(slot); }}
                onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; setDraggingSlot(slot); }}
                onDragLeave={() => setDraggingSlot("")}
                onDrop={(event) => { event.preventDefault(); setDraggingSlot(""); selectFile(slot, event.dataTransfer.files?.[0]); }}
              >
                <div className="upload-icon">{selected ? "ok" : "csv"}</div>
                <div>
                  <div className="upload-title">{label}</div>
                  <div className="upload-desc">{selected?.name || existing || description}</div>
                  <div className="drop-hint">{selected ? "Ready to upload" : "Drop CSV here or choose a file"}</div>
                </div>
                <StatusBadge text={selected ? "Ready" : existing ? "Uploaded" : "Required"} state={selected ? "success" : existing ? "neutral" : "warning"} />
                <div className="upload-actions">
                  <label className="file-button">{selected || existing ? "Replace" : "Choose"}<input type="file" accept=".csv,text/csv" onChange={(event) => { selectFile(slot, event.target.files?.[0]); event.target.value = ""; }} /></label>
                  {selected && <button className="danger-link upload-remove-button" type="button" onClick={() => removeFile(slot)}>Remove</button>}
                </div>
              </div>
            );
          })}
        </div>
        <div className="import-alert">Meta Instagram and Facebook currently share this six-file source snapshot. YouTube and TikTok upload slots will be enabled after their export contracts are available.</div>
        {error && <div className="import-alert danger">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Cancel</button>
        </div>
      </form>
    </Modal>
  );
}
