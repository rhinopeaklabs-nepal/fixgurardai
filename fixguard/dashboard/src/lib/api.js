// An empty VITE_API_BASE_URL means "same origin", which is how the single
// docker-compose deployment serves the dashboard: nginx hands /api to the
// api container, so the bundle needs no absolute host. The check is against
// undefined rather than falsy, because `"" || fallback` would quietly send
// production traffic to the developer's own machine.
const RAW_BASE = import.meta.env.VITE_API_BASE_URL;
const BASE = (RAW_BASE === undefined ? "http://127.0.0.1:8000" : RAW_BASE)
  .replace(/\/$/, "");

// There is deliberately no API key in this bundle any more. It used to ship
// one so the dashboard could authenticate, which meant view-source handed it
// to anybody. The session cookie replaced it: httpOnly, so no script on this
// page can read it either, and the key is now only ever a server-to-server
// credential. Requests must opt into sending cookies explicitly.
const CREDENTIALS = "include";

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
    credentials: CREDENTIALS,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
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
  listAudits: (limit = 25) => request(`/api/v1/audits?limit=${limit}`),
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

  // Accounts. /me answers 200 with a null user when signed out, so the
  // app can ask "who is this" on every load without treating the normal
  // signed-out state as an error.
  me: (opts) => request("/api/v1/auth/me", opts),
  signup: (email, password, name) =>
    request("/api/v1/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    }),
  login: (email, password) =>
    request("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request("/api/v1/auth/logout", { method: "POST" }),

  // SRS 10.2 and 10.4. Deleting an audit takes its share link with it, so a
  // link already handed to a client stops resolving - which is the point.
  // Administration. These answer 404 to anyone who is not a listed admin,
  // so a non-admin dashboard that called them by mistake would see the same
  // thing as a typo rather than a locked door worth rattling.
  adminOverview: (days = 30) => request(`/api/v1/admin/overview?days=${days}`),
  adminUsers: () => request("/api/v1/admin/users"),
  adminAudits: (limit = 50, status = null) =>
    request(
      `/api/v1/admin/audits?limit=${limit}` + (status ? `&status=${status}` : ""),
    ),

  deleteAudit: (id) => request(`/api/v1/audits/${id}`, { method: "DELETE" }),
  deleteMyData: () => request("/api/v1/account/data", { method: "DELETE" }),
};

/**
 * The PDF endpoint is authenticated, and a plain link cannot carry the
 * session in a way that also names the file, so fetch it and save the blob.
 */
export async function downloadPdf(id, filename) {
  const res = await fetch(api.pdfUrl(id), { credentials: CREDENTIALS });
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
