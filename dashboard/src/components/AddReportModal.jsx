import { useState } from "react";
import { CSV_TYPES, KPI_METRICS, REPORT_MONTHS } from "../lib/constants";
import { api } from "../lib/api";
import { formatNumber, platformFlags, prettyMetric } from "../lib/format";
import { PlatformBadge, StatusBadge } from "./Badges";
import Modal, { ModalHeader } from "./Modal";
import TypedNumberInput from "./TypedNumberInput";

export default function AddReportModal({
  client,
  month,
  reportMonths = [],
  platformData,
  onClose,
  onImported,
  onUpdateMonth,
  onSaveKpiTargets,
  activePlatform,
  initialTab = "csv",
  onReportLocked,
}) {
  const isUpdateMode = Boolean(month?.id);
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().toLocaleString("en-US", { month: "long" });
  const defaultMonth = month?.slug
    || REPORT_MONTHS.find((item) => item.slug === `${currentMonth.toLowerCase()}-${currentYear}`)?.slug
    || REPORT_MONTHS.find((item) => item.slug.endsWith(`-${currentYear}`))?.slug
    || REPORT_MONTHS[0]?.slug;
  const defaultMonthName = REPORT_MONTHS.find((item) => item.slug === defaultMonth)?.label?.split(" ")[0] || currentMonth;
  const [tab, setTab] = useState(initialTab);
  const [files, setFiles] = useState({});
  const [draggingSlot, setDraggingSlot] = useState("");
  const [selectedYear, setSelectedYear] = useState(Number((defaultMonth || "").split("-").at(-1)) || currentYear);
  const [selectedMonthName, setSelectedMonthName] = useState(defaultMonthName);
  const [isImporting, setIsImporting] = useState(false);
  const [isSavingKpi, setIsSavingKpi] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [error, setError] = useState("");
  const platforms = platformFlags(client);
  const kpiPlatforms = activePlatform ? [activePlatform] : platforms;
  const existingFiles = month?.uploaded_csv_files || {};
  const selectedFileCount = CSV_TYPES.filter((item) => files[item.key]).length;
  const uploadedCount = CSV_TYPES.filter(
    (item) => files[item.key] || existingFiles[item.key],
  ).length;
  const warningCount = importResult?.summary?.warnings || 0;
  const monthNames = [...new Set(REPORT_MONTHS.map((item) => item.label.split(" ")[0]))];
  const yearOptions = [...new Set(REPORT_MONTHS.map((item) => Number(item.slug.split("-").at(-1))))];
  const selectedMonth = `${selectedMonthName.toLowerCase()}-${selectedYear}`;
  const selectedMonthNumber = new Date(`${selectedMonthName} 1, ${selectedYear}`).getMonth() + 1;
  const selectedMonthExists = reportMonths.some(
    (monthItem) => (
      String(monthItem.id) !== String(month?.id)
      && monthItem.slug === selectedMonth
    ),
  );
  const isMonthChanged = isUpdateMode && selectedMonth !== month?.slug;
  const canSaveCsv = !selectedMonthExists && (
    selectedFileCount > 0
    || (isUpdateMode && isMonthChanged)
  );

  function selectFile(key, file) {
    if (!file) return;
    setImportResult(null);
    setError("");
    setFiles((current) => ({ ...current, [key]: file }));
  }

  function removeFile(key) {
    setImportResult(null);
    setError("");
    setFiles((current) => {
      const nextFiles = { ...current };
      delete nextFiles[key];
      return nextFiles;
    });
  }

  function handleDragOver(event, key) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    setDraggingSlot(key);
  }

  function handleDrop(event, key) {
    event.preventDefault();
    setDraggingSlot("");
    selectFile(key, event.dataTransfer.files?.[0]);
  }

  async function importCsv() {
    if (!client?.id) return;
    if (selectedMonthExists) {
      setError(
        `${selectedMonthName} ${selectedYear} already exists for this client.`,
      );
      return;
    }
    setIsImporting(true);
    setError("");
    try {
      if (isUpdateMode && isMonthChanged && selectedFileCount === 0) {
        const updated = await onUpdateMonth?.(month, selectedMonth);
        if (updated !== false) onClose();
        return;
      }

      const formData = new FormData();
      formData.append("client_id", client.id);
      formData.append("month_slug", selectedMonth);
      if (isUpdateMode) formData.append("period_id", month.id);
      CSV_TYPES.forEach((item) => {
        if (files[item.key]) formData.append(item.key, files[item.key]);
      });
      const data = await api("/api/import/csv", {
        method: "POST",
        body: formData,
      });
      setImportResult(data);
      await onImported?.(data);
    } catch (err) {
      if (!onReportLocked?.(err)) setError(err.message);
    } finally {
      setIsImporting(false);
    }
  }

  async function saveKpiTargets(event) {
    event?.preventDefault();
    if (!client?.id) return;
    setIsSavingKpi(true);
    setError("");
    const formElement = event?.currentTarget?.tagName === "FORM"
      ? event.currentTarget
      : document.getElementById("kpi-target-form");
    const form = new FormData(formElement);
    const periodYear = selectedYear || currentYear;
    const targets = [];
    kpiPlatforms.forEach((platform) => {
      (KPI_METRICS[platform] || []).forEach((metric) => {
        const targetMonth = form.get(`${platform}:${metric}:target_month`);
        const targetYear = form.get(`${platform}:${metric}:target_year`);
        const existing = (platformData[platform]?.kpi_results || []).find((item) => item.metric_name === metric);
        const existingTarget = (platformData[platform]?.kpi_targets || []).find(
          (item) => item.metric_name === metric
            && Number(item.period_year) === Number(periodYear)
            && Number(item.period_month) === selectedMonthNumber,
        );
        if (targetMonth || targetYear || existing?.target_month || existing?.target_year) {
          targets.push({
            platform,
            metric_name: metric,
            period_year: periodYear,
            period_month: selectedMonthNumber,
            target_month: targetMonth || null,
            target_year: targetYear || null,
            unit: existingTarget?.unit || existing?.unit || "count",
          });
        }
      });
    });
    try {
      const saved = await onSaveKpiTargets?.(targets);
      if (saved === false) return;
      onClose();
    } catch (err) {
      if (!onReportLocked?.(err)) setError(err.message);
    } finally {
      setIsSavingKpi(false);
    }
  }

  return (
    <Modal wide onClose={onClose}>
      <ModalHeader
        title={isUpdateMode ? "Update Report Data" : "Add Report Data"}
        subtitle={isUpdateMode
          ? "Change the report month or replace selected CSV data."
          : "Upload monthly CSV files and define KPI targets for each connected platform."}
        onClose={onClose}
      />
      <div className="modal-context">
        <div>
          <span>Client</span>
          <strong>{client?.client_name || "Client"}</strong>
        </div>
        <div className="split-fields">
          <label>
            {tab === "csv" ? "Report Year" : "KPI Year"}
            <select value={selectedYear} onChange={(event) => setSelectedYear(Number(event.target.value))}>
              {yearOptions.map((year) => <option value={year} key={year}>{year}</option>)}
            </select>
          </label>
          <label>
            {tab === "csv" ? "Report Month" : "KPI Month"}
            <select value={selectedMonthName} onChange={(event) => setSelectedMonthName(event.target.value)}>
              {monthNames.map((monthName) => <option value={monthName} key={monthName}>{monthName}</option>)}
            </select>
          </label>
          {tab === "csv" && selectedMonthExists ? (
            <span className="field-note danger-text">
              This report month already exists.
            </span>
          ) : null}
        </div>
      </div>
      <div className="tabs">
        <button className={`tab ${tab === "csv" ? "active" : ""}`} onClick={() => setTab("csv")} type="button">
          CSV Files ({uploadedCount}/{CSV_TYPES.length})
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
                <strong>
                  {isUpdateMode
                    ? `${uploadedCount} of ${CSV_TYPES.length} CSV files available`
                    : `${selectedFileCount} of ${CSV_TYPES.length} CSV files selected`}
                </strong>
                <span>
                  {isUpdateMode
                    ? selectedFileCount
                      ? `${selectedFileCount} replacement file${selectedFileCount === 1 ? "" : "s"} selected.`
                      : isMonthChanged
                        ? "The report month will be updated without replacing CSV data."
                        : "Choose a file to replace existing data, or change the report month."
                    : selectedFileCount
                      ? "Ready to save selected files into the database."
                      : "Choose CSV files first."}
                </span>
              </div>
              <button
                type="button"
                className="primary-button"
                disabled={isImporting || !canSaveCsv}
                onClick={importCsv}
              >
                {isImporting
                  ? "Saving..."
                  : isUpdateMode
                    ? "Save Changes"
                    : "Save CSV Data"}
              </button>
            </div>
            <div className="upload-list">
              {CSV_TYPES.map(({ key, title, description, optional }) => {
                const result = importResult?.files?.find((item) => item.slot === key);
                const hasWarning = (result?.warnings || []).length > 0;
                const selectedFile = files[key];
                const existingFilename = existingFiles[key];
                const displayedFilename = selectedFile?.name || existingFilename;
                const hasStoredFile = Boolean(existingFilename && !selectedFile);
                const uploadStatus = selectedFile
                  ? (hasWarning ? { text: "Partial", state: "warning" } : { text: "Ready", state: "success" })
                  : hasStoredFile
                    ? { text: "Uploaded", state: "neutral" }
                    : optional
                      ? { text: "Optional", state: "neutral" }
                      : { text: "Required", state: "warning" };
                return (
                  <div
                    className={`upload-row ${draggingSlot === key ? "is-dragging" : ""}`}
                    key={key}
                    onDragEnter={(event) => handleDragOver(event, key)}
                    onDragOver={(event) => handleDragOver(event, key)}
                    onDragLeave={() => setDraggingSlot("")}
                    onDrop={(event) => handleDrop(event, key)}
                  >
                    <div className="upload-icon">{displayedFilename ? "ok" : "csv"}</div>
                    <div>
                      <div className="upload-title">{title}</div>
                      <div className="upload-desc">
                        {displayedFilename || description}
                        {result?.rows ? ` - ${result.rows} rows` : ""}
                      </div>
                      {!displayedFilename && <div className="drop-hint">Drop CSV here or choose a file</div>}
                      {hasStoredFile && (
                        <div className="drop-hint">Choose a new file only if this data needs to be replaced</div>
                      )}
                      {hasWarning && (
                        <ul className="warning-list compact">
                          {result.warnings.slice(0, 2).map((warning) => <li key={warning}>{warning}</li>)}
                        </ul>
                      )}
                    </div>
                    <StatusBadge
                      text={uploadStatus.text}
                      state={uploadStatus.state}
                    />
                    <div className="upload-actions">
                      <label className="file-button">
                        {displayedFilename ? "Replace" : "Choose"}
                        <input
                          type="file"
                          accept=".csv,text/csv"
                          onChange={(event) => {
                            selectFile(key, event.target.files?.[0]);
                            event.target.value = "";
                          }}
                        />
                      </label>
                      {!isUpdateMode && selectedFile ? (
                        <button
                          type="button"
                          className="danger-link upload-remove-button"
                          onClick={() => removeFile(key)}
                        >
                          Remove
                        </button>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
            {error && <div className="import-alert danger">{error}</div>}
            {importResult && (
              <section className="import-result">
                <div>
                  <strong>
                    {isUpdateMode
                      ? `${importResult.summary.uploaded} CSV file${importResult.summary.uploaded === 1 ? "" : "s"} updated`
                      : `${importResult.summary.uploaded} of ${importResult.summary.expected} files imported`}
                  </strong>
                  <span>{warningCount ? `${warningCount} warnings found` : "No warnings found"}</span>
                </div>
                {!!importResult.summary.missing_files?.length && (
                  <p>Missing files: {importResult.summary.missing_files.join(", ")}</p>
                )}
                <p>
                  {importResult.summary.platform_reports
                    ? `${Object.keys(importResult.summary.platform_reports).length} platform reports updated. `
                    : ""}
                  {importResult.summary.competitor_rows || 0} competitor profiles and {importResult.summary.competitor_content_rows || 0} competitor posts stored.
                </p>
                {importResult.summary.content_breakdown ? (
                  <div className="import-platform-breakdown">
                    {Object.entries(importResult.summary.content_breakdown.detected || {}).map(([platform, count]) => (
                      <span key={platform}>{platform}: {count} rows</span>
                    ))}
                    {(importResult.summary.content_breakdown.unknown_count || 0) > 0 ? (
                      <span>{importResult.summary.content_breakdown.unknown_count} unknown rows skipped</span>
                    ) : null}
                  </div>
                ) : null}
              </section>
            )}
          </>
        ) : (
          <form id="kpi-target-form" className="kpi-target-list" onSubmit={saveKpiTargets}>
            <div className="csv-action-bar">
              <div>
                <strong>Update KPI targets only</strong>
                <span>This does not require uploading CSV files.</span>
              </div>
              <button type="submit" className="primary-button" disabled={isSavingKpi}>
                {isSavingKpi ? "Saving..." : "Save KPI Targets"}
              </button>
            </div>
            {kpiPlatforms.map((platform) => (
              <section className="kpi-target-card" key={`${platform}-${selectedYear}`}>
                <h3><PlatformBadge platform={platform} /> KPI Targets</h3>
                {(KPI_METRICS[platform] || []).map((metric) => {
                  const targetRow = (platformData[platform]?.kpi_targets || []).find(
                    (item) => item.metric_name === metric
                      && Number(item.period_year) === Number(selectedYear)
                      && Number(item.period_month) === selectedMonthNumber,
                  ) || {};
                  const row = (platformData[platform]?.kpi_results || []).find((item) => item.metric_name === metric) || {};
                  return (
                    <div className="kpi-target-row" key={metric}>
                      <strong>{prettyMetric(metric)}</strong>
                      <span className="muted">
                        Actual month / YTD: {formatNumber(row.actual_month)} / {formatNumber(row.actual_year)}
                      </span>
                      <TypedNumberInput
                        name={`${platform}:${metric}:target_month`}
                        step="0.01"
                        defaultValue={targetRow.target_month || row.target_month || ""}
                        placeholder="Monthly target"
                      />
                      <TypedNumberInput
                        name={`${platform}:${metric}:target_year`}
                        step="0.01"
                        defaultValue={targetRow.target_year || row.target_year || ""}
                        placeholder="Yearly target"
                      />
                    </div>
                  );
                })}
              </section>
            ))}
            {error && <div className="import-alert danger">{error}</div>}
          </form>
        )}
      </div>
      <div className="modal-actions sticky-actions">
        <span className="action-hint">
          {tab === "csv"
            ? selectedMonthExists
              ? "Choose a report month that does not already exist."
              : selectedFileCount
                ? `${selectedFileCount} file${selectedFileCount === 1 ? "" : "s"} selected for saving.`
                : isUpdateMode && isMonthChanged
                  ? "Save to update the report month without replacing CSV data."
                  : isUpdateMode
                    ? "Choose a replacement file or change the report month."
                    : "Choose at least one CSV file to import."
            : "Save KPI targets independently from CSV upload."}
        </span>
        <div>
          <button type="button" className="secondary-button" onClick={onClose}>Cancel</button>
          <button
            type="button"
            className="primary-button"
            disabled={tab === "csv" ? isImporting || !canSaveCsv : isSavingKpi}
            onClick={tab === "csv" ? importCsv : saveKpiTargets}
          >
            {tab === "csv"
              ? isImporting
                ? "Saving..."
                : isUpdateMode
                  ? "Save Changes"
                  : "Save CSV Data"
              : isSavingKpi ? "Saving..." : "Save KPI Targets"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
