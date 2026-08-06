import { useState } from "react";
import Modal, { ModalHeader } from "./Modal";
import TypedNumberInput from "./TypedNumberInput";
import { formatNumber, prettyMetric } from "../lib/format";

export default function EditKpiModal({
  row,
  onClose,
  onSave,
  onReportLocked,
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await onSave({
        metric_name: row.metric_name,
        target_month: form.get("target_month"),
        target_year: form.get("target_year"),
        unit: row.unit || "count",
      });
    } catch (err) {
      if (!onReportLocked?.(err)) setError(err.message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Modal onClose={onClose}>
      <ModalHeader
        title="Update KPI Target"
        subtitle="Edit the selected platform KPI target for this report year."
        onClose={onClose}
      />
      <form className="modal-body" onSubmit={handleSubmit}>
        <label>Metric <input value={prettyMetric(row.metric_name)} readOnly /></label>
        <label>Actual Month <input value={formatNumber(row.actual_month)} readOnly /></label>
        <label>Actual YTD <input value={formatNumber(row.actual_year)} readOnly /></label>
        <label>Monthly Target <TypedNumberInput name="target_month" step="0.01" defaultValue={row.target_month || ""} /></label>
        <label>Yearly Target <TypedNumberInput name="target_year" step="0.01" defaultValue={row.target_year || ""} /></label>
        {error && <div className="import-alert danger">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="secondary-button" onClick={onClose} disabled={isSaving}>Cancel</button>
          <button type="submit" className="primary-button" disabled={isSaving}>
            {isSaving ? "Saving..." : "Save KPI"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
