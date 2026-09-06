const BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const KEY = import.meta.env.VITE_API_KEY || "";

export const ALL_MODULES = ["form", "router", "assets", "reach"];

export const MODULE_LABELS = {
  form: "Forms",
  router: "Navigation & routes",
  assets: "Assets",
  reach: "DNS & TLS",
};

export const GRADE_LETTER = {
  verified_healthy: "A", minor_issues: "B", needs_attention: "C", critical: "F",
};

export const GRADE_CHIP = {
  verified_healthy: "bg-emerald-100 text-emerald-700",
  minor_issues: "bg-emerald-100 text-emerald-700",
  needs_attention: "bg-amber-100 text-amber-700",
  critical: "bg-red-100 text-red-700",
};

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", "X-API-Key": KEY, ...(options.headers || {}) },
  });
  const text = await res.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!res.ok) {
    // SRS 8.3 envelope: { error: { code, message, audit_id, retryable } }
    const e = body?.error;
    const err = new Error(e?.message || `Request failed (${res.status})`);
    err.code = e?.code || "INTERNAL_ERROR";
    err.retryable = Boolean(e?.retryable);
    err.status = res.status;
    throw err;
  }
  return body;
}

export const api = {
  base: BASE,
  health: () => request("/api/v1/health"),
  startAudit: (domain_url, modules = ALL_MODULES, max_pages = 1, auth = null) =>
    request("/api/v1/audits/start", {
      method: "POST",
      body: JSON.stringify({
        domain_url, modules, max_pages, i_own_this_site: true,
        ...(auth ? { auth } : {}),
      }),
    }),
  retryAudit: (id) => request(`/api/v1/audits/${id}/retry`, { method: "POST" }),
  getStatus: (id) => request(`/api/v1/audits/${id}/status`),
  getReport: (id) => request(`/api/v1/audits/${id}/report`),
  compare: (id, baseline) =>
    request(
      `/api/v1/audits/${id}/compare` + (baseline ? `?baseline=${baseline}` : ""),
    ),
  listAudits: () => request("/api/v1/audits?limit=25"),
  quota: () => request("/api/v1/quota"),
  share: (id) => request(`/api/v1/audits/${id}/share`, { method: "POST" }),
  publicReport: (token, mode = "client") =>
    request(`/api/v1/public/reports/${token}?mode=${mode}`),
  streamUrl: (id) => `${BASE}/api/v1/audits/${id}/stream`,
  pdfUrl: (id) => `${BASE}/api/v1/reports/${id}/pdf`,
  badge: (id) => request(`/api/v1/reports/${id}/badge`),

  // Module 1
  surgify: (body) =>
    request("/api/v1/prompts/surgify", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  fromAudit: (audit_id) =>
    request("/api/v1/prompts/from-audit", {
      method: "POST",
      body: JSON.stringify({ audit_id }),
    }),
  promptHistory: () => request("/api/v1/prompts/history"),
  agentStatus: () => request("/api/v1/agents/status"),
};

/** The PDF endpoint needs the API key, so fetch it as a blob and save it. */
export async function downloadPdf(id, filename) {
  const res = await fetch(api.pdfUrl(id), { headers: { "X-API-Key": KEY } });
  if (!res.ok) throw new Error("The certificate could not be generated.");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || `fixguard-${id.slice(0, 8)}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
