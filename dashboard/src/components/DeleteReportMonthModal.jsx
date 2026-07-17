import Modal, { ModalHeader } from "./Modal";

export default function DeleteReportMonthModal({ month, isDeleting, onClose, onConfirm }) {
  const closeHandler = isDeleting ? () => {} : onClose;
  return (
    <Modal onClose={closeHandler}>
      <ModalHeader
        title="Delete Report Month"
        subtitle="This action will remove all report data for this month. The client and other months will remain available."
        onClose={closeHandler}
      />
      <div className="modal-body">
        <div className="delete-confirm-box">
          <strong>{month?.label}</strong>
        </div>
        <div className="modal-actions">
          <button type="button" className="secondary-button" onClick={onClose} disabled={isDeleting}>
            Cancel
          </button>
          <button type="button" className="danger-button" onClick={onConfirm} disabled={isDeleting}>
            {isDeleting ? "Deleting..." : "Delete Report Month"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
