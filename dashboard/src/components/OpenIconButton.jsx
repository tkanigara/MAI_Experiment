import shareIcon from "./logo/share.png";

export default function OpenIconButton({ label, onClick }) {
  return (
    <button className="open-icon-button" type="button" onClick={onClick} aria-label={label} title={label}>
      <img src={shareIcon} alt="" />
    </button>
  );
}
