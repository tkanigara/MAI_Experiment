import { useEffect, useMemo, useState } from "react";
import AddClientModal from "./components/AddClientModal";
import AddReportModal from "./components/AddReportModal";
import DeleteClientModal from "./components/DeleteClientModal";
import DeleteReportMonthModal from "./components/DeleteReportMonthModal";
import EditKpiModal from "./components/EditKpiModal";
import Header from "./components/Header";
import { api } from "./lib/api";
import { clientSlug, platformFlags } from "./lib/format";
import ClientDetailPage from "./pages/ClientDetailPage";
import ClientsPage from "./pages/ClientsPage";
import MonthDetailPage from "./pages/MonthDetailPage";
import PlatformDetailPage from "./pages/PlatformDetailPage";

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
  const [toast, setToast] = useState("");
  const [editKpi, setEditKpi] = useState(null);
  const [editClient, setEditClient] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeletingClient, setIsDeletingClient] = useState(false);
  const [deleteReportMonthTarget, setDeleteReportMonthTarget] = useState(null);
  const [isDeletingReportMonth, setIsDeletingReportMonth] = useState(false);
  const [generatingReportId, setGeneratingReportId] = useState("");
  const [reportJob, setReportJob] = useState(null);
  const [reportElapsed, setReportElapsed] = useState(0);
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
  const currentMonth = reportMonths.find((month) => month.slug === route[2]);
  const currentPlatform = route[3];

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
  }

  async function deleteClient(client) {
    if (!client?.id) return;
    setIsDeletingClient(true);
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
    setIsDeletingClient(false);
    showToast("Client deleted.");
  }

  async function deleteReportMonth(month) {
    if (!selectedClient?.id || !month?.id) return;
    setIsDeletingReportMonth(true);
    await api(`/api/clients/${selectedClient.id}/report-periods/${month.id}`, { method: "DELETE" });
    await loadClient(selectedClient);
    setPlatformData({});
    setDeleteReportMonthTarget(null);
    setIsDeletingReportMonth(false);
    showToast(`${month.label} report data deleted.`);
  }

  async function generateSlidesReport(month) {
    if (!selectedClient || !month?.id) return;
    if (reportJob?.status === "running") return;
    const startedAt = Date.now();
    const reportLabel = `${selectedClient.client_name} - ${month.period_label || month.label || "Report"}`;
    setReportElapsed(0);
    setReportJob({
      status: "running",
      periodId: month.id,
      label: reportLabel,
      startedAt,
      presentationUrl: "",
      error: "",
    });
    setGeneratingReportId(month.id);
    try {
      const result = await api("/api/reports/slides", {
        method: "POST",
        body: JSON.stringify({
          client_id: selectedClient.id,
          period_id: month.id,
        }),
      });
      setReportJob({
        status: "complete",
        periodId: month.id,
        label: reportLabel,
        startedAt,
        presentationUrl: result.presentation_url || "",
        error: "",
      });
    } catch (err) {
      setError(err.message);
      setReportJob({
        status: "failed",
        periodId: month.id,
        label: reportLabel,
        startedAt,
        presentationUrl: "",
        error: err.message || "Failed to generate report.",
      });
    } finally {
      setGeneratingReportId("");
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
    loadClient(currentClient).catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentClient?.id]);

  useEffect(() => {
    if (!selectedClient) return;
    loadPlatformData(selectedClient).catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClient?.id, currentMonth?.slug]);

  useEffect(() => {
    if (reportJob?.status !== "running") return undefined;
    const updateElapsed = () => {
      setReportElapsed(Math.floor((Date.now() - reportJob.startedAt) / 1000));
    };
    updateElapsed();
    const intervalId = window.setInterval(updateElapsed, 1000);
    return () => window.clearInterval(intervalId);
  }, [reportJob?.status, reportJob?.startedAt]);

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
      onEditClient={setEditClient}
      onDeleteClient={setDeleteTarget}
    />
  );

  if (currentClient && selectedClient && !currentMonth) {
    content = (
      <ClientDetailPage
        client={selectedClient}
        profiles={profiles}
        reportMonths={reportMonths}
        onNavigate={navigate}
        onOpenMonth={(path) => navigate(`/clients/${path}`)}
        onOpenAddReport={() => setModal("add-report-csv")}
        onOpenKpiTargets={() => setModal("add-report-kpi")}
        onDeleteClient={setDeleteTarget}
        onDeleteReportMonth={setDeleteReportMonthTarget}
        onGenerateReport={generateSlidesReport}
        generatingReportId={generatingReportId}
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
        onOpenAddReport={() => setModal("add-report-csv")}
        onGenerateReport={generateSlidesReport}
        isGeneratingReport={generatingReportId === currentMonth.id}
      />
    );
  }

  if (currentClient && selectedClient && currentMonth && currentPlatform) {
    content = (
      <PlatformDetailPage
        client={selectedClient}
        month={currentMonth}
        platform={currentPlatform}
        data={platformData[currentPlatform]}
        onNavigate={navigate}
        onOpenReportKpi={() => setModal("add-report-kpi")}
        onEditKpi={setEditKpi}
      />
    );
  }

  return (
    <>
      <Header />
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
      {reportJob && (
        <div className={`report-toast ${reportJob.status}`}>
          <div className="report-toast-main">
            <div>
              <p className="report-toast-title">
                {reportJob.status === "running"
                  ? "Generating report"
                  : reportJob.status === "complete"
                    ? "Report generated"
                    : "Report failed"}
              </p>
              <p className="report-toast-detail">{reportJob.label}</p>
            </div>
            {reportJob.status === "failed" && (
              <button
                type="button"
                className="report-toast-close"
                aria-label="Close report notification"
                onClick={() => setReportJob(null)}
              >
                x
              </button>
            )}
          </div>
          {reportJob.status === "running" && (
            <p className="report-toast-meta">{formatElapsed(reportElapsed)}</p>
          )}
          {reportJob.status === "complete" && (
            <button
              type="button"
              className="report-toast-open"
              disabled={!reportJob.presentationUrl}
              onClick={() => {
                if (reportJob.presentationUrl) {
                  window.open(reportJob.presentationUrl, "_blank", "noopener,noreferrer");
                }
                setReportJob(null);
              }}
            >
              Buka
            </button>
          )}
          {reportJob.status === "failed" && (
            <p className="report-toast-error">{reportJob.error}</p>
          )}
        </div>
      )}
      {toast && <div className="toast active">{toast}</div>}
    </>
  );
}
