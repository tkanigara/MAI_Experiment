import Modal, { ModalHeader } from "./Modal";

export default function DeleteClientModal({ client, workspace = "social", isDeleting, onClose, onConfirm }) {
  const closeHandler = isDeleting ? () => {} : onClose;
  const isAdsWorkspace = workspace === "ads";
  const isShared = (client?.products || []).includes(isAdsWorkspace ? "social_media" : "meta_ads");
  const workspaceLabel = isAdsWorkspace ? "Ads" : "Social Media";
  const otherWorkspaceLabel = isAdsWorkspace ? "Social Media" : "Ads";
  return (
    <Modal onClose={closeHandler}>
      <ModalHeader
        title={isShared ? `Remove from ${workspaceLabel}` : "Delete Client"}
        subtitle={isShared
          ? `The shared client and its ${otherWorkspaceLabel} data will remain available in the ${otherWorkspaceLabel} workspace.`
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
              ? (isShared ? "Removing..." : "Deleting...")
              : (isShared ? `Remove from ${workspaceLabel}` : "Delete Client")}
          </button>
        </div>
      </div>
    </Modal>
  );
}
