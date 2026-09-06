import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ALL_MODULES, MODULE_LABELS, api } from "../lib/api";
import { useAuth } from "../lib/auth";

/**
 * The audit console.
 *
 * This is a tool, not a page to read, so it is laid out to be operated: the
 * one field that matters is the first thing under the cursor, the settings
 * almost nobody changes are folded away behind a summary of what they
 * currently say, and the two things that stop you working - your remaining
 * quota and what you already ran - sit beside the form rather than below it.
 *
 * The marketing headline that used to open this page now lives on the landing
 * page, where it is aimed at somebody who has not decided yet. Repeating it to
 * a person who has signed in and come here to run an audit spent the whole
 * first screen telling them something they had already agreed with.
 */

const GRADE_CHIP = {
  verified_healthy: "bg-emerald-100 text-emerald-700",
  minor_issues: "bg-emerald-100 text-emerald-700",
  needs_attention: "bg-amber-100 text-amber-700",
  critical: "bg-red-100 text-red-700",
};
const GRADE_LETTER = {
  verified_healthy: "A", minor_issues: "B", needs_attention: "C", critical: "F",
};

const PAGE_CHOICES = [
  [1, "Just this page"],
  [5, "Up to 5 pages"],
  [10, "Up to 10 pages"],
  [20, "Up to 20 pages"],
  [30, "Up to 30 pages (slowest)"],
];

