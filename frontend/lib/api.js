// Thin fetch client for the FastAPI backend.
// In production the UI is served from the same origin as the API (BASE = ""),
// so all calls are same-origin. In dev, set NEXT_PUBLIC_API_BASE.

const BASE = process.env.NEXT_PUBLIC_API_BASE || "";

async function request(path, { method = "GET", body } = {}) {
  const res = await fetch(BASE + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  base: BASE,
  catalogs: () => request("/api/catalogs"),
  schemas: (catalog) => request(`/api/schemas?catalog=${encodeURIComponent(catalog)}`),
  tables: (catalog, schema) =>
    request(
      `/api/tables?catalog=${encodeURIComponent(catalog)}&schema=${encodeURIComponent(schema)}`
    ),
  load: (payload) => request("/api/load", { method: "POST", body: payload }),
  profile: (payload) => request("/api/profile", { method: "POST", body: payload }),
  column: (payload) => request("/api/column", { method: "POST", body: payload }),
  save: (payload) => request("/api/save", { method: "POST", body: payload }),
  // returns a download URL for the Excel export (POST), handled via fetch+blob
  exportExcel: async (payload) => {
    const res = await fetch(BASE + "/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Export failed");
    return res.blob();
  },
};

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
