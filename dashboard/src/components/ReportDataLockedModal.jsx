import Modal, { ModalHeader } from "./Modal";

export default function ReportDataLockedModal({
  clientName,
  periodLabel,
  job,
  onClose,
  onOpenHistory,
}) {
  const context = [clientName, periodLabel].filter(Boolean).join(" — ");
  const status = String(job?.status || "running").replaceAll("_", " ");

  return (
    <Modal onClose={onClose}>
      <ModalHeader
        title="Report sedang dibuat"
        subtitle={context || "Data report sementara dikunci."}
        onClose={onClose}
      />
      <div className="modal-body">
        <p>
          Data tidak dapat diubah sampai proses generate selesai atau
          dibatalkan. Perubahan yang belum disimpan tetap aman di halaman ini.
        </p>
        <div className="report-lock-summary">
          <span>Status generation</span>
          <strong>{status}</strong>
        </div>
        <div className="modal-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={onClose}
          >
            Tutup
          </button>
          <button
            type="button"
            className="primary-button"
            onClick={onOpenHistory}
          >
            Lihat Report History
          </button>
        </div>
      </div>
    </Modal>
  );
}