export default function Home() {
  const [url, setUrl] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [modules, setModules] = useState(ALL_MODULES);
  const [maxPages, setMaxPages] = useState(1);
  const [showOptions, setShowOptions] = useState(false);
  const [needsAuth, setNeedsAuth] = useState(false);
  const [cookieHeader, setCookieHeader] = useState("");
  const [verifyText, setVerifyText] = useState("");
  const [authForms, setAuthForms] = useState(false);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  const [quota, setQuota] = useState(null);
  const navigate = useNavigate();
  const { user } = useAuth();

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

  const firstName = (user?.name || user?.email || "").split(/[\s@]/)[0];
  const pageLabel = PAGE_CHOICES.find(([v]) => v === maxPages)?.[1] ?? "";
  const outOfQuota = quota?.remaining === 0;

  return (
    <div className="mx-auto max-w-6xl px-5 py-8 lg:py-10">
      <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-extrabold tracking-tight text-slate-900">
            {firstName ? `Run an audit, ${firstName}` : "Run an audit"}
          </h1>
          <p className="mt-1 text-slate-600">
            One address. FixGuard opens it in a real browser and reports what
            actually happens.
          </p>
        </div>
        <QuotaMeter quota={quota} />
      </header>

      <div className="grid gap-6 lg:grid-cols-[1.55fr_1fr] lg:items-start">
        {/* ------------------------------------------------ the console */}
        <form
          onSubmit={submit}
          className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"
        >
          <label
            htmlFor="url"
            className="mb-2 block text-sm font-semibold text-slate-700"
          >
            Website address
          </label>
          <div className="flex flex-col gap-2.5 sm:flex-row">
            <input
              id="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="yourbakery.com"
              required
              autoFocus
              autoComplete="url"
              className="flex-1 rounded-xl border border-slate-300 px-4 py-3 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-brand focus:ring-2 focus:ring-brand/20"
            />
            <button
              type="submit"
              disabled={busy || outOfQuota}
              className="rounded-xl bg-brand px-6 py-3 font-semibold text-white transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy ? "Starting…" : "Run audit"}
            </button>
          </div>

          {/* Settings people rarely change, folded away but never hidden:
              the summary line says what they currently are, so collapsing
              them costs no information. */}
          <button
            type="button"
            onClick={() => setShowOptions((v) => !v)}
            aria-expanded={showOptions}
            className="mt-4 flex w-full items-center gap-2 rounded-lg px-1 py-1.5 text-left text-sm text-slate-500 transition hover:text-slate-800"
          >
            <span
              className={`text-slate-400 transition-transform ${showOptions ? "rotate-90" : ""}`}
              aria-hidden
            >
              ›
            </span>
            <span className="font-medium">Options</span>
            {!showOptions && (
              <span className="truncate text-slate-400">
                {modules.length} of {ALL_MODULES.length} checks · {pageLabel}
                {needsAuth ? " · behind a login" : ""}
              </span>
            )}
          </button>

          {showOptions && (
            <div className="mt-2 space-y-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <fieldset>
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
                            prev.includes(m)
                              ? prev.filter((x) => x !== m)
                              : [...prev, m],
                          )
                        }
                        className={`rounded-full border px-3 py-1.5 text-sm font-medium transition ${
                          on
                            ? "border-brand bg-brand/10 text-brand"
                            : "border-slate-300 bg-white text-slate-500 hover:bg-slate-100"
                        }`}
                      >
                        {on ? "✓ " : ""}
                        {MODULE_LABELS[m]}
                      </button>
                    );
                  })}
                </div>
              </fieldset>

              <div>
                <label
                  htmlFor="pages"
                  className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500"
                >
                  How many pages?
                </label>
                <select
                  id="pages"
                  value={maxPages}
                  onChange={(e) => setMaxPages(Number(e.target.value))}
                  className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand"
                >
                  {PAGE_CHOICES.map(([v, label]) => (
                    <option key={v} value={v}>
                      {label}
                    </option>
                  ))}
                </select>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-500">
                  FixGuard finds routes itself: your sitemap first, then by
                  following links from every page it visits. Forms share one
                  budget across the scan.
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <label className="flex items-start gap-2.5 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={needsAuth}
                    onChange={(e) => setNeedsAuth(e.target.checked)}
                    className="mt-0.5 h-4 w-4 accent-[#0055ff]"
                  />
                  <span>
                    <span className="font-semibold">
                      This page is behind a login
                    </span>
                    <span className="mt-0.5 block text-xs leading-relaxed text-slate-500">
                      FixGuard never asks for your password. You stay signed in,
                      and logging out ends its access immediately.
                    </span>
                  </span>
                </label>

                {needsAuth && <AuthBlock
                  cookieHeader={cookieHeader}
                  setCookieHeader={setCookieHeader}
                  verifyText={verifyText}
                  setVerifyText={setVerifyText}
                  authForms={authForms}
                  setAuthForms={setAuthForms}
                />}
              </div>
            </div>
          )}

          <label className="mt-5 flex items-start gap-2.5 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-0.5 h-4 w-4 accent-[#0055ff]"
            />
            <span className="leading-relaxed">
              I own this site or have permission to test it. FixGuard will fill
              in and submit its forms using clearly-labelled test data.
            </span>
          </label>

          {error && (
            <p
              role="alert"
              className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700"
            >
              {error}
            </p>
          )}
        </form>

        {/* ------------------------------------------------- right rail */}
        <aside className="space-y-4">
          <section>
            <div className="mb-2 flex items-baseline justify-between">
              <h2 className="text-sm font-bold uppercase tracking-wide text-slate-500">
                Recent audits
              </h2>
              {history.length > 0 && (
                <Link
                  to="/history"
                  className="text-xs font-medium text-brand hover:underline"
                >
                  All
                </Link>
              )}
            </div>

            {history.length === 0 ? (
              <p className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-10 text-center text-sm leading-relaxed text-slate-400">
                Nothing here yet.
                <br />
                Your first audit will appear here.
              </p>
            ) : (
              <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white">
                {history.slice(0, 8).map((a) => (
                  <li key={a.id}>
                    <Link
                      to={`/a/${a.id}`}
                      className="flex items-center gap-3 px-3.5 py-3 transition hover:bg-slate-50"
                    >
                      <span
                        className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg font-display text-sm font-extrabold ${
                          GRADE_CHIP[a.grade] || "bg-slate-100 text-slate-400"
                        }`}
                      >
                        {GRADE_LETTER[a.grade] || "–"}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-slate-800">
                          {a.target_url.replace(/^https?:\/\//, "")}
                        </span>
                        <span className="block text-xs text-slate-400">
                          {new Date(a.created_at).toLocaleDateString(undefined, {
                            day: "numeric",
                            month: "short",
                          })}
                          {a.duration_ms
                            ? ` · ${(a.duration_ms / 1000).toFixed(1)}s`
                            : ""}
                        </span>
                      </span>
                      <StatusMark run={a} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ quota */

/**
 * The quota is the thing that stops you working, so it is shown as a shape
 * rather than a sentence at the foot of the form. Colour carries the same
 * information as the number, which is what makes it readable at a glance.
 */
function QuotaMeter({ quota }) {
  if (!quota) return null;
  const { remaining, limit, resets_at: resets } = quota;
  const pct = limit ? (remaining / limit) * 100 : 0;
  const tone =
    remaining === 0
      ? { bar: "bg-red-500", text: "text-red-600" }
      : remaining <= 3
        ? { bar: "bg-amber-500", text: "text-amber-600" }
        : { bar: "bg-emerald-500", text: "text-emerald-600" };

  return (
    <div className="min-w-[13rem] rounded-xl border border-slate-200 bg-white px-4 py-3">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Audits this hour
        </span>
        <span className={`font-display text-sm font-extrabold ${tone.text}`}>
          {remaining}
          <span className="font-sans font-normal text-slate-400">/{limit}</span>
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${tone.bar}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-1.5 text-xs leading-snug text-slate-400">
        {remaining === 0 && resets
          ? `Resets ${new Date(resets).toLocaleTimeString()}.`
          : "Audits that cannot reach the site do not count."}
      </p>
    </div>
  );
}

/** State as a shape, not only as a word. */
function StatusMark({ run }) {
  if (run.status === "complete") {
    return (
      <span className="shrink-0 font-display text-sm font-extrabold tabular-nums text-slate-700">
        {run.health_score ?? "n/a"}
      </span>
    );
  }
  if (run.status === "failed") {
    return (
      <span className="shrink-0 rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-semibold text-red-700">
        failed
      </span>
    );
  }
  return (
    <span className="flex shrink-0 items-center gap-1.5 text-[11px] font-medium text-slate-500">
      <span className="h-1.5 w-1.5 animate-ring rounded-full bg-brand" />
      {run.status}
    </span>
  );
}

/* ------------------------------------------------- session handoff block */

function AuthBlock({
  cookieHeader, setCookieHeader,
  verifyText, setVerifyText,
  authForms, setAuthForms,
}) {
  return (
    <div className="mt-4 border-t border-slate-200 pt-4">
      <p className="mb-3 text-sm font-semibold text-slate-700">
        Four clicks, about thirty seconds
      </p>

      <ol className="mb-3 list-none space-y-2.5 p-0">
        <Step n="1">
          Open your site and <strong>sign in as normal</strong>.
        </Step>
        <Step n="2">
          Press <Key>F12</Key>, click the <strong>Network</strong> tab, then
          press <Key>Ctrl</Key> + <Key>R</Key> to reload.
        </Step>
        <Step n="3">
          Click the <strong>Doc</strong> filter button. That hides the scripts
          and images, leaving just your page.
        </Step>
        <Step n="4">
          <strong>Right-click the top row</strong> &rarr; <strong>Copy</strong>{" "}
          &rarr; <strong>Copy as cURL</strong>.
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
      <p className="mt-1 text-xs text-slate-500">{cookieSummary(cookieHeader)}</p>
      <p className="mt-1.5 text-xs text-slate-400">
        Seeing two rows with the same name? Take the first one — the other is
        your service worker re-fetching the page.
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
              Optional. FixGuard already stops if it lands on a sign-in page;
              this makes that check exact.
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
              Also submit forms behind the login. Off by default, because a
              signed-in form may change a setting rather than send a message.
            </span>
          </label>
        </div>
      </details>

      <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-500">
        FixGuard skips your sign-out link and anything that looks like it deletes
        data. Only the cookie <em>names</em> are saved — never their values.
      </p>
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
  if (!text)
    return "Anything works: the cURL command, the request headers, or just the cookie line.";

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
