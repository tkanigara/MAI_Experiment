export default function MissingDataModal({ platformLabel, missingData, onClose }) {
  const items = missingData?.items || [];

  return (
    <>
      <div className="modal-backdrop" onClick={onClose} />
      <section className="modal data-check-modal" role="dialog" aria-modal="true">
        <div className="modal-head">
          <div>
            <h2>Missing Data</h2>
            <p>{platformLabel} fields that are still empty in the latest report.</p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close">x</button>
        </div>
        <div className="modal-body">
          <div className={`data-health-card ${items.length ? "is-partial" : "is-complete"}`}>
            <strong>{items.length ? `${items.length} fields need attention` : "All key fields are filled"}</strong>
            <span>{items.length ? "These values are NULL or empty in the database." : "No empty key fields found for this platform."}</span>
          </div>
          {items.length ? (
            <div className="missing-data-list">
              {items.map((item) => (
                <div className="missing-data-row" key={item.field}>
                  <div>
                    <span>{item.label}</span>
                    {item.total_count ? (
                      <small>{item.missing_count} of {item.total_count} posts are empty</small>
                    ) : null}
                  </div>
                  <code>{item.field}</code>
                </div>
              ))}
            </div>
          ) : null}
        </div>
        <div className="modal-actions sticky-actions">
          <span className="action-hint">This only checks report data fields, not insight text, SEO, or ads.</span>
          <button className="secondary-button" onClick={onClose}>Close</button>
        </div>
      </section>
    </>
  );
}
