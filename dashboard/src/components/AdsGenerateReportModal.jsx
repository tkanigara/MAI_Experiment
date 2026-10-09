import Modal, { ModalHeader } from "./Modal";

const MODEL_OPTIONS = [
  {
    value: "jba",
    label: "JBA · Ad Set performance",
    help: "Campaign and Ad Set comparison, with creative drilldown.",
  },
  {
    value: "dunlop",
    label: "DUNLOP · Creative performance",
    help: "Platform-specific creative, placement, audience, and region views.",
  },
];

export default function AdsGenerateReportModal({
  client,
  period,
  isSubmitting,
  onClose,
  onConfirm,
}) {
  const closeHandler = isSubmitting ? () => {} : onClose;
  return (
    <Modal onClose={closeHandler}>
      <ModalHeader
        title="Generate Ads report"
        subtitle="Choose the report layout and data scope for this period."
        onClose={closeHandler}
      />
      <div className="modal-body generation-confirm-body ads-generation-modal">
        <div className="generation-confirm-target">
          <strong>{client?.client_name || "-"}</strong>
          <span>{period?.period_label || "-"}</span>
        </div>
        <label className="field">
          <span>Report layout</span>
          <select name="report_model" defaultValue="jba">
            {MODEL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <small>JBA is selected by default. DUNLOP keeps Instagram/Facebook creative sections separated.</small>
        </label>
        <label className="field">
          <span>Platform scope</span>
          <select name="platform_scope" defaultValue="meta">
            <option value="meta">All Meta (Instagram + Facebook)</option>
            <option value="instagram">Instagram</option>
            <option value="facebook">Facebook</option>
          </select>
        </label>
        <p className="generation-confirm-copy">
          The report uses the active Ads snapshot and the confirmed objective for this period. You can change the source from Data Sources before generating.
        </p>
        <div className="modal-actions">
          <button type="button" className="secondary-button" onClick={onClose} disabled={isSubmitting}>Cancel</button>
          <button
            type="button"
            className="primary-button"
            disabled={isSubmitting}
            onClick={(event) => {
              const form = event.currentTarget.closest(".ads-generation-modal");
              onConfirm({
                report_model: form?.querySelector("[name='report_model']")?.value || "jba",
                platform_scope: form?.querySelector("[name='platform_scope']")?.value || "meta",
              });
            }}
          >
            {isSubmitting ? "Adding to queue..." : "Generate report"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
