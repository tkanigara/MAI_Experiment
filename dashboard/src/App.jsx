import { useEffect, useMemo, useState } from "react";
import AddClientModal from "./components/AddClientModal";
import AddAdsClientModal from "./components/AddAdsClientModal";
import AddReportModal from "./components/AddReportModal";
import DeleteClientModal from "./components/DeleteClientModal";
import DeleteReportMonthModal from "./components/DeleteReportMonthModal";
import EditKpiModal from "./components/EditKpiModal";
import GenerateReportModal from "./components/GenerateReportModal";
import Header from "./components/Header";
import MetaAdsImportModal from "./components/MetaAdsImportModal";
import ReportDataLockedModal from "./components/ReportDataLockedModal";
import { api } from "./lib/api";
import { adsPeriodSlug, clientSlug, platformFlags } from "./lib/format";
import ClientDetailPage from "./pages/ClientDetailPage";
import AdsClientDetailPage from "./pages/AdsClientDetailPage";
import AdsClientsPage from "./pages/AdsClientsPage";
import AdsPeriodDetailPage from "./pages/AdsPeriodDetailPage";
import AdsPlatformDetailPage from "./pages/AdsPlatformDetailPage";
import ClientsPage from "./pages/ClientsPage";
import MonthDetailPage from "./pages/MonthDetailPage";
import PlatformDetailPage from "./pages/PlatformDetailPage";
import ReportDataEditorPage from "./pages/ReportDataEditorPage";
import ReportJobsPage, {
  isActiveReportJob,
  reportJobStageLabel,
  reportJobStatusLabel,
} from "./pages/ReportJobsPage";
import WorkspaceSelectorPage from "./pages/WorkspaceSelectorPage";

function pathParts() {
  return window.location.pathname.split("/").filter(Boolean);
}

function workspaceFromPath() {
  const first = pathParts()[0];
  if (first === "ads") return "ads";
  if (first === "social" || first === "clients" || first === "report-jobs") return "social";
  return null;
}

function routeParts() {
  const parts = pathParts();
  return ["social", "ads"].includes(parts[0]) ? parts.slice(1) : parts;
}

const REPORT_HISTORY_PAGE_SIZE = 20;

function historyPageFromLocation() {
  const value = Number(new URLSearchParams(window.location.search).get("page"));
  return Number.isInteger(value) && value > 0 ? value : 1;
}

