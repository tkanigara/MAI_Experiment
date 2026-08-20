import { useEffect } from "react";

export default function Modal({ children, onClose, wide = false }) {
  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const close = (event) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", close);
    return () => { document.body.style.overflow = previous; document.removeEventListener("keydown", close); };
  }, [onClose]);
  return (
    <>
      <div className="modal-backdrop" onClick={onClose} />
      <section className={`modal ${wide ? "modal-wide" : ""}`} role="dialog" aria-modal="true">{children}</section>
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
