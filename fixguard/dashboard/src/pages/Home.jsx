import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ALL_MODULES, MODULE_LABELS, api } from "../lib/api";

const GRADE_CHIP = {
  verified_healthy: "bg-emerald-100 text-emerald-700",
  minor_issues: "bg-emerald-100 text-emerald-700",
  needs_attention: "bg-amber-100 text-amber-700",
  critical: "bg-red-100 text-red-700",
};
const GRADE_LETTER = {
  verified_healthy: "A", minor_issues: "B", needs_attention: "C", critical: "F",
};

export default function Home() {
  const [url, setUrl] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [modules, setModules] = useState(ALL_MODULES);
  const [maxPages, setMaxPages] = useState(1);
  const [needsAuth, setNeedsAuth] = useState(false);
  const [cookieHeader, setCookieHeader] = useState("");
  const [verifyText, setVerifyText] = useState("");
  const [authForms, setAuthForms] = useState(false);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  const [quota, setQuota] = useState(null);
  const navigate = useNavigate();

  const refresh = () =>
    api
      .listAudits()
      .then((d) => {
        setHistory(d.audits || []);
        if (d.quota) setQuota(d.quota);
      })
      .catch(() => {});

  useEffect(() => {
    refresh();
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError(null);
    if (!consent) {
      setError("Please confirm you own this site or have permission to test it.");
      return;
    }
    setBusy(true);
    try {
      const auth =
        needsAuth && cookieHeader.trim()
          ? {
              cookie_header: cookieHeader.trim(),
              verify_text: verifyText.trim() || null,
              submit_forms: authForms,
            }
          : null;
      const { audit_id } = await api.startAudit(
        url.trim(), modules, maxPages, auth,
      );
      navigate(`/a/${audit_id}`);
    } catch (err) {
      setError(err.message);
      setBusy(false);
      refresh();
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-5 py-12">
      <header className="mb-10 text-center">
        <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-brand">
          Pre-flight QA for AI Builder sites
        </div>
        <h1 className="text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">
          Find what is broken before your customers do
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-slate-600">
          FixGuard submits your forms, watches the console, and follows your routes
          in a real browser. It reports what actually happens, not what the page says.
        </p>
      </header>

      <form onSubmit={submit} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <label htmlFor="url" className="mb-2 block text-sm font-semibold text-slate-700">
          Website address
        </label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            id="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="yourbakery.com"
            required
            className="flex-1 rounded-lg border border-slate-300 px-4 py-3 text-slate-900 outline-none focus:border-brand focus:ring-2 focus:ring-blue-100"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-brand px-6 py-3 font-semibold text-white transition hover:bg-brand-dark disabled:opacity-50"
          >
            {busy ? "Starting..." : "Run audit"}
          </button>
        </div>

        <fieldset className="mt-5">
          <legend className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">
            Checks to run
          </legend>
          <div className="flex flex-wrap gap-2">
            {ALL_MODULES.map((m) => {
              const on = modules.includes(m);
              return (
                <button
                  key={m}
                  type="button"
                  aria-pressed={on}
                  onClick={() =>
                    setModules((prev) =>
                      prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m],
                    )
                  }
                  className={`rounded-full border px-3 py-1.5 text-sm font-medium transition ${
                    on
                      ? "border-brand bg-blue-50 text-brand"
                      : "border-slate-300 bg-white text-slate-500 hover:bg-slate-50"
                  }`}
                >
                  {on ? "✓ " : ""}{MODULE_LABELS[m]}
                </button>
              );
            })}
          </div>
        </fieldset>

        <div className="mt-4">
          <label htmlFor="pages" className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">
            How many pages?
          </label>
          <select
            id="pages"
            value={maxPages}
            onChange={(e) => setMaxPages(Number(e.target.value))}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand"
          >
            <option value={1}>Just this page</option>
            <option value={5}>Up to 5 pages</option>
            <option value={10}>Up to 10 pages</option>
            <option value={20}>Up to 20 pages</option>
            <option value={30}>Up to 30 pages (slowest)</option>
          </select>
          <span className="ml-2 text-xs text-slate-400">
            FixGuard finds routes itself: your sitemap first, then by following
            links from every page it visits. Forms share one budget across the scan.
          </span>
        </div>

        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <label className="flex items-start gap-2.5 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={needsAuth}
              onChange={(e) => setNeedsAuth(e.target.checked)}
              className="mt-0.5 h-4 w-4 accent-[#0055ff]"
            />
            <span>
              <span className="font-semibold">This page is behind a login</span>
              <span className="mt-0.5 block text-xs text-slate-500">
                FixGuard never asks for your password. You stay signed in, and
                logging out ends its access immediately.
              </span>
            </span>
          </label>

          {needsAuth && (
            <div className="mt-4 border-t border-slate-200 pt-4">
              <p className="mb-3 text-sm font-semibold text-slate-700">
                Four clicks, about thirty seconds
              </p>

              <ol className="mb-3 list-none space-y-2.5 p-0">
                <Step n="1">
                  Open your site and <strong>sign in as normal</strong>.
                </Step>
                <Step n="2">
                  Press <Key>F12</Key>, click the <strong>Network</strong> tab,
                  then press <Key>Ctrl</Key> + <Key>R</Key> to reload.
                </Step>
                <Step n="3">
                  Click the <strong>Doc</strong> filter button. That hides the
                  scripts and images, leaving just your page.
                </Step>
                <Step n="4">
                  <strong>Right-click the top row</strong> &rarr;{" "}
                  <strong>Copy</strong> &rarr; <strong>Copy as cURL</strong>.
                </Step>
              </ol>

              <label
                htmlFor="cookieHeader"
                className="mb-1 block text-xs font-bold uppercase tracking-wide text-slate-500"
              >
                Paste it here
              </label>
              <textarea
                id="cookieHeader"
                value={cookieHeader}
                onChange={(e) => setCookieHeader(e.target.value)}
                rows={3}
                placeholder="Paste here — the whole thing, however messy"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-xs outline-none focus:border-brand"
              />
              <p className="mt-1 text-xs text-slate-500">
                {cookieSummary(cookieHeader)}
              </p>
              <p className="mt-1.5 text-xs text-slate-400">
                Seeing two rows with the same name? Take the first one — the
                other is your service worker re-fetching the page.
              </p>

              <details className="mt-3">
                <summary className="cursor-pointer text-xs font-medium text-brand">
                  More options
                </summary>
                <div className="mt-3 space-y-3 border-l-2 border-slate-200 pl-3">
                  <div>
                    <label
                      htmlFor="verifyText"
                      className="mb-1 block text-xs font-semibold text-slate-600"
                    >
                      Text that only appears when you are signed in
                    </label>
                    <input
                      id="verifyText"
                      value={verifyText}
                      onChange={(e) => setVerifyText(e.target.value)}
                      placeholder="your@email.com, or your account name"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand"
                    />
                    <p className="mt-1 text-xs text-slate-500">
                      Optional. FixGuard already stops if it lands on a sign-in
                      page; this makes that check exact.
                    </p>
                  </div>

                  <label className="flex items-start gap-2.5 text-xs text-slate-600">
                    <input
                      type="checkbox"
                      checked={authForms}
                      onChange={(e) => setAuthForms(e.target.checked)}
                      className="mt-0.5 h-3.5 w-3.5 accent-[#0055ff]"
                    />
                    <span>
                      Also submit forms behind the login. Off by default, because
                      a signed-in form may change a setting rather than send a
                      message.
                    </span>
                  </label>
                </div>
              </details>

              <p className="mt-3 rounded-lg bg-white px-3 py-2 text-xs text-slate-500">
                FixGuard skips your sign-out link and anything that looks like it
                deletes data. Only the cookie <em>names</em> are saved — never
                their values.
              </p>
            </div>
          )}
        </div>

        <label className="mt-4 flex items-start gap-2.5 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-0.5 h-4 w-4 accent-[#0055ff]"
          />
          <span>
            I own this site or have permission to test it. FixGuard will fill in and
            submit its forms using clearly-labelled test data.
          </span>
        </label>

        {error && (
          <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
        )}

        {quota && (
          <p
            className={`mt-3 text-xs ${
              quota.remaining === 0
                ? "text-red-600"
                : quota.remaining <= 3
                  ? "text-amber-600"
                  : "text-slate-400"
            }`}
          >
            {quota.remaining} of {quota.limit} audits left this hour
            {quota.remaining === 0 && quota.resets_at
              ? ` · resets ${new Date(quota.resets_at).toLocaleTimeString()}`
              : ""}
            . Audits that cannot reach the site do not count.
          </p>
        )}
      </form>

      <section className="mt-10">
        <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">
          Recent audits
        </h2>
        {history.length === 0 ? (
          <p className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm text-slate-400">
            No audits yet. Run your first one above.
          </p>
        ) : (
          <ul className="divide-y divide-slate-200 overflow-hidden rounded-xl border border-slate-200 bg-white">
            {history.map((a) => (
              <li key={a.id}>
                <Link to={`/a/${a.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50">
                  <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg text-sm font-bold ${GRADE_CHIP[a.grade] || "bg-slate-100 text-slate-400"}`}>
                    {GRADE_LETTER[a.grade] || "-"}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-slate-800">
                      {a.target_url}
                    </span>
                    <span className="block text-xs text-slate-400">
                      {new Date(a.created_at).toLocaleString()}
                      {a.duration_ms ? ` - ${(a.duration_ms / 1000).toFixed(1)}s` : ""}
                    </span>
                  </span>
                  <span className="shrink-0 text-sm font-semibold tabular-nums text-slate-500">
                    {a.status === "complete"
                      ? (a.health_score ?? "n/a")
                      : a.status}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Step({ n, children }) {
  return (
    <li className="flex gap-2.5 text-sm text-slate-600">
      <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-brand text-[11px] font-bold text-white">
        {n}
      </span>
      <span>{children}</span>
    </li>
  );
}

function Key({ children }) {
  return (
    <kbd className="rounded border border-slate-300 bg-white px-1.5 py-0.5 font-mono text-[11px] text-slate-700 shadow-sm">
      {children}
    </kbd>
  );
}

/**
 * Read the paste back to the user before they submit. Pasting the wrong thing
 * is the likeliest mistake here, and it would otherwise only surface as a
 * failed audit a minute later.
 */
function cookieSummary(raw) {
  const text = (raw || "").trim();
  if (!text) return "Anything works: the cURL command, the request headers, or just the cookie line.";

  const line =
    text.match(/-H\s+['"]\s*cookie\s*:\s*([^'"]+)/i)?.[1] ??
    text.match(/^\s*cookie\s*:\s*(.+)$/im)?.[1] ??
    (text.includes("=") ? text : "");

  const names = line
    .split(";")
    .map((p) => p.split("=")[0].trim())
    .filter((n) => n && /^[\w!#$%&'*+.^`|~-]+$/.test(n));

  if (names.length === 0) {
    return "No cookies spotted in that yet — make sure you copied the request while signed in.";
  }
  const shown = names.slice(0, 4).join(", ");
  return `Found ${names.length} cookie${names.length === 1 ? "" : "s"}: ${shown}${
    names.length > 4 ? ", …" : ""
  }`;
}
