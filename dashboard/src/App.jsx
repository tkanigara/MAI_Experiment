import { useEffect, useMemo, useState } from "react";
import AddClientModal from "./components/AddClientModal";
import AddReportModal from "./components/AddReportModal";
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
    const entries = await Promise.all(
      platformFlags(client).map(async (platform) => {
        try {
          return [platform, await api(`/api/clients/${client.id}/platforms/${platform}/overview`)];
        } catch {
          return [platform, { platform, report: null, metrics: [], kpi_results: [], top_posts: [], low_posts: [] }];
        }
      }),
    );
    setPlatformData(Object.fromEntries(entries));
  }

  async function saveKpi(payload) {
    if (!selectedClient || !currentPlatform) return;
    await api("/api/kpi-targets", {
      method: "POST",
      body: JSON.stringify({
        client_id: selectedClient.id,
        platform: currentPlatform,
        metric_name: payload.metric_name,
        period_year: 2026,
        target_month: payload.target_month,
        unit: payload.unit,
      }),
    });
    setEditKpi(null);
    await loadPlatformData(selectedClient);
    showToast("KPI target updated.");
  }

  async function deleteClient(client) {
    if (!client?.id) return;
    const confirmed = window.confirm(
      `Delete ${client.client_name}? This will remove its profiles, reports, competitors, KPI data, and imported raw rows.`,
    );
    if (!confirmed) return;
    await api(`/api/clients/${client.id}`, { method: "DELETE" });
    await loadClients();
    if (selectedClient?.id === client.id || currentClient?.id === client.id) {
      setSelectedClient(null);
      setProfiles([]);
      setReportMonths([]);
      setPlatformData({});
      navigate("/clients");
    }
    showToast("Client deleted.");
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
    if (!selectedClient || !currentMonth) return;
    loadPlatformData(selectedClient).catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClient?.id, currentMonth?.slug]);

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
      onDeleteClient={(client) => deleteClient(client).catch((err) => setError(err.message))}
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
        onDeleteClient={(client) => deleteClient(client).catch((err) => setError(err.message))}
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
      {(modal === "add-report-csv" || modal === "add-report-kpi") && (
        <AddReportModal
          client={selectedClient}
          month={currentMonth}
          reportMonths={reportMonths}
          platformData={platformData}
          initialTab={modal === "add-report-kpi" ? "kpi" : "csv"}
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
      {toast && <div className="toast active">{toast}</div>}
    </>
  );
}
