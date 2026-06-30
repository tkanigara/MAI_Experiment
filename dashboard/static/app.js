const state = {
  clients: [],
  selectedClient: null,
  selectedPlatforms: [],
  selectedPlatform: null,
  routeReady: false,
};

const $ = (selector) => document.querySelector(selector);
const KPI_METRICS = {
  instagram: [
    { value: "followers", label: "Followers", unit: "count" },
    { value: "engagement", label: "Engagement", unit: "count" },
    { value: "reach", label: "Reach", unit: "count" },
  ],
  facebook: [
    { value: "followers", label: "Followers", unit: "count" },
    { value: "engagement", label: "Engagement", unit: "count" },
    { value: "reach", label: "Reach", unit: "count" },
  ],
  tiktok: [
    { value: "followers", label: "Followers", unit: "count" },
    { value: "engagement", label: "Engagement", unit: "count" },
    { value: "views", label: "Views", unit: "views" },
  ],
  youtube: [
    { value: "subscribers", label: "Subscribers", unit: "count" },
    { value: "engagement", label: "Engagement", unit: "count" },
    { value: "views", label: "Views", unit: "views" },
  ],
};

function setStatus(text) {
  $("#connection-status").textContent = text;
}

function showView(name) {
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === name);
  });
  $(`#${name}-view`).classList.add("active");
  $("#page-title").textContent = name === "kpi" ? "KPI Input" : "Clients";
}

function clientSlug(client) {
  return client.client_code || client.id;
}

function findClient(slug) {
  return state.clients.find((client) => client.client_code === slug || client.id === slug);
}

function routeTo(path, replace = false) {
  if (window.location.pathname === path) return;
  const method = replace ? "replaceState" : "pushState";
  window.history[method]({}, "", path);
}

