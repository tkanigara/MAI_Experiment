export default function Breadcrumb({ items, onNavigate }) {
  return (
    <nav className="breadcrumb">
      {items.map((item, index) => (
        <span className="crumb" key={`${item.label}-${index}`}>
          {index > 0 && <span className="crumb-separator">&gt;</span>}
          {item.path ? (
            <button type="button" onClick={() => onNavigate(item.path)}>
              {item.label}
            </button>
          ) : (
            <strong>{item.label}</strong>
          )}
        </span>
      ))}
    </nav>
  );
}
