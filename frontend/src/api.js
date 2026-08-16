// Client API centralizzato: una sola fonte per fetch + gestione errori.
const JSON_HEADERS = { "Content-Type": "application/json" };

async function req(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { const j = await res.json(); detail = j.detail || detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  results: (hours) => req(`/api/results${hours ? `?hours=${hours}` : ""}`),
  stats: (hours) => req(`/api/stats?hours=${hours}`),
  hourly: (hours) => req(`/api/hourly?hours=${hours}`),
  outages: (hours) => req(`/api/outages?hours=${hours}`),
  runNow: () => req(`/api/run`, { method: "POST" }),
  getSettings: () => req(`/api/settings`),
  saveSettings: (body) => req(`/api/settings`, { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify(body) }),
  servers: () => req(`/api/servers`),
  testNotify: (channel) => req(`/api/test-notify?channel=${channel}`, { method: "POST" }),
};

export const COL = {
  bg: "#0a0e17", panel: "#111827", edge: "#1e2a3d", grid: "#1a2436",
  signal: "#3ddc84", upload: "#4aa8ff", amber: "#ffb03a", bad: "#ff5a5a",
  text: "#e6edf5", dim: "#6b7a90",
  mono: "'JetBrains Mono','SF Mono','Fira Code',ui-monospace,monospace",
};

// formattazione timestamp coerente con il mock
export function fmtAxis(iso, hours) {
  const d = new Date(iso);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  if (hours <= 24) return `${hh}:${mm}`;
  return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")} ${hh}`;
}
export function fmtFull(iso) {
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")} · ` +
         `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
