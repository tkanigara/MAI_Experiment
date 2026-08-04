import { useMemo, useState } from "react";
import Modal, { ModalHeader } from "./Modal";
import { PLATFORM_LABELS, PLATFORMS } from "../lib/constants";

const DEFAULT_INDUSTRIES = ["Automotive", "Retail & E-Commerce", "Technology"];

export default function AddClientModal({
  client = null,
  industries = [],
  onClose,
  onAddClient,
  onReportLocked,
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [industryMode, setIndustryMode] = useState(client?.industry || "");
  const isEdit = Boolean(client);
  const industryOptions = useMemo(
    () => [...new Set([...DEFAULT_INDUSTRIES, ...industries].filter(Boolean))].sort((a, b) => a.localeCompare(b)),
    [industries],
  );

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const platforms = form.getAll("platforms");
    if (platforms.length === 0) {
      setError("Select at least one connected platform.");
      setIsSaving(false);
      return;
    }
    const industry =
      industryMode === "__custom__"
        ? String(form.get("custom_industry") || "").trim()
        : String(form.get("industry") || "").trim();
    try {
      await onAddClient({
        client_name: form.get("client_name"),
        industry,
        ...Object.fromEntries(
          PLATFORMS.map((platform) => [
            `has_${platform}`,
            platforms.includes(platform),
          ]),
        ),
      });
    } catch (err) {
      if (!onReportLocked?.(err)) setError(err.message);
      setIsSaving(false);
    }
  }

  return (
    <Modal onClose={onClose}>
      <ModalHeader
        title={isEdit ? "Edit Client" : "Add New Client"}
        subtitle={isEdit ? "Update client information and connected social media platforms." : "Create a client profile and select connected social media platforms."}
        onClose={onClose}
      />
      <form className="modal-body" onSubmit={handleSubmit}>
        <label>Client Name <input name="client_name" placeholder="e.g. Dunlop Indonesia" defaultValue={client?.client_name || ""} required /></label>
        <label>
          Industry
          <select name="industry" required value={industryMode} onChange={(event) => setIndustryMode(event.target.value)}>
            <option value="">Select industry</option>
            {industryOptions.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
            <option value="__custom__">Add new industry</option>
          </select>
        </label>
        {industryMode === "__custom__" && (
          <label>
            New Industry
            <input name="custom_industry" placeholder="e.g. Logistics" required />
          </label>
        )}
        <div>
          <div className="field-label">Connected Platforms</div>
          <div className="check-grid">
            {PLATFORMS.map((platform) => (
              <label key={platform}>
                <input
                  type="checkbox"
                  name="platforms"
                  value={platform}
                  defaultChecked={client?.[`has_${platform}`]}
                />{" "}
                {PLATFORM_LABELS[platform]}
              </label>
            ))}
          </div>
        </div>
        {error && <div className="import-alert danger">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="secondary-button" onClick={onClose} disabled={isSaving}>Cancel</button>
          <button type="submit" className="primary-button" disabled={isSaving}>
            {isSaving ? "Saving..." : isEdit ? "Save Changes" : "Save Client"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
