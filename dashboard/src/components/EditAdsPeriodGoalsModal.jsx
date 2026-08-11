import { useState } from "react";
import AdsPeriodGoalFields, { initialAdsPeriodGoals, serializeAdsPeriodGoals } from "./AdsPeriodGoalFields";
import Modal, { ModalHeader } from "./Modal";

export default function EditAdsPeriodGoalsModal({ client, period, onClose, onSave }) {
  const [goals, setGoals] = useState(() => initialAdsPeriodGoals(client, period));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    const adsGoals = serializeAdsPeriodGoals(goals, client);
    if (!Object.values(adsGoals).some((items) => items.length)) {
      setError("Select at least one Ads goal for this report month.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await onSave({ ads_goals: adsGoals });
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <Modal onClose={onClose} wide>
      <ModalHeader title={`Edit ${period.period_label} Goals & KPI`} subtitle="These settings apply only to this report month." onClose={onClose} />
      <form className="modal-body" onSubmit={submit}>
        <AdsPeriodGoalFields client={client} goals={goals} onChange={setGoals} />
        {error && <div className="import-alert danger">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Cancel</button>
          <button type="submit" className="primary-button" disabled={saving}>{saving ? "Saving..." : "Save Goals & KPI"}</button>
        </div>
      </form>
    </Modal>
  );
}
