import Modal, { ModalHeader } from "./Modal";

export default function GenerateReportModal({
  client,
  month,
  platforms = [],
  isSubmitting,
  onClose,
  onConfirm,
}) {
  const platformReportCount = Number(month?.platform_reports || 0);
  const hasReportData = platformReportCount > 0;
  const hasPartialData = (
    hasReportData
    && platforms.length > 0
    && platformReportCount < platforms.length
  );
  const closeHandler = isSubmitting ? () => {} : onClose;

  return (
    <Modal onClose={closeHandler}>
      <ModalHeader
        title="Generate report?"
        subtitle="Please confirm the report you want to generate."
        onClose={closeHandler}
      />
      <div className="modal-body generation-confirm-body">
        <div className="generation-confirm-target">
          <strong>{client?.client_name || "-"}</strong>
          <span>{month?.label || "-"}</span>
        </div>

        {!hasReportData && (
          <div className="data-health-card is-blocked">
            <strong>Report data is not ready</strong>
            <span>Import report data for this period before generating.</span>
          </div>
        )}
        {hasPartialData && (
          <div className="data-health-card is-partial">
            <strong>Some platform data may be incomplete</strong>
            <span>The report can still be generated.</span>
          </div>
        )}

        <p className="generation-confirm-copy">
          Gemini will analyze this report data and create a Google Slides presentation.
        </p>

        <div className="modal-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="primary-button"
            onClick={onConfirm}
            disabled={!hasReportData || isSubmitting}
          >
            {isSubmitting ? "Adding to queue..." : "Generate report"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
