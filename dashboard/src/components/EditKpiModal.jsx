import Modal, { ModalHeader } from "./Modal";
import { formatNumber, prettyMetric } from "../lib/format";

export default function EditKpiModal({ row, onClose, onSave }) {
  function handleSubmit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSave({
      metric_name: row.metric_name,
      target_month: form.get("target_month"),
      unit: form.get("unit"),
    });
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
        <label>Actual <input value={formatNumber(row.actual_month)} readOnly /></label>
        <label>Monthly Target <input name="target_month" type="number" step="0.01" defaultValue={row.target_month || ""} /></label>
        <label>Unit <input name="unit" defaultValue={row.unit || "count"} /></label>
        <div className="modal-actions">
          <button type="button" className="secondary-button" onClick={onClose}>Cancel</button>
          <button type="submit" className="primary-button">Save KPI</button>
        </div>
      </form>
    </Modal>
  );
}
