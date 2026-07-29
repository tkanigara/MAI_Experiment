export async function api(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const response = await fetch(path, {
    headers: isFormData ? {} : { "Content-Type": "application/json" },
    ...options,
  });
  const contentType = response.headers.get("Content-Type") || "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : { error: await response.text() };
  if (!response.ok) {
    const message = String(data.error || "Request failed");
    throw new Error(message.startsWith("<!DOCTYPE") ? "API endpoint is not available. Restart the dashboard backend." : message);
  }
  return data;
}
