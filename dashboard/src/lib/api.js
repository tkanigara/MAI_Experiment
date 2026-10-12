function cookieValue(name) {
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

function loginPath() {
  const current = `${window.location.pathname}${window.location.search}`;
  const next = current.startsWith("/login") ? "/" : current;
  return `/login?next=${encodeURIComponent(next)}`;
}

export async function api(path, options = {}) {
  const { skipAuthRedirect = false, ...fetchOptions } = options;
  const isFormData = fetchOptions.body instanceof FormData;
  const method = String(fetchOptions.method || "GET").toUpperCase();
  const headers = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(fetchOptions.headers || {}),
  };
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrfToken = cookieValue("mai_dashboard_csrf");
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  }
  const response = await fetch(path, {
    ...fetchOptions,
    headers,
    credentials: "same-origin",
  });
  const contentType = response.headers.get("Content-Type") || "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : { error: await response.text() };
  if (!response.ok) {
    if (response.status === 401 && !skipAuthRedirect) {
      window.location.assign(loginPath());
    }
    const message = String(data.error || "Request failed");
    const error = new Error(
      message.startsWith("<!DOCTYPE")
        ? "API endpoint is not available. Restart the dashboard backend."
        : message,
    );
    error.status = response.status;
    error.code = data.code || "";
    error.job = data.job || null;
    throw error;
  }
  return data;
}
