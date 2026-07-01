import { useState } from "react";
import { CSV_TYPES, KPI_METRICS, REPORT_MONTHS } from "../lib/constants";
import { formatNumber, platformFlags, prettyMetric } from "../lib/format";
import { PlatformBadge, StatusBadge } from "./Badges";
import Modal, { ModalHeader } from "./Modal";

export default function AddReportModal({
  client,
  month,
  reportMonths = [],
  platformData,
  onClose,
  onImported,
  initialTab = "csv",
}) {
  const [tab, setTab] = useState(initialTab);
  const [files, setFiles] = useState({});
  const [selectedMonth, setSelectedMonth] = useState(month?.slug || REPORT_MONTHS[0]?.slug);
  const [isImporting, setIsImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [error, setError] = useState("");
  const platforms = platformFlags(client);
  const uploadedCount = CSV_TYPES.filter((item) => files[item.key]).length;
  const warningCount = importResult?.summary?.warnings || 0;
  const monthOptions = [
    ...reportMonths,
    ...REPORT_MONTHS.filter((item) => !reportMonths.some((monthItem) => monthItem.slug === item.slug)),
  ];

  function selectFile(key, file) {
    setImportResult(null);
    setError("");
    setFiles((current) => ({ ...current, [key]: file }));
  }

  async function importCsv() {
    if (!client?.id) return;
    setIsImporting(true);
    setError("");
    const formData = new FormData();
    formData.append("client_id", client.id);
    formData.append("month_slug", selectedMonth);
    CSV_TYPES.forEach((item) => {
      if (files[item.key]) formData.append(item.key, files[item.key]);
    });
    try {
      const response = await fetch("/api/import/csv", {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Import failed");
      setImportResult(data);
      await onImported?.(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsImporting(false);
    }
  }

  return (
    <Modal wide onClose={onClose}>
      <ModalHeader
        title="Add Report Data"
        subtitle="Upload monthly CSV files and define KPI targets for each connected platform."
        onClose={onClose}
      />
      <div className="modal-context">
        <div>
          <span>Client</span>
          <strong>{client?.client_name || "Client"}</strong>
        </div>
        <label>
          Report Month
          <select value={selectedMonth} onChange={(event) => setSelectedMonth(event.target.value)}>
            {monthOptions.map((item) => <option value={item.slug} key={item.slug}>{item.label}</option>)}
          </select>
        </label>
      </div>
      <div className="tabs">
        <button className={`tab ${tab === "csv" ? "active" : ""}`} onClick={() => setTab("csv")} type="button">
          CSV Files ({uploadedCount}/7)
        </button>
        <button className={`tab ${tab === "kpi" ? "active" : ""}`} onClick={() => setTab("kpi")} type="button">
          KPI Targets
        </button>
      </div>
      <div className="modal-scroll">
        {tab === "csv" ? (
          <>
            <div className="csv-action-bar">
              <div>
                <strong>{uploadedCount} of 7 CSV files selected</strong>
                <span>{uploadedCount ? "Ready to save selected files into the database." : "Choose CSV files first."}</span>
              </div>
              <button
                type="button"
                className="primary-button"
                disabled={isImporting || uploadedCount === 0}
                onClick={importCsv}
              >
                {isImporting ? "Saving..." : "Save CSV Data"}
              </button>
            </div>
            <div className="upload-list">
              {CSV_TYPES.map(({ key, title, description }) => {
                const result = importResult?.files?.find((item) => item.slot === key);
                const hasWarning = (result?.warnings || []).length > 0;
                return (
                  <div className="upload-row" key={key}>
                    <div className="upload-icon">{files[key] ? "ok" : "csv"}</div>
                    <div>
                      <div className="upload-title">{title}</div>
                      <div className="upload-desc">
                        {files[key]?.name || description}
                        {result?.rows ? ` - ${result.rows} rows` : ""}
                      </div>
                      {hasWarning && (
                        <ul className="warning-list compact">
                          {result.warnings.slice(0, 2).map((warning) => <li key={warning}>{warning}</li>)}
                        </ul>
                      )}
                    </div>
                    <StatusBadge
                      text={files[key] ? (hasWarning ? "Partial" : "Ready") : "Required"}
                      state={files[key] ? (hasWarning ? "partial" : "ready") : "partial"}
                    />
                    <label className="file-button">
                      Choose
                      <input
                        type="file"
                        accept=".csv,text/csv"
                        onChange={(event) => selectFile(key, event.target.files?.[0])}
                      />
                    </label>
                  </div>
                );
              })}
            </div>
            {error && <div className="import-alert danger">{error}</div>}
            {importResult && (
              <section className="import-result">
                <div>
                  <strong>{importResult.summary.uploaded} of {importResult.summary.expected} files imported</strong>
                  <span>{warningCount ? `${warningCount} warnings found` : "No warnings found"}</span>
                </div>
                {!!importResult.summary.missing_files?.length && (
                  <p>Missing files: {importResult.summary.missing_files.join(", ")}</p>
                )}
                <p>
                  {importResult.summary.platform_reports
                    ? `${Object.keys(importResult.summary.platform_reports).length} platform reports updated. `
                    : ""}
                  {importResult.summary.competitor_rows || 0} competitor rows stored.
                </p>
              </section>
            )}
          </>
        ) : (
          <div className="kpi-target-list">
            {platforms.map((platform) => (
              <section className="kpi-target-card" key={platform}>
                <h3><PlatformBadge platform={platform} /> KPI Targets</h3>
                {(KPI_METRICS[platform] || []).map((metric) => {
                  const row = (platformData[platform]?.kpi_results || []).find((item) => item.metric_name === metric) || {};
                  return (
                    <div className="kpi-target-row" key={metric}>
                      <strong>{prettyMetric(metric)}</strong>
                      <span className="muted">Actual: {formatNumber(row.actual_month)}</span>
                      <input defaultValue={row.target_month || ""} placeholder="Target" />
                    </div>
                  );
                })}
              </section>
            ))}
          </div>
        )}
      </div>
      <div className="modal-actions sticky-actions">
        <span className="action-hint">
          {uploadedCount ? `${uploadedCount} file selected. Click import to save into database.` : "Choose at least one CSV file to import."}
        </span>
        <div>
          <button type="button" className="secondary-button" onClick={onClose}>Cancel</button>
          <button
            type="button"
            className="primary-button"
            disabled={isImporting || uploadedCount === 0}
            onClick={tab === "csv" ? importCsv : onClose}
          >
            {isImporting ? "Saving..." : tab === "csv" ? "Save CSV Data" : "Done"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