async function handleRoute(replace = false) {
  const parts = window.location.pathname.split("/").filter(Boolean);
  if (!parts.length) {
    routeTo("/clients", true);
    showView("clients");
    return;
  }
  if (parts[0] === "kpi") {
    showView("kpi");
    return;
  }
  if (parts[0] !== "clients") {
    routeTo("/clients", true);
    showView("clients");
    return;
  }
  if (!parts[1]) {
    showView("clients");
    return;
  }
  const client = findClient(parts[1]);
  if (!client) {
    routeTo("/clients", true);
    showView("clients");
    return;
  }
  await openClient(client.id, { updateRoute: false });
  if (parts[2]) {
    await openOverview(parts[2], { updateRoute: false });
  }
  if (replace) {
    const route = parts[2]
      ? `/clients/${clientSlug(client)}/${parts[2]}`
      : `/clients/${clientSlug(client)}`;
    routeTo(route, true);
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

function formatNumber(value, suffix = "") {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (!Number.isFinite(number)) return `${value}${suffix}`;
  const formatted = number.toLocaleString("en-US", {
    maximumFractionDigits: Math.abs(number) < 10 ? 2 : 0,
  });
  return `${formatted}${suffix}`;
}

function platformFlags(client) {
  return ["instagram", "facebook", "tiktok", "youtube"].filter(
    (platform) => client[`has_${platform}`],
  );
}

function renderClients() {
  const grid = $("#client-grid");
  if (!state.clients.length) {
    grid.innerHTML = `<div class="empty">Belum ada client di database.</div>`;
    return;
  }
  grid.innerHTML = state.clients
    .map((client) => {
      const platforms = platformFlags(client);
      return `
        <article class="client-card" data-client-id="${client.id}">
          <div class="card-title">${client.client_name}</div>
          <div class="card-meta">${client.industry || "No industry"} · ${client.connected_profiles || 0} profile</div>
          <div class="pill-row">
            ${platforms.map((platform) => `<span class="pill">${platform}</span>`).join("")}
          </div>
        </article>
      `;
    })
    .join("");
  document.querySelectorAll(".client-card").forEach((card) => {
    card.addEventListener("click", () => openClient(card.dataset.clientId));
  });
}

function renderKpiClientOptions() {
  $("#kpi-client").innerHTML = state.clients
    .map((client) => `<option value="${client.id}">${client.client_name}</option>`)
    .join("");
}

async function loadClients() {
  state.clients = await api("/api/clients");
  renderClients();
  renderKpiClientOptions();
  setStatus("Connected");
  state.routeReady = true;
  await handleRoute(true);
}

async function openClient(clientId, options = {}) {
  const payload = await api(`/api/clients/${clientId}/platforms`);
  state.selectedClient = payload.client;
  state.selectedPlatforms = payload.profiles;
  $("#client-name").textContent = payload.client.client_name;
  $("#client-detail").textContent = `${payload.client.industry || "Client"} · ${payload.profiles.length} connected profile`;
  $("#platform-row").innerHTML = payload.profiles
    .map(
      (profile) => `
        <article class="platform-card" data-platform="${profile.platform}">
          <div class="card-title">${profile.platform}</div>
          <div class="card-meta">${profile.profile_name || profile.source_profile_id}</div>
        </article>
      `,
    )
    .join("");
  document.querySelectorAll(".platform-card").forEach((card) => {
    card.addEventListener("click", () => openOverview(card.dataset.platform));
  });
  showView("platform");
  $("#page-title").textContent = "Platforms";
  if (options.updateRoute !== false) {
    routeTo(`/clients/${clientSlug(payload.client)}`);
  }
}

async function openOverview(platform, options = {}) {
  state.selectedPlatform = platform;
  const clientId = state.selectedClient.id;
  const payload = await api(`/api/clients/${clientId}/platforms/${platform}/overview`);
  const report = payload.report;
  $("#overview-heading").textContent = `${state.selectedClient.client_name} · ${platform}`;
  $("#overview-period").textContent = report
    ? `${report.period_label || "Latest period"} · ${report.period_start} to ${report.period_end}`
    : "No report data";
  $("#profile-link").hidden = !report?.profile_url;
  $("#profile-link").href = report?.profile_url || "#";
  renderMetrics(payload.metrics);
  renderKpiResults(payload.kpi_results);
  renderPosts(payload.top_posts);
  showView("overview");
  $("#page-title").textContent = "Overview";
  if (options.updateRoute !== false) {
    routeTo(`/clients/${clientSlug(state.selectedClient)}/${platform}`);
  }
}

function renderMetrics(metrics) {
  $("#metric-grid").innerHTML = metrics.length
    ? metrics
        .map(
          (item) => `
            <article class="metric-card">
              <div class="metric-label">${item.label}</div>
              <div class="metric-value">${formatNumber(item.value, item.suffix || "")}</div>
            </article>
          `,
        )
        .join("")
    : `<div class="empty">Belum ada overview report untuk platform ini.</div>`;
}

function renderKpiResults(rows) {
  $("#kpi-results-body").innerHTML = rows.length
    ? rows
        .map(
          (row) => `
            <tr>
              <td>${row.metric_name}</td>
              <td>${formatNumber(row.actual_month, row.unit === "%" ? "%" : "")}</td>
              <td>${formatNumber(row.target_month, row.unit === "%" ? "%" : "")}</td>
              <td>${formatNumber(row.achievement_month, "%")}</td>
            </tr>
          `,
        )
        .join("")
    : `<tr><td colspan="4">Belum ada KPI result untuk periode ini.</td></tr>`;
}

function captionText(post) {
  const text = post.caption || post.post_id || "Untitled content";
  return text.length > 96 ? `${text.slice(0, 93)}...` : text;
}

function renderPosts(posts) {
  $("#top-posts").innerHTML = posts.length
    ? posts
        .slice(0, 5)
        .map(
          (post, index) => `
            <article class="post-item">
              <div class="rank">${post.rank || index + 1}</div>
              <div class="post-caption">${captionText(post)}</div>
              <div class="post-score">${formatNumber(post.total_engagement)}</div>
            </article>
          `,
        )
        .join("")
    : `<div class="empty">Belum ada top content.</div>`;
}

function updateMetricOptions() {
  const platform = $("#kpi-platform").value;
  const metrics = KPI_METRICS[platform] || [];
  $("#kpi-metric").innerHTML = metrics
    .map((metric) => `<option value="${metric.value}" data-unit="${metric.unit}">${metric.label}</option>`)
    .join("");
  updateMetricUnit();
}

function updateMetricUnit() {
  const selected = $("#kpi-metric").selectedOptions[0];
  $("#kpi-unit").value = selected?.dataset.unit || "count";
}

async function saveKpiTarget(event) {
  event.preventDefault();
  const payload = {
    client_id: $("#kpi-client").value,
    platform: $("#kpi-platform").value,
    metric_name: $("#kpi-metric").value,
    period_year: $("#kpi-year").value,
    target_month: $("#kpi-target-month").value,
    target_year: $("#kpi-target-year").value,
    unit: $("#kpi-unit").value,
    notes: $("#kpi-notes").value,
  };
  await api("/api/kpi-targets", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (state.selectedClient?.id === payload.client_id && state.selectedPlatform === payload.platform) {
    await openOverview(payload.platform);
  }
  $("#toast").textContent = "KPI target saved and overview updated.";
  $("#toast").classList.add("active");
  setTimeout(() => $("#toast").classList.remove("active"), 2600);
  event.target.reset();
  $("#kpi-year").value = new Date().getFullYear();
  updateMetricOptions();
}

function bindEvents() {
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => {
      if (item.dataset.view === "kpi") {
        routeTo("/kpi");
        showView("kpi");
        return;
      }
      routeTo("/clients");
      showView("clients");
    });
  });
  $("#back-to-clients").addEventListener("click", () => {
    routeTo("/clients");
    showView("clients");
  });
  $("#back-to-platforms").addEventListener("click", () => openClient(state.selectedClient.id));
  $("#kpi-form").addEventListener("submit", saveKpiTarget);
  $("#kpi-platform").addEventListener("change", updateMetricOptions);
  $("#kpi-metric").addEventListener("change", updateMetricUnit);
  window.addEventListener("popstate", () => {
    if (state.routeReady) handleRoute();
  });
  $("#kpi-year").value = new Date().getFullYear();
  updateMetricOptions();
}

bindEvents();
loadClients().catch((error) => {
  setStatus("Disconnected");
  $("#client-grid").innerHTML = `<div class="empty">${error.message}</div>`;
});
