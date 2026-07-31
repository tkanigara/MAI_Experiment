import { useEffect, useMemo, useState } from "react";
import AddClientModal from "./components/AddClientModal";
import AddReportModal from "./components/AddReportModal";
import DeleteClientModal from "./components/DeleteClientModal";
import DeleteReportMonthModal from "./components/DeleteReportMonthModal";
import EditKpiModal from "./components/EditKpiModal";
import GenerateReportModal from "./components/GenerateReportModal";
import Header from "./components/Header";
import ReportDataLockedModal from "./components/ReportDataLockedModal";
import { api } from "./lib/api";
import { clientSlug, platformFlags } from "./lib/format";
import ClientDetailPage from "./pages/ClientDetailPage";
import ClientsPage from "./pages/ClientsPage";
import MonthDetailPage from "./pages/MonthDetailPage";
import PlatformDetailPage from "./pages/PlatformDetailPage";
import ReportDataEditorPage from "./pages/ReportDataEditorPage";
import ReportJobsPage, {
  isActiveReportJob,
  reportJobStageLabel,
  reportJobStatusLabel,
} from "./pages/ReportJobsPage";

function routeParts() {
  return window.location.pathname.split("/").filter(Boolean);
}

export default function App() {
  const [clients, setClients] = useState([]);
  const [query, setQuery] = useState("");
  const [industry, setIndustry] = useState("");
  const [route, setRoute] = useState(routeParts());
  const [selectedClient, setSelectedClient] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [reportMonths, setReportMonths] = useState([]);
  const [platformData, setPlatformData] = useState({});
  const [modal, setModal] = useState(null);
  const [generateReportTarget, setGenerateReportTarget] = useState(null);
  const [toast, setToast] = useState("");
  const [editKpi, setEditKpi] = useState(null);
  const [editClient, setEditClient] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeletingClient, setIsDeletingClient] = useState(false);
  const [deleteReportMonthTarget, setDeleteReportMonthTarget] = useState(null);
  const [isDeletingReportMonth, setIsDeletingReportMonth] = useState(false);
  const [reportJobs, setReportJobs] = useState([]);
  const [focusedReportJobId, setFocusedReportJobId] = useState("");
  const [reportJobActionId, setReportJobActionId] = useState("");
  const [reportElapsed, setReportElapsed] = useState(0);
  const [reportDataLock, setReportDataLock] = useState(null);
  const [error, setError] = useState("");

  const industries = useMemo(
    () => [...new Set(clients.map((client) => client.industry).filter(Boolean))],
    [clients],
  );

  const currentClientSlug = route[0] === "clients" ? route[1] : null;
  const currentClient = useMemo(
    () => clients.find((client) => client.client_code === currentClientSlug || client.id === currentClientSlug),
    [clients, currentClientSlug],
  );
  const isGlobalReportJobs = route[0] === "report-jobs";
  const isClientReportJobs = route[0] === "clients" && route[2] === "report-jobs";
  const currentMonth = isClientReportJobs
    ? null
    : reportMonths.find((month) => month.slug === route[2]);
  const currentPlatform = route[3];
  const isReportEditor = currentPlatform === "edit";
  const isLegacyPeriodReportJobs = currentPlatform === "jobs";
  const reportJob = reportJobs.find((job) => job.id === focusedReportJobId);
  const activeReportPeriodIds = useMemo(
    () => new Set(
      reportJobs
        .filter(isActiveReportJob)
        .map((job) => String(job.report_period_id)),
    ),
    [reportJobs],
  );
  const activeReportJobIdsKey = reportJobs
    .filter(isActiveReportJob)
    .map((job) => job.id)
    .sort()
    .join(",");

  function activeJobForPeriod(periodId) {
    return reportJobs.find(
      (job) => (
        String(job.report_period_id) === String(periodId)
        && isActiveReportJob(job)
      ),
    );
  }

  function showReportDataLock(job, fallback = {}) {
    if (job?.id) mergeReportJobs([job]);
    const clientId = job?.client_id || fallback.client?.id || selectedClient?.id;
    const lockClient = clients.find(
      (client) => String(client.id) === String(clientId),
    ) || fallback.client || selectedClient;
    const lockMonth = fallback.month || reportMonths.find(
      (month) => String(month.id) === String(job?.report_period_id),
    );
    setReportDataLock({
      job: job || {},
      clientId,
      clientName: job?.client_name_snapshot || lockClient?.client_name,
      periodLabel: job?.period_label_snapshot || lockMonth?.label,
    });
  }

  function handleReportDataLock(errorValue, fallback = {}) {
    if (errorValue?.code !== "REPORT_PERIOD_LOCKED") return false;
    showReportDataLock(errorValue.job, fallback);
    return true;
  }

  function runWhenPeriodUnlocked(month, action) {
    const activeJob = activeJobForPeriod(month?.id);
    if (activeJob) {
      showReportDataLock(activeJob, { client: selectedClient, month });
      return false;
    }
    action?.();
    return true;
  }

  function runWhenClientUnlocked(client, action) {
    const activeJob = reportJobs.find(
      (job) => (
        String(job.client_id) === String(client?.id)
        && isActiveReportJob(job)
      ),
    );
    if (activeJob) {
      showReportDataLock(activeJob, { client });
      return false;
    }
    action?.();
    return true;
  }

  function navigate(path, replace = false) {
    if (window.location.pathname !== path) {
      window.history[replace ? "replaceState" : "pushState"]({}, "", path);
    }
    setRoute(routeParts());
  }

  function showToast(message) {
    setToast(message);
    window.setTimeout(() => setToast(""), 2400);
  }

  function formatElapsed(seconds) {
    const safeSeconds = Math.max(0, Number(seconds) || 0);
    const minutes = Math.floor(safeSeconds / 60);
    const remainder = safeSeconds % 60;
    if (!minutes) return `${remainder}s`;
    return `${minutes}m ${String(remainder).padStart(2, "0")}s`;
  }

  function sortReportJobs(rows) {
    return [...rows].sort((left, right) => {
      const leftTime = new Date(left.created_at || left.queued_at || 0).getTime();
      const rightTime = new Date(right.created_at || right.queued_at || 0).getTime();
      return rightTime - leftTime;
    });
  }

  function mergeReportJobs(rows, replacePeriodId = "") {
    setReportJobs((current) => {
      const merged = new Map(
        current
          .filter((job) => (
            !replacePeriodId
            || String(job.report_period_id) !== String(replacePeriodId)
          ))
          .map((job) => [job.id, job]),
      );
      rows.filter(Boolean).forEach((job) => merged.set(job.id, job));
      return sortReportJobs([...merged.values()]);
    });
  }

  function replaceReportJobs(jobs) {
    const sortedJobs = sortReportJobs(jobs);
    setReportJobs(sortedJobs);
    setFocusedReportJobId((current) => {
      if (current && sortedJobs.some((job) => job.id === current)) {
        return current;
      }
      return sortedJobs.find(isActiveReportJob)?.id || "";
    });
    return sortedJobs;
  }

  async function loadClientReportJobs(client) {
    if (!client?.id || String(client.id).startsWith("local-")) {
      setReportJobs([]);
      return [];
    }
    const jobs = await api(
      `/api/clients/${client.id}/report-jobs?limit=100`,
    );
    return replaceReportJobs(jobs);
  }

  async function loadGlobalReportJobs() {
    const jobs = await api("/api/report-jobs?limit=100");
    return replaceReportJobs(jobs);
  }

  async function refreshVisibleReportJobs() {
    if (isGlobalReportJobs) return loadGlobalReportJobs();
    if (selectedClient) return loadClientReportJobs(selectedClient);
    return [];
  }

  function openPresentation(presentationUrl) {
    if (presentationUrl) {
      window.open(presentationUrl, "_blank", "noopener,noreferrer");
    }
  }

  async function loadClients() {
    const rows = await api("/api/clients");
    setClients(rows);
    if (!routeParts().length) navigate("/clients", true);
  }

  async function loadClient(client) {
    if (!client) return;
    if (String(client.id).startsWith("local-")) {
      setSelectedClient(client);
      setProfiles(platformFlags(client).map((platform) => ({
        id: `${client.id}-${platform}`,
        platform,
        profile_name: `${client.client_name} ${platform}`,
      })));
      setReportMonths([]);
      return;
    }
    const payload = await api(`/api/clients/${client.id}/platforms`);
    setSelectedClient(payload.client);
    setProfiles(payload.profiles);
    setReportMonths(payload.report_months || []);
  }

  async function loadPlatformData(client) {
    if (!client) return;
    const periodQuery = currentMonth?.id ? `?period_id=${encodeURIComponent(currentMonth.id)}` : "";
    const entries = await Promise.all(
      platformFlags(client).map(async (platform) => {
        try {
          return [platform, await api(`/api/clients/${client.id}/platforms/${platform}/overview${periodQuery}`)];
        } catch {
          return [platform, { platform, report: null, metrics: [], kpi_results: [], top_posts: [], low_posts: [] }];
        }
      }),
    );
    setPlatformData(Object.fromEntries(entries));
  }

  async function saveKpi(payload) {
    if (!selectedClient || !currentPlatform) return;
    const periodDate = new Date(`${currentMonth?.period_start || new Date().toISOString()}`);
    try {
      await api("/api/kpi-targets", {
        method: "POST",
        body: JSON.stringify({
          client_id: selectedClient.id,
          platform: currentPlatform,
          metric_name: payload.metric_name,
          period_year: periodDate.getUTCFullYear(),
          period_month: periodDate.getUTCMonth() + 1,
          target_month: payload.target_month,
          target_year: payload.target_year ?? editKpi?.target_year ?? null,
          unit: payload.unit,
        }),
      });
      setEditKpi(null);
      await loadPlatformData(selectedClient);
      showToast("KPI target updated.");
      return true;
    } catch (err) {
      if (handleReportDataLock(err, {
        client: selectedClient,
        month: currentMonth,
      })) return false;
      throw err;
    }
  }

  async function saveKpiTargets(targets) {
    if (!selectedClient) return;
    const validTargets = targets.filter((target) => (
      target.target_month !== null
      && target.target_month !== ""
    ) || (
      target.target_year !== null
      && target.target_year !== ""
    ));
    if (!validTargets.length) {
      showToast("No KPI target changes to save.");
      return;
    }
    try {
      await Promise.all(
        validTargets.map((target) => api("/api/kpi-targets", {
          method: "POST",
          body: JSON.stringify({
            client_id: selectedClient.id,
            platform: target.platform,
            metric_name: target.metric_name,
            period_year: target.period_year,
            period_month: target.period_month,
            target_month: target.target_month,
            target_year: target.target_year,
            unit: target.unit,
          }),
        })),
      );
      await loadPlatformData(selectedClient);
      showToast("KPI targets updated.");
      return true;
    } catch (err) {
      if (handleReportDataLock(err, {
        client: selectedClient,
        month: currentMonth,
      })) return false;
      throw err;
    }
  }

  async function deleteClient(client) {
    if (!client?.id) return;
    setIsDeletingClient(true);
    try {
      await api(`/api/clients/${client.id}`, { method: "DELETE" });
      await loadClients();
      if (selectedClient?.id === client.id || currentClient?.id === client.id) {
        setSelectedClient(null);
        setProfiles([]);
        setReportMonths([]);
        setPlatformData({});
        navigate("/clients");
      }
      setDeleteTarget(null);
      showToast("Client deleted.");
    } catch (err) {
      if (handleReportDataLock(err, { client })) {
        setDeleteTarget(null);
        return;
      }
      throw err;
    } finally {
      setIsDeletingClient(false);
    }
  }

  async function deleteReportMonth(month) {
    if (!selectedClient?.id || !month?.id) return;
    setIsDeletingReportMonth(true);
    try {
      await api(`/api/clients/${selectedClient.id}/report-periods/${month.id}`, { method: "DELETE" });
      await loadClient(selectedClient);
      setPlatformData({});
      setDeleteReportMonthTarget(null);
      showToast(`${month.label} report data deleted.`);
    } catch (err) {
      if (handleReportDataLock(err, {
        client: selectedClient,
        month,
      })) {
        setDeleteReportMonthTarget(null);
        return;
      }
      throw err;
    } finally {
      setIsDeletingReportMonth(false);
    }
  }

  function requestSlidesReportGeneration(month) {
    if (!selectedClient || !month?.id) return;
    const activeJob = reportJobs.find(
      (job) => (
        String(job.report_period_id) === String(month.id)
        && isActiveReportJob(job)
      ),
    );
    if (activeJob) {
      setFocusedReportJobId(activeJob.id);
      return;
    }
    setGenerateReportTarget(month);
  }

  async function generateSlidesReport(month) {
    if (!selectedClient || !month?.id) return false;
    const activeJob = reportJobs.find(
      (job) => (
        String(job.report_period_id) === String(month.id)
        && isActiveReportJob(job)
      ),
    );
    if (activeJob) {
      setFocusedReportJobId(activeJob.id);
      return true;
    }
    setReportJobActionId(`create:${month.id}`);
    try {
      const job = await api("/api/report-jobs", {
        method: "POST",
        body: JSON.stringify({
          client_id: selectedClient.id,
          period_id: month.id,
        }),
      });
      mergeReportJobs([job]);
      setFocusedReportJobId(job.id);
      setReportElapsed(0);
      return true;
    } catch (err) {
      const jobs = await loadClientReportJobs(selectedClient).catch(() => []);
      const activeJob = jobs.find(
        (job) => (
          String(job.report_period_id) === String(month.id)
          && isActiveReportJob(job)
        ),
      );
      if (activeJob) {
        setFocusedReportJobId(activeJob.id);
        return true;
      }
      showToast(err.message || "Failed to add report to queue.");
      return false;
    } finally {
      setReportJobActionId("");
    }
  }

  async function confirmSlidesReportGeneration() {
    if (!generateReportTarget) return;
    const wasQueued = await generateSlidesReport(generateReportTarget);
    if (wasQueued) setGenerateReportTarget(null);
  }

  async function cancelReportJob(job) {
    if (!job?.id || !isActiveReportJob(job)) return;
    setReportJobActionId(job.id);
    try {
      const updated = await api(`/api/report-jobs/${job.id}/cancel`, {
        method: "POST",
        body: JSON.stringify({
          reason: "Cancelled from dashboard",
        }),
      });
      mergeReportJobs([updated]);
      setFocusedReportJobId(updated.id);
    } catch (err) {
      const jobs = await refreshVisibleReportJobs().catch(() => []);
      const latest = jobs.find((item) => item.id === job.id);
      if (latest) setFocusedReportJobId(latest.id);
      showToast(err.message || "Failed to cancel report generation.");
    } finally {
      setReportJobActionId("");
    }
  }

  async function retryReportJob(job) {
    if (!job?.id || !["failed", "cancelled"].includes(job.status)) return;
    setReportJobActionId(job.id);
    try {
      const retried = await api(`/api/report-jobs/${job.id}/retry`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      mergeReportJobs([retried]);
      setFocusedReportJobId(retried.id);
      setReportElapsed(0);
    } catch (err) {
      const jobs = await refreshVisibleReportJobs().catch(() => []);
      const activeJob = jobs.find(
        (item) => (
          String(item.report_period_id) === String(job.report_period_id)
          && isActiveReportJob(item)
        ),
      );
      if (activeJob) setFocusedReportJobId(activeJob.id);
      showToast(err.message || "Failed to retry report generation.");
    } finally {
      setReportJobActionId("");
    }
  }

  useEffect(() => {
    loadClients().catch((err) => setError(err.message));
    const onPopState = () => setRoute(routeParts());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!currentClient) return;
    setReportJobs([]);
    setFocusedReportJobId("");
    loadClient(currentClient).catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentClient?.id]);

  useEffect(() => {
    if (!isGlobalReportJobs) return undefined;
    let stopped = false;
    const refresh = () => {
      loadGlobalReportJobs().catch((err) => {
        if (!stopped) setError(err.message);
      });
    };
    setReportJobs([]);
    setFocusedReportJobId("");
    refresh();
    const intervalId = window.setInterval(refresh, 3000);
    return () => {
      stopped = true;
      window.clearInterval(intervalId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isGlobalReportJobs]);

  useEffect(() => {
    if (
      !currentClient
      || !selectedClient
      || String(selectedClient.id) !== String(currentClient.id)
      || isGlobalReportJobs
    ) {
      return undefined;
    }
    let stopped = false;
    const refresh = () => {
      loadClientReportJobs(selectedClient).catch((err) => {
        if (!stopped) setError(err.message);
      });
    };
    refresh();
    const intervalId = window.setInterval(refresh, 5000);
    return () => {
      stopped = true;
      window.clearInterval(intervalId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentClient?.id, selectedClient?.id, isGlobalReportJobs]);

  useEffect(() => {
    if (!currentClient || !selectedClient) return;
    loadPlatformData(selectedClient).catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClient?.id, currentMonth?.slug]);

  useEffect(() => {
    if (!activeReportJobIdsKey) return undefined;
    const jobIds = activeReportJobIdsKey.split(",");
    let stopped = false;
    const poll = async () => {
      const rows = await Promise.all(
        jobIds.map((jobId) => api(`/api/report-jobs/${jobId}`).catch(() => null)),
      );
      if (!stopped) mergeReportJobs(rows);
    };
    const intervalId = window.setInterval(poll, 3000);
    return () => {
      stopped = true;
      window.clearInterval(intervalId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeReportJobIdsKey]);

  useEffect(() => {
    if (!isActiveReportJob(reportJob)) return undefined;
    const startedAt = new Date(
      reportJob.started_at
      || reportJob.queued_at
      || reportJob.created_at
      || Date.now(),
    ).getTime();
    const updateElapsed = () => {
      setReportElapsed(Math.floor((Date.now() - startedAt) / 1000));
    };
    updateElapsed();
    const intervalId = window.setInterval(updateElapsed, 1000);
    return () => window.clearInterval(intervalId);
  }, [
    reportJob?.id,
    reportJob?.status,
    reportJob?.started_at,
    reportJob?.queued_at,
    reportJob?.created_at,
  ]);

  let content = (
    <ClientsPage
      clients={clients}
      industries={industries}
      query={query}
      industry={industry}
      onQueryChange={setQuery}
      onIndustryChange={setIndustry}
      onOpenClient={(id) => {
        const client = clients.find((item) => item.id === id);
        navigate(`/clients/${clientSlug(client)}`);
      }}
      onOpenAddClient={() => setModal("add-client")}
      onEditClient={(client) => runWhenClientUnlocked(
        client,
        () => setEditClient(client),
      )}
      onDeleteClient={(client) => runWhenClientUnlocked(
        client,
        () => setDeleteTarget(client),
      )}
    />
  );

  if (isGlobalReportJobs) {
    content = (
      <ReportJobsPage
        jobs={reportJobs}
        actionJobId={reportJobActionId}
        onNavigate={navigate}
        onCancel={cancelReportJob}
        onRetry={retryReportJob}
        onRefresh={() => {
          loadGlobalReportJobs().catch((err) => {
            showToast(err.message || "Failed to refresh report queue.");
          });
        }}
        onOpenReport={openPresentation}
      />
    );
  }

  if (
    currentClient
    && selectedClient
    && !currentMonth
    && !isClientReportJobs
  ) {
    content = (
      <ClientDetailPage
        client={selectedClient}
        profiles={profiles}
        reportMonths={reportMonths}
        onNavigate={navigate}
        onOpenMonth={(path) => navigate(`/clients/${path}`)}
        onOpenAddReport={() => setModal("add-report-csv")}
        onOpenKpiTargets={() => setModal("add-report-kpi")}
        onDeleteClient={(client) => runWhenClientUnlocked(
          client,
          () => setDeleteTarget(client),
        )}
        onDeleteReportMonth={(month) => runWhenPeriodUnlocked(
          month,
          () => setDeleteReportMonthTarget(month),
        )}
        onGenerateReport={requestSlidesReportGeneration}
        activeReportPeriodIds={activeReportPeriodIds}
        reportJobActionId={reportJobActionId}
        onOpenReportJobs={() => navigate(
          `/clients/${clientSlug(selectedClient)}/report-jobs`,
        )}
      />
    );
  }

  if (currentClient && selectedClient && currentMonth && !currentPlatform) {
    content = (
      <MonthDetailPage
        client={selectedClient}
        month={currentMonth}
        profiles={profiles}
        platformData={platformData}
        onNavigate={navigate}
        onOpenPlatform={(path) => navigate(`/clients/${path}`)}
        onOpenAddReport={() => runWhenPeriodUnlocked(
          currentMonth,
          () => setModal("add-report-csv"),
        )}
        onGenerateReport={requestSlidesReportGeneration}
        isGeneratingReport={
          activeReportPeriodIds.has(String(currentMonth.id))
          || reportJobActionId === `create:${currentMonth.id}`
        }
        onOpenEditor={() => runWhenPeriodUnlocked(
          currentMonth,
          () => navigate(`/clients/${clientSlug(selectedClient)}/${currentMonth.slug}/edit`),
        )}
      />
    );
  }

  if (
    currentClient
    && selectedClient
    && (
      isClientReportJobs
      || (currentMonth && isLegacyPeriodReportJobs)
    )
  ) {
    content = (
      <ReportJobsPage
        client={selectedClient}
        jobs={reportJobs}
        actionJobId={reportJobActionId}
        onNavigate={navigate}
        onCancel={cancelReportJob}
        onRetry={retryReportJob}
        onRefresh={() => {
          loadClientReportJobs(selectedClient).catch((err) => {
            showToast(err.message || "Failed to refresh generation history.");
          });
        }}
        onOpenReport={openPresentation}
      />
    );
  }

  if (currentClient && selectedClient && currentMonth && isReportEditor) {
    content = (
      <ReportDataEditorPage
        client={selectedClient}
        month={currentMonth}
        onNavigate={navigate}
        onSaved={async () => {
          await loadClient(selectedClient);
          await loadPlatformData(selectedClient);
          showToast("Report data updated.");
        }}
        onReportLocked={(err) => handleReportDataLock(err, {
          client: selectedClient,
          month: currentMonth,
        })}
      />
    );
  }

  if (
    currentClient
    && selectedClient
    && currentMonth
    && currentPlatform
    && !isReportEditor
    && !isLegacyPeriodReportJobs
  ) {
    content = (
      <PlatformDetailPage
        client={selectedClient}
        month={currentMonth}
        platform={currentPlatform}
        data={platformData[currentPlatform]}
        onNavigate={navigate}
        onOpenReportKpi={() => runWhenPeriodUnlocked(
          currentMonth,
          () => setModal("add-report-kpi"),
        )}
        onEditKpi={(row) => runWhenPeriodUnlocked(
          currentMonth,
          () => setEditKpi(row),
        )}
        onOpenEditor={() => runWhenPeriodUnlocked(
          currentMonth,
          () => navigate(`/clients/${clientSlug(selectedClient)}/${currentMonth.slug}/edit`),
        )}
      />
    );
  }

  return (
    <>
      <Header
        activeSection={isGlobalReportJobs ? "report-jobs" : "clients"}
        onNavigate={navigate}
      />
      <main className="page-shell">
        {error ? <div className="empty">{error}</div> : content}
      </main>
      {modal === "add-client" && (
        <AddClientModal
          industries={industries}
          onClose={() => setModal(null)}
          onAddClient={async (client) => {
            const savedClient = await api("/api/clients", {
              method: "POST",
              body: JSON.stringify(client),
            });
            await loadClients();
            setModal(null);
            showToast("Client saved.");
            navigate(`/clients/${clientSlug(savedClient)}`);
          }}
        />
      )}
      {editClient && (
        <AddClientModal
          client={editClient}
          industries={industries}
          onClose={() => setEditClient(null)}
          onReportLocked={(err) => handleReportDataLock(err, {
            client: editClient,
          })}
          onAddClient={async (client) => {
            const savedClient = await api(`/api/clients/${editClient.id}`, {
              method: "POST",
              body: JSON.stringify(client),
            });
            await loadClients();
            if (selectedClient?.id === editClient.id) {
              await loadClient(savedClient);
            }
            setEditClient(null);
            showToast("Client updated.");
            if (currentClient?.id === editClient.id && clientSlug(savedClient) !== currentClientSlug) {
              navigate(`/clients/${clientSlug(savedClient)}`, true);
            }
          }}
        />
      )}
      {(modal === "add-report-csv" || modal === "add-report-kpi") && (
        <AddReportModal
          client={selectedClient}
          month={currentMonth}
          reportMonths={reportMonths}
          platformData={platformData}
          activePlatform={modal === "add-report-kpi" ? currentPlatform : null}
          initialTab={modal === "add-report-kpi" ? "kpi" : "csv"}
          onSaveKpiTargets={saveKpiTargets}
          onReportLocked={(err) => handleReportDataLock(err, {
            client: selectedClient,
            month: currentMonth,
          })}
          onImported={async () => {
            await loadClients();
            await loadClient(selectedClient);
            await loadPlatformData(selectedClient);
            showToast("CSV data imported. Overview refreshed.");
          }}
          onClose={() => setModal(null)}
        />
      )}
      {editKpi && (
        <EditKpiModal
          row={editKpi}
          onClose={() => setEditKpi(null)}
          onSave={saveKpi}
          onReportLocked={(err) => handleReportDataLock(err, {
            client: selectedClient,
            month: currentMonth,
          })}
        />
      )}
      {deleteTarget && (
        <DeleteClientModal
          client={deleteTarget}
          isDeleting={isDeletingClient}
          onClose={() => setDeleteTarget(null)}
          onConfirm={() => {
            deleteClient(deleteTarget).catch((err) => {
              setIsDeletingClient(false);
              setError(err.message);
            });
          }}
        />
      )}
      {deleteReportMonthTarget && (
        <DeleteReportMonthModal
          month={deleteReportMonthTarget}
          isDeleting={isDeletingReportMonth}
          onClose={() => setDeleteReportMonthTarget(null)}
          onConfirm={() => {
            deleteReportMonth(deleteReportMonthTarget).catch((err) => {
              setIsDeletingReportMonth(false);
              setError(err.message);
            });
          }}
        />
      )}
      {generateReportTarget && selectedClient && (
        <GenerateReportModal
          client={selectedClient}
          month={generateReportTarget}
          platforms={platformFlags(selectedClient)}
          isSubmitting={
            reportJobActionId === `create:${generateReportTarget.id}`
          }
          onClose={() => setGenerateReportTarget(null)}
          onConfirm={() => {
            confirmSlidesReportGeneration().catch((err) => {
              setReportJobActionId("");
              showToast(err.message || "Failed to add report to queue.");
            });
          }}
        />
      )}
      {reportDataLock && (
        <ReportDataLockedModal
          clientName={reportDataLock.clientName}
          periodLabel={reportDataLock.periodLabel}
          job={reportDataLock.job}
          onClose={() => setReportDataLock(null)}
          onOpenHistory={() => {
            const lockClient = clients.find(
              (client) => (
                String(client.id) === String(reportDataLock.clientId)
              ),
            );
            setReportDataLock(null);
            setModal(null);
            setEditClient(null);
            setEditKpi(null);
            setDeleteTarget(null);
            setDeleteReportMonthTarget(null);
            navigate(
              lockClient
                ? `/clients/${clientSlug(lockClient)}/report-jobs`
                : "/report-jobs",
            );
          }}
        />
      )}
      {reportJob && (
        <div className={`report-toast ${reportJob.status}`}>
          <div className="report-toast-main">
            <div>
              <p className="report-toast-title">
                {reportJobStatusLabel(reportJob.status)}
              </p>
              <p className="report-toast-detail">
                {reportJob.client_name_snapshot} - {reportJob.period_label_snapshot}
              </p>
            </div>
            {!isActiveReportJob(reportJob) && (
              <button
                type="button"
                className="report-toast-close"
                aria-label="Close report notification"
                onClick={() => {
                  const nextActive = reportJobs.find(
                    (job) => job.id !== reportJob.id && isActiveReportJob(job),
                  );
                  setFocusedReportJobId(nextActive?.id || "");
                }}
              >
                x
              </button>
            )}
          </div>
          {isActiveReportJob(reportJob) && (
            <p className="report-toast-meta">
              {reportJobStageLabel(reportJob.current_stage)}
              {" - "}
              {formatElapsed(reportElapsed)}
            </p>
          )}
          {reportJob.error_message && (
            <p className="report-toast-error">{reportJob.error_message}</p>
          )}
          <div className="report-toast-actions">
            {reportJob.presentation_url && (
              <button
                type="button"
                className="report-toast-open secondary"
                onClick={() => openPresentation(reportJob.presentation_url)}
              >
                Open Slides
              </button>
            )}
            {["failed", "cancelled"].includes(reportJob.status) && (
              <button
                type="button"
                className="report-toast-open"
                disabled={reportJobActionId === reportJob.id}
                onClick={() => retryReportJob(reportJob)}
              >
                {reportJobActionId === reportJob.id ? "Retrying..." : "Retry"}
              </button>
            )}
            {["queued", "running", "retrying"].includes(reportJob.status) && (
              <button
                type="button"
                className="report-toast-cancel"
                disabled={reportJobActionId === reportJob.id}
                onClick={() => cancelReportJob(reportJob)}
              >
                {reportJobActionId === reportJob.id
                  ? "Cancelling..."
                  : "Cancel"}
              </button>
            )}
            <button
              type="button"
              className="report-toast-open"
              onClick={() => {
                const targetClient = clients.find(
                  (client) => String(client.id) === String(reportJob.client_id),
                );
                if (targetClient) {
                  navigate(
                    `/clients/${clientSlug(targetClient)}/report-jobs`,
                  );
                } else {
                  navigate("/report-jobs");
                }
              }}
            >
              View history
            </button>
          </div>
        </div>
      )}
      {toast && <div className="toast active">{toast}</div>}
    </>
  );
}
