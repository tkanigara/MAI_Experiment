import Modal, { ModalHeader } from "./Modal";

export default function DeleteClientModal({ client, isDeleting, onClose, onConfirm }) {
  const closeHandler = isDeleting ? () => {} : onClose;
  const isSharedWithAds = (client?.products || []).includes("meta_ads");
  return (
    <Modal onClose={closeHandler}>
      <ModalHeader
        title={isSharedWithAds ? "Remove from Social Media" : "Delete Client"}
        subtitle={isSharedWithAds
          ? "The shared client and its Meta Ads data will remain available in the Ads workspace."
          : "This action will remove the client and all related dashboard data."}
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
            {isDeleting
              ? (isSharedWithAds ? "Removing..." : "Deleting...")
              : (isSharedWithAds ? "Remove from Social Media" : "Delete Client")}
          </button>
        </div>
      </div>
    </Modal>
  );
}
