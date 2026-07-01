import { useState } from "react";
import Modal, { ModalHeader } from "./Modal";

export default function AddClientModal({ onClose, onAddClient }) {
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const platforms = form.getAll("platforms");
    try {
      await onAddClient({
        client_code: String(form.get("client_code") || "").toLowerCase().replace(/\s+/g, "-"),
        client_name: form.get("client_name"),
        industry: form.get("industry"),
        has_instagram: platforms.includes("instagram"),
        has_facebook: platforms.includes("facebook"),
        has_tiktok: platforms.includes("tiktok"),
        has_youtube: platforms.includes("youtube"),
      });
    } catch (err) {
      setError(err.message);
      setIsSaving(false);
    }
  }

  return (
    <Modal onClose={onClose}>
      <ModalHeader
        title="Add New Client"
        subtitle="Create a client profile and select connected social media platforms."
        onClose={onClose}
      />
      <form className="modal-body" onSubmit={handleSubmit}>
        <label>Client Name <input name="client_name" placeholder="e.g. Dunlop Indonesia" required /></label>
        <label>Client Code <input name="client_code" placeholder="e.g. DNLP-ID" required /></label>
        <label>
          Industry
          <select name="industry" required>
            <option value="">Select industry</option>
            <option>Automotive</option>
            <option>Retail & E-Commerce</option>
            <option>Demo</option>
            <option>Technology</option>
          </select>
        </label>
        <div>
          <div className="field-label">Connected Platforms</div>
          <div className="check-grid">
            <label><input type="checkbox" name="platforms" value="instagram" /> Instagram</label>
            <label><input type="checkbox" name="platforms" value="facebook" /> Facebook</label>
            <label><input type="checkbox" name="platforms" value="tiktok" /> TikTok</label>
            <label><input type="checkbox" name="platforms" value="youtube" /> YouTube</label>
          </div>
        </div>
        {error && <div className="import-alert danger">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="secondary-button" onClick={onClose} disabled={isSaving}>Cancel</button>
          <button type="submit" className="primary-button" disabled={isSaving}>
            {isSaving ? "Saving..." : "Save Client"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
