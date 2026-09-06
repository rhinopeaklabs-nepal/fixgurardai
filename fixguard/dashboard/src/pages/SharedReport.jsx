import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import { Breakdown, FindingCard, FormFinding, ScoreDial } from "../components/Findings";

/**
 * Public report. FR-4.3 requires two modes: a simplified client-facing view
 * and a developer-facing view with the technical detail. The mode is fetched
 * from the API rather than filtered here, so the client view never ships
 * technical payloads to the browser at all.
 */
export default function SharedReport() {
  const { token } = useParams();
  const [mode, setMode] = useState("client");
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api
      .publicReport(token, mode)
      .then((d) => !cancelled && setReport(d))
      .catch((err) => {
        if (cancelled) return;
        setError(
          err.code === "REPORT_EXPIRED"
            ? "This report link has expired."
            : "This report could not be found.",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [token, mode]);

  if (error) {
    return (
      <Wrap>
        <p className="rounded-xl bg-white px-4 py-8 text-center text-slate-500 shadow-sm">
          {error}
        </p>
      </Wrap>
    );
  }
  if (!report) {
    return (
      <Wrap>
        <div className="h-40 animate-pulse rounded-2xl bg-slate-200" />
      </Wrap>
    );
  }

  const sb = report.score_breakdown || {};
  const router = report.router || {};
  const rerender = router.rerender || {};

  return (
    <Wrap>
      <header className="mb-6">
        <p className="text-xs font-bold uppercase tracking-widest text-brand">
          FixGuard AI - Verified Site Report
        </p>
        <h1 className="mt-1 break-all text-xl font-bold text-slate-900">
          {report.target_url}
        </h1>
        <p className="text-sm text-slate-500">
          Checked {new Date(report.completed_at || report.created_at).toLocaleString()}
        </p>

        <div
          className="mt-4 inline-flex rounded-lg border border-slate-300 bg-white p-0.5"
          role="group"
          aria-label="Report detail level"
        >
          {[
            ["client", "Summary"],
            ["developer", "Technical detail"],
          ].map(([value, label]) => (
            <button
              key={value}
              onClick={() => setMode(value)}
              aria-pressed={mode === value}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                mode === value
                  ? "bg-brand text-white"
                  : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <ScoreDial
            score={report.health_score}
            grade={report.grade}
            letter={sb.letter}
            label={sb.label}
          />
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">
            Breakdown
          </h3>
          <Breakdown breakdown={sb.breakdown} />
        </div>
      </div>

      <section className="mt-8 space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wide text-slate-500">
          What we checked
        </h2>

        {(report.forms || []).map((f, i) => (
          <FormFinding key={i} form={f} />
        ))}

        <FindingCard
          severity={router.has_navigation_loop ? "critical" : "ok"}
          title={
            router.has_navigation_loop
              ? "Redirect loop detected"
              : "Navigation is stable"
          }
        >
          {router.has_navigation_loop
            ? "The page repeatedly redirects to itself, which makes it unusable for visitors."
            : "No redirect loops were found while browsing this page."}
        </FindingCard>

        <FindingCard
          severity={rerender.suspected_infinite_rerender ? "critical" : "ok"}
          title={
            rerender.suspected_infinite_rerender
              ? "Suspected infinite re-render"
              : "Rendering is stable"
          }
        >
          {rerender.suspected_infinite_rerender
            ? `The page changed ${rerender.peak_mutations_in_window} elements in ${rerender.window_ms}ms with no user input. This drains battery and slows the page.`
            : "The page settles after loading, as it should."}
        </FindingCard>

        {(router.broken_routes_list || []).length > 0 && (
          <FindingCard severity="warning" title="Broken links found">
            <p>
              {router.broken_routes_list.length} of {router.routes_crawled} checked
              links did not load correctly.
            </p>
            <ul className="mt-2 space-y-0.5 font-mono text-xs text-slate-500">
              {router.broken_routes_list.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          </FindingCard>
        )}

        <FindingCard
          severity={report.console_error_count > 0 ? "warning" : "ok"}
          title={
            report.console_error_count > 0
              ? `${report.console_error_count} JavaScript error(s) logged`
              : "No JavaScript errors"
          }
        >
          {report.console_error_count > 0
            ? "Errors in the browser console often precede visible breakage."
            : "The page loaded without logging errors."}
        </FindingCard>
      </section>

      {mode === "developer" && (
        <section className="mt-8 space-y-3">
          <h2 className="text-sm font-bold uppercase tracking-wide text-slate-500">
            Technical detail
          </h2>

          {(report.routes_map || []).length > 0 && (
            <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
              {report.routes_map.map((r, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 border-b border-slate-100 px-4 py-2 last:border-0"
                >
                  <span
                    className={`h-2 w-2 shrink-0 rounded-full ${
                      r.ok ? "bg-emerald-500" : "bg-red-500"
                    }`}
                  />
                  <span className="min-w-0 flex-1 truncate font-mono text-xs text-slate-700">
                    {r.path}
                  </span>
                  <span className="shrink-0 text-xs tabular-nums text-slate-400">
                    {r.status ?? "no response"}
                  </span>
                </div>
              ))}
            </div>
          )}

          {(report.console_errors || []).map((c, i) => (
            <div key={i} className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="break-all font-mono text-xs text-slate-800">{c.message}</p>
              {c.source_url && (
                <p className="mt-1 truncate font-mono text-[11px] text-slate-400">
                  {c.source_url}
                  {c.line ? `:${c.line}` : ""}
                </p>
              )}
            </div>
          ))}

          {(report.asset_issues || []).map((a, i) => (
            <div key={i} className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="truncate font-mono text-xs text-slate-700">{a.url}</p>
              <p className="text-[11px] text-slate-400">
                {a.resource_type} - {a.status || a.failure}
              </p>
            </div>
          ))}
        </section>
      )}

      <footer className="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-400">
        Generated by FixGuard AI. Form checks confirm that a submission leaves the
        browser and is accepted by the receiving server. Delivery to a specific
        mailbox is not verified.
      </footer>
    </Wrap>
  );
}

function Wrap({ children }) {
  return <div className="mx-auto max-w-3xl px-5 py-12">{children}</div>;
}