export default function App() {
  const [clients, setClients] = useState([]);
  const [allClients, setAllClients] = useState([]);
  const [productSummary, setProductSummary] = useState({ social_media: 0, meta_ads: 0 });
  const [query, setQuery] = useState("");
  const [industry, setIndustry] = useState("");
  const [route, setRoute] = useState(routeParts());
  const [selectedClient, setSelectedClient] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [reportMonths, setReportMonths] = useState([]);
  const [adsPeriods, setAdsPeriods] = useState([]);
  const [adsPlatformCatalog, setAdsPlatformCatalog] = useState([]);
  const [adsImportPeriod, setAdsImportPeriod] = useState(null);
  const [platformData, setPlatformData] = useState({});
  const [modal, setModal] = useState(null);
  const [generateReportTarget, setGenerateReportTarget] = useState(null);
  const [toast, setToast] = useState("");
  const [editKpi, setEditKpi] = useState(null);
  const [editClient, setEditClient] = useState(null);
  const [editAdsClient, setEditAdsClient] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeletingClient, setIsDeletingClient] = useState(false);
  const [deleteReportMonthTarget, setDeleteReportMonthTarget] = useState(null);
  const [isDeletingReportMonth, setIsDeletingReportMonth] = useState(false);
  const [deleteAdsPeriodTarget, setDeleteAdsPeriodTarget] = useState(null);
  const [isDeletingAdsPeriod, setIsDeletingAdsPeriod] = useState(false);
  const [reportJobs, setReportJobs] = useState([]);
  const [reportJobsPagination, setReportJobsPagination] = useState({
    page: 1,
    page_size: REPORT_HISTORY_PAGE_SIZE,
    total: 0,
    total_pages: 1,
  });
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

  const workspace = workspaceFromPath();
  const isAdsWorkspace = workspace === "ads";
  const isSocialWorkspace = workspace === "social";
  const isGlobalReportJobs = isSocialWorkspace && route[0] === "report-jobs";
  const isClientReportJobs = isSocialWorkspace && route[0] === "clients" && route[2] === "report-jobs";
  const reportHistoryPage = (isGlobalReportJobs || isClientReportJobs)
    ? historyPageFromLocation()
    : 1;
  const currentMonth = isClientReportJobs
    ? null
    : reportMonths.find((month) => month.slug === route[2]);
  const currentPlatform = route[3];
  const currentAdsPeriod = isAdsWorkspace
    ? adsPeriods.find((period) => adsPeriodSlug(period) === route[2] || String(period.id) === route[2])
    : null;
  const currentAdsPlatform = isAdsWorkspace ? route[3] : null;
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
    let targetPath = path;
    if (
      isSocialWorkspace
      && (path === "/clients" || path.startsWith("/clients/") || path === "/report-jobs")
    ) {
      targetPath = `/social${path}`;
    }
    const currentPath = `${window.location.pathname}${window.location.search}`;
    if (currentPath !== targetPath) {
      window.history[replace ? "replaceState" : "pushState"]({}, "", targetPath);
    }
    setRoute(routeParts());
  }

  function navigateReportHistoryPage(page, replace = false) {
    const nextPage = Math.max(1, Number(page) || 1);
    const query = nextPage > 1 ? `?page=${nextPage}` : "";
    navigate(`${window.location.pathname}${query}`, replace);
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

  function replaceReportJobs(jobs, pagination = null) {
    const sortedJobs = sortReportJobs(jobs);
    setReportJobs(sortedJobs);
    if (pagination) setReportJobsPagination(pagination);
    setFocusedReportJobId((current) => {
      if (current && sortedJobs.some((job) => job.id === current)) {
        return current;
      }
      return sortedJobs.find(isActiveReportJob)?.id || "";
    });
    return sortedJobs;
  }

  async function loadClientReportJobs(client, page = reportHistoryPage) {
    if (!client?.id || String(client.id).startsWith("local-")) {
      setReportJobs([]);
      return [];
    }
    const payload = await api(
      `/api/clients/${client.id}/report-jobs?page=${page}&page_size=${REPORT_HISTORY_PAGE_SIZE}`,
    );
    const jobs = Array.isArray(payload) ? payload : (payload.jobs || []);
    const pagination = Array.isArray(payload) ? {
      page: 1,
      page_size: REPORT_HISTORY_PAGE_SIZE,
      total: jobs.filter((job) => !isActiveReportJob(job)).length,
      total_pages: 1,
    } : payload.pagination;
    if (
      isClientReportJobs
      && pagination?.page
      && pagination.page !== page
    ) {
      navigateReportHistoryPage(pagination.page, true);
    }
    return replaceReportJobs(jobs, pagination);
  }

  async function loadGlobalReportJobs(page = reportHistoryPage) {
    const payload = await api(
      `/api/report-jobs?page=${page}&page_size=${REPORT_HISTORY_PAGE_SIZE}`,
    );
    const jobs = Array.isArray(payload) ? payload : (payload.jobs || []);
    const pagination = Array.isArray(payload) ? {
      page: 1,
      page_size: REPORT_HISTORY_PAGE_SIZE,
      total: jobs.filter((job) => !isActiveReportJob(job)).length,
      total_pages: 1,
    } : payload.pagination;
    if (
      isGlobalReportJobs
      && pagination?.page
      && pagination.page !== page
    ) {
      navigateReportHistoryPage(pagination.page, true);
    }
    return replaceReportJobs(jobs, pagination);
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
    if (!workspace) {
      const summary = await api("/api/client-products/summary");
      setProductSummary(summary);
      setClients([]);
      setAllClients([]);
      return;
    }
    if (isAdsWorkspace) {
      const [adsRows, masterRows, summary] = await Promise.all([
        api("/api/clients?product=meta_ads"),
        api("/api/clients"),
        api("/api/client-products/summary"),
      ]);
      setClients(adsRows);
      setAllClients(masterRows);
      setProductSummary(summary);
      return;
    }
    const [socialRows, summary] = await Promise.all([
      api("/api/clients?product=social_media"),
      api("/api/client-products/summary"),
    ]);
    setClients(socialRows);
    setAllClients(socialRows);
    setProductSummary(summary);
  }

  async function loadAdsClient(client) {
    if (!client?.id) return;
    const payload = await api(`/api/ads/clients/${client.id}/periods`);
    setSelectedClient(payload.client);
    setAdsPeriods(payload.periods || []);
    setAdsPlatformCatalog(payload.platforms || []);
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
      const sharedWithOtherWorkspace = isAdsWorkspace
        ? (client.products || []).includes("social_media")
        : (client.products || []).includes("meta_ads");
      if (sharedWithOtherWorkspace) {
        const product = isAdsWorkspace ? "meta_ads" : "social_media";
        await api(`/api/clients/${client.id}/products/${product}`, { method: "DELETE" });
      } else {
        await api(`/api/clients/${client.id}`, { method: "DELETE" });
      }
      await loadClients();
      if (selectedClient?.id === client.id || currentClient?.id === client.id) {
        setSelectedClient(null);
        setProfiles([]);
        setReportMonths([]);
        setPlatformData({});
        navigate(isAdsWorkspace ? "/ads/clients" : "/clients");
      }
      setDeleteTarget(null);
      showToast(sharedWithOtherWorkspace
        ? `Client removed from ${isAdsWorkspace ? "Ads" : "Social Media"}.`
        : "Client deleted.");
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

  async function deleteAdsPeriod(period) {
    if (!selectedClient?.id || !period?.id) return;
    setIsDeletingAdsPeriod(true);
    try {
      await api(`/api/ads/clients/${selectedClient.id}/periods/${period.id}`, { method: "DELETE" });
      await loadAdsClient(selectedClient);
      if (currentAdsPeriod?.id === period.id) navigate(`/ads/clients/${clientSlug(selectedClient)}`);
      setDeleteAdsPeriodTarget(null);
      showToast(`${period.period_label} Ads report data deleted.`);
    } finally {
      setIsDeletingAdsPeriod(false);
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

  async function updateReportMonth(month, monthSlug) {
    if (!selectedClient?.id || !month?.id) return false;
    try {
      const updated = await api(
        `/api/clients/${selectedClient.id}/report-periods/${month.id}`,
        {
          method: "PUT",
          body: JSON.stringify({ month_slug: monthSlug }),
        },
      );
      await loadClient(selectedClient);
      setPlatformData({});
      if (
        currentClient?.id === selectedClient.id
        && route[2] === month.slug
      ) {
        const suffix = route.slice(3).join("/");
        navigate(
          `/clients/${clientSlug(selectedClient)}/${updated.slug}${suffix ? `/${suffix}` : ""}`,
          true,
        );
      }
      showToast(`${month.label} changed to ${updated.label}.`);
      return true;
    } catch (err) {
      if (handleReportDataLock(err, {
        client: selectedClient,
        month,
      })) {
        return false;
      }
      throw err;
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
    const onPopState = () => setRoute(routeParts());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    setError("");
    setSelectedClient(null);
    setProfiles([]);
    setReportMonths([]);
    setAdsPeriods([]);
    setAdsPlatformCatalog([]);
    loadClients().catch((err) => setError(err.message));
    const first = pathParts()[0];
    if (["clients", "report-jobs"].includes(first)) {
      navigate(`/social${window.location.pathname}${window.location.search}`, true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace]);

  useEffect(() => {
    if (!currentClient) return;
    setReportJobs([]);
    setFocusedReportJobId("");
    if (isAdsWorkspace) {
      loadAdsClient(currentClient).catch((err) => setError(err.message));
    } else if (isSocialWorkspace) {
      loadClient(currentClient).catch((err) => setError(err.message));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentClient?.id, workspace]);

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
  }, [isGlobalReportJobs, reportHistoryPage]);

  useEffect(() => {
    if (
      !isSocialWorkspace
      ||
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
  }, [
    currentClient?.id,
    selectedClient?.id,
    isGlobalReportJobs,
    reportHistoryPage,
  ]);

  useEffect(() => {
    if (!isSocialWorkspace || !currentClient || !selectedClient) return;
    loadPlatformData(selectedClient).catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClient?.id, currentMonth?.slug, workspace]);

  useEffect(() => {
    if (!isSocialWorkspace || !activeReportJobIdsKey) return undefined;
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
    <WorkspaceSelectorPage counts={productSummary} onNavigate={navigate} />
  );

  if (isSocialWorkspace) {
    content = (
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
  }

  if (isAdsWorkspace) {
    content = (
      <AdsClientsPage
        clients={clients}
        industries={industries}
        query={query}
        industry={industry}
        onQueryChange={setQuery}
        onIndustryChange={setIndustry}
        onOpenClient={(id) => {
          const client = clients.find((item) => item.id === id);
          navigate(`/ads/clients/${clientSlug(client)}`);
        }}
        onOpenAddClient={() => setModal("add-ads-client")}
        onEditClient={setEditAdsClient}
        onDeleteClient={setDeleteTarget}
      />
    );
    if (currentClient && selectedClient && !currentAdsPeriod) {
      content = (
        <AdsClientDetailPage
          client={selectedClient}
          periods={adsPeriods}
          onNavigate={navigate}
          onOpenPeriod={(periodSlug) => navigate(`/ads/clients/${clientSlug(selectedClient)}/${periodSlug}`)}
          onEditClient={setEditAdsClient}
          onDeleteClient={setDeleteTarget}
          onDeletePeriod={setDeleteAdsPeriodTarget}
          onUpload={(period) => {
            setAdsImportPeriod(period);
            setModal("add-ads-import");
          }}
        />
      );
    }
    if (currentClient && selectedClient && currentAdsPeriod && !currentAdsPlatform) {
      content = (
        <AdsPeriodDetailPage
          client={selectedClient}
          period={currentAdsPeriod}
          platformCatalog={adsPlatformCatalog}
          onNavigate={navigate}
          onOpenPlatform={(path) => navigate(`/ads/clients/${path}`)}
          onUpdate={(period) => { setAdsImportPeriod(period); setModal("add-ads-import"); }}
        />
      );
    }
    if (currentClient && selectedClient && currentAdsPeriod && currentAdsPlatform) {
      content = (
        <AdsPlatformDetailPage
          client={selectedClient}
          period={currentAdsPeriod}
          platform={currentAdsPlatform}
          onNavigate={navigate}
          onUpdate={(period) => { setAdsImportPeriod(period); setModal("add-ads-import"); }}
        />
      );
    }
  }

  if (isSocialWorkspace && isGlobalReportJobs) {
    content = (
      <ReportJobsPage
        jobs={reportJobs}
        pagination={reportJobsPagination}
        actionJobId={reportJobActionId}
        onNavigate={navigate}
        onCancel={cancelReportJob}
        onRetry={retryReportJob}
        onRefresh={() => {
          loadGlobalReportJobs(reportHistoryPage).catch((err) => {
            showToast(err.message || "Failed to refresh report queue.");
          });
        }}
        onPageChange={navigateReportHistoryPage}
        onOpenReport={openPresentation}
      />
    );
  }

  if (
    isSocialWorkspace
    &&
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

  if (isSocialWorkspace && currentClient && selectedClient && currentMonth && !currentPlatform) {
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
    isSocialWorkspace
    &&
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
        pagination={reportJobsPagination}
        actionJobId={reportJobActionId}
        onNavigate={navigate}
        onCancel={cancelReportJob}
        onRetry={retryReportJob}
        onRefresh={() => {
          loadClientReportJobs(selectedClient, reportHistoryPage).catch((err) => {
            showToast(err.message || "Failed to refresh generation history.");
          });
        }}
        onPageChange={navigateReportHistoryPage}
        onOpenReport={openPresentation}
      />
    );
  }

  if (isSocialWorkspace && currentClient && selectedClient && currentMonth && isReportEditor) {
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
    isSocialWorkspace
    &&
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
        workspace={workspace}
        onNavigate={navigate}
      />
      <main className="page-shell">
        {error ? <div className="empty">{error}</div> : content}
      </main>
      {isSocialWorkspace && modal === "add-client" && (
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
          onUpdateMonth={updateReportMonth}
          onSaveKpiTargets={saveKpiTargets}
          onReportLocked={(err) => handleReportDataLock(err, {
            client: selectedClient,
            month: currentMonth,
          })}
          onImported={async (data) => {
            const previousMonth = currentMonth;
            await loadClients();
            await loadClient(selectedClient);
            await loadPlatformData(selectedClient);
            if (
              previousMonth?.id
              && String(data?.period?.id) === String(previousMonth.id)
              && data?.period?.slug
              && data.period.slug !== previousMonth.slug
            ) {
              const suffix = route.slice(3).join("/");
              navigate(
                `/clients/${clientSlug(selectedClient)}/${data.period.slug}${suffix ? `/${suffix}` : ""}`,
                true,
              );
            }
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
          workspace={workspace}
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
      {isAdsWorkspace && modal === "add-ads-client" && (
        <AddAdsClientModal
          clients={allClients.filter((client) => !(client.products || []).includes("meta_ads"))}
          industries={[...new Set(allClients.map((client) => client.industry).filter(Boolean))]}
          onClose={() => setModal(null)}
          onSave={async (payload) => {
            let savedClient;
            if (payload.existing_client_id) {
              savedClient = await api(
                `/api/clients/${payload.existing_client_id}/products/meta_ads`,
                { method: "POST", body: JSON.stringify({ ads_platforms: payload.ads_platforms }) },
              );
            } else {
              savedClient = await api("/api/clients", {
                method: "POST",
                body: JSON.stringify({ ...payload, product: "meta_ads" }),
              });
            }
            await loadClients();
            setModal(null);
            showToast("Ads client enabled.");
            navigate(`/ads/clients/${clientSlug(savedClient)}`);
          }}
        />
      )}
      {isAdsWorkspace && editAdsClient && (
        <AddAdsClientModal
          client={editAdsClient}
          clients={[]}
          industries={industries}
          onClose={() => setEditAdsClient(null)}
          onSave={async (payload) => {
            const savedClient = await api(
              `/api/clients/${editAdsClient.id}/products/meta_ads`,
              { method: "POST", body: JSON.stringify({ ads_platforms: payload.ads_platforms }) },
            );
            await loadClients();
            await loadAdsClient({ ...editAdsClient, ...savedClient });
            setEditAdsClient(null);
            showToast("Ads client updated.");
          }}
        />
      )}
      {isAdsWorkspace && modal === "add-ads-import" && selectedClient && (
        <MetaAdsImportModal
          client={selectedClient}
          period={adsImportPeriod}
          onClose={() => {
            setModal(null);
            setAdsImportPeriod(null);
          }}
          onImported={async () => {
            await loadClients();
            await loadAdsClient(selectedClient);
            setModal(null);
            setAdsImportPeriod(null);
            showToast("Ads report data imported.");
          }}
        />
      )}
      {deleteAdsPeriodTarget && (
        <DeleteReportMonthModal
          month={{ ...deleteAdsPeriodTarget, label: deleteAdsPeriodTarget.period_label }}
          isDeleting={isDeletingAdsPeriod}
          onClose={() => setDeleteAdsPeriodTarget(null)}
          onConfirm={() => deleteAdsPeriod(deleteAdsPeriodTarget).catch((err) => { setIsDeletingAdsPeriod(false); setError(err.message); })}
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
