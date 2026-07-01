export default function Modal({ children, onClose, wide = false }) {
  return (
    <>
      <div className="modal-backdrop" onClick={onClose} />
      <section className={`modal ${wide ? "modal-wide" : ""}`}>{children}</section>
    </>
  );
}

export function ModalHeader({ title, subtitle, onClose }) {
  return (
    <div className="modal-head">
      <div>
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      <button className="icon-button modal-close" type="button" onClick={onClose}>
        x
      </button>
    </div>
  );
}
