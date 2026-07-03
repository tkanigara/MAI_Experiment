import Modal, { ModalHeader } from "./Modal";

export default function DeleteClientModal({ client, isDeleting, onClose, onConfirm }) {
  const closeHandler = isDeleting ? () => {} : onClose;
  return (
    <Modal onClose={closeHandler}>
      <ModalHeader
        title="Delete Client"
        subtitle="This action will remove the client and all related dashboard data."
        onClose={closeHandler}
      />
      <div className="modal-body">
        <div className="delete-confirm-box">
          <strong>{client?.client_name}</strong>
        </div>
        <div className="modal-actions">
          <button type="button" className="secondary-button" onClick={onClose} disabled={isDeleting}>
            Cancel
          </button>
          <button type="button" className="danger-button" onClick={onConfirm} disabled={isDeleting}>
            {isDeleting ? "Deleting..." : "Delete Client"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
