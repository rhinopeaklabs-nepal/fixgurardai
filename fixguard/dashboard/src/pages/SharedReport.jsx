import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import {
  Breakdown,
  Evidence,
  FindingCard,
  FormFinding,
  PassedStrip,
  ScoreDial,
} from "../components/Findings";

/**
 * Public report. FR-4.3 requires two modes: a simplified client-facing view
 * and a developer-facing view with the technical detail. The mode is fetched
 * from the API rather than filtered here, so the client view never ships
 * technical payloads to the browser at all.
 *
 * This is the page somebody is handed rather than one they navigated to, and
 * often the only part of FixGuard they will ever see. It is laid out so the
 * verdict is legible before anything is read: the score and what needs
 * attention first, everything that passed collapsed underneath it.
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
      <Shell>
        <div className="rounded-2xl border border-slate-200 bg-white px-6 py-16 text-center">
          <p className="font-display text-lg font-bold text-slate-800">{error}</p>
          <p className="mt-1.5 text-sm text-slate-500">
            Ask whoever sent it for a fresh link.
          </p>
        </div>
      </Shell>
    );
  }

  if (!report) {
    return (
      <Shell>
        <div className="space-y-4">
          <div className="h-40 animate-pulse rounded-2xl bg-slate-200" />
          <div className="h-24 animate-pulse rounded-2xl bg-slate-200" />
        </div>
      </Shell>
    );
  }

  const sb = report.score_breakdown || {};
  const router = report.router || {};
  const rerender = router.rerender || {};
  const forms = report.forms || [];
  const broken = router.broken_routes_list || [];
  const consoleErrors = report.console_error_count || 0;

  // Split once, here, rather than letting each block decide how loud to be.
  const problemForms = forms.filter((f) => f.severity === "critical" || f.severity === "warning");
  const passedForms = forms.filter((f) => !problemForms.includes(f));

  const passed = [];
  if (!router.has_navigation_loop)
    passed.push({
      title: "Navigation is stable",
      detail: "No redirect loops were found while browsing this page.",
    });
  if (!rerender.suspected_infinite_rerender)
    passed.push({
      title: "Rendering settles",
      detail: "The page stops changing itself once it has loaded, as it should.",
    });
  if (broken.length === 0 && router.routes_crawled)
    passed.push({
      title: "Every link checked led somewhere",
      detail: `${router.routes_crawled} link${router.routes_crawled === 1 ? "" : "s"} followed.`,
    });
  if (consoleErrors === 0)
    passed.push({
      title: "No JavaScript errors",
      detail: "The page loaded without logging errors to the console.",
    });
  passedForms.forEach((f) =>
    passed.push({
      title: `Form works: ${f.heading || f.submit_text || "untitled form"}`,
      detail: f.explanation,
    }),
  );

  const problemCount =
    problemForms.length +
    (router.has_navigation_loop ? 1 : 0) +
    (rerender.suspected_infinite_rerender ? 1 : 0) +
    (broken.length ? 1 : 0) +
    (consoleErrors ? 1 : 0);

  return (
    <Shell>
      {/* ------------------------------------------------------- header */}
      <header className="mb-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-display text-base font-extrabold tracking-tight text-brand">
            FixGuard AI
          </span>
          <span className="text-xs font-semibold uppercase tracking-widest text-slate-400">
            Verified site report
          </span>
        </div>
        <h1 className="mt-3 break-all font-display text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
          {report.target_url}
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Checked{" "}
          {new Date(report.completed_at || report.created_at).toLocaleString()}
        </p>
      </header>

      {/* -------------------------------------------------- score + parts */}
      <div className="grid gap-4 lg:grid-cols-[1fr_1.1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <ScoreDial
            score={report.health_score}
            grade={report.grade}
            letter={sb.letter}
            label={sb.label}
          />
          <p className="mt-5 border-t border-slate-100 pt-4 text-sm leading-relaxed text-slate-600">
            {problemCount === 0
              ? "Nothing needing attention was found in the checks below."
              : `${problemCount} thing${problemCount === 1 ? "" : "s"} need${problemCount === 1 ? "s" : ""} attention. Each one below names what was observed.`}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-xs font-bold uppercase tracking-wide text-slate-500">
            How the score is made up
          </h2>
          <Breakdown breakdown={sb.breakdown} />
        </div>
      </div>

      {/* --------------------------------------------------- what to fix */}
      {problemCount > 0 && (
        <section className="mt-9">
          <h2 className="mb-3 font-display text-lg font-extrabold tracking-tight text-slate-900">
            Needs attention
          </h2>
          <div className="space-y-2.5">
            {problemForms.map((f, i) => (
              <FormFinding key={`f${i}`} form={f} />
            ))}

            {router.has_navigation_loop && (
              <FindingCard severity="critical" title="Redirect loop">
                The page repeatedly redirects to itself, which makes it unusable
                for visitors.
                <Evidence
                  lines={[
                    `${router.loop_count ?? "many"} navigations within ${router.window_seconds ?? "the"} seconds`,
                  ]}
                />
              </FindingCard>
            )}

            {rerender.suspected_infinite_rerender && (
              <FindingCard severity="critical" title="Suspected infinite re-render">
                The page keeps changing its own content with no user input. This
                drains battery and slows everything else down.
                <Evidence
                  lines={[
                    `${rerender.peak_mutations_in_window} DOM changes per ${rerender.window_ms}ms`,
                  ]}
                />
              </FindingCard>
            )}

            {broken.length > 0 && (
              <FindingCard
                severity="warning"
                title={`${broken.length} link${broken.length === 1 ? "" : "s"} lead nowhere`}
              >
                Visitors clicking these reach a dead page.
                <Evidence lines={broken.slice(0, 10)} />
              </FindingCard>
            )}

            {consoleErrors > 0 && (
              <FindingCard
                severity="warning"
                title={`${consoleErrors} JavaScript error${consoleErrors === 1 ? "" : "s"} logged`}
              >
                Errors in the browser console often precede visible breakage.
              </FindingCard>
            )}
          </div>
        </section>
      )}

      {/* ------------------------------------------------- what passed */}
      {passed.length > 0 && (
        <section className="mt-6">
          <PassedStrip items={passed} />
        </section>
      )}

      {/* ------------------------------------------ technical detail */}
      <section className="mt-9">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-lg font-extrabold tracking-tight text-slate-900">
            Detail
          </h2>
          <div
            className="inline-flex rounded-lg border border-slate-300 bg-white p-0.5"
            role="group"
            aria-label="Report detail level"
          >
            {[
              ["client", "Summary"],
              ["developer", "Technical"],
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
        </div>

        {mode === "client" ? (
          <p className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-6 text-center text-sm leading-relaxed text-slate-500">
            Switch to <strong>Technical</strong> for the routes that were
            visited, the console output and the files that failed to load.
            <br />
            Useful for whoever is going to fix this.
          </p>
        ) : (
          <TechnicalDetail report={report} />
        )}
      </section>

      <footer className="mt-10 border-t border-slate-200 pt-5 text-xs leading-relaxed text-slate-500">
        <p>
          Generated by FixGuard AI. Form checks confirm that a submission leaves
          the browser and is accepted by the receiving server.{" "}
          <strong className="font-semibold text-slate-600">
            Delivery to a specific mailbox is not verified.
          </strong>
        </p>
        <p className="mt-1.5">
          Reachability is measured from one region, not from everywhere.
        </p>
        {/* Somebody reading a shared report has had no other contact with
            this service and did not agree to anything. Naming what it does
            with data is more warranted here, not less. */}
        <p className="mt-3">
          <a href="/privacy" className="font-medium text-brand hover:underline">
            Privacy
          </a>{" "}
          &middot;{" "}
          <a href="/terms" className="font-medium text-brand hover:underline">
            Terms
          </a>
        </p>
      </footer>
    </Shell>
  );
}

function TechnicalDetail({ report }) {
  const routes = report.routes_map || [];
  const errors = report.console_errors || [];
  const assets = report.asset_issues || [];

  if (!routes.length && !errors.length && !assets.length) {
    return (
      <p className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-6 text-center text-sm text-slate-400">
        No routes, console output or failed files were recorded for this run.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      {routes.length > 0 && (
        <Panel title={`Pages visited (${routes.length})`}>
          <ul className="divide-y divide-slate-100">
            {routes.map((r, i) => (
              <li key={i} className="flex items-center gap-3 px-4 py-2">
                <span
                  className={`h-2 w-2 shrink-0 rounded-full ${r.ok ? "bg-emerald-500" : "bg-red-500"}`}
                  aria-hidden
                />
                <span className="min-w-0 flex-1 truncate font-mono text-xs text-slate-700">
                  {r.path}
                </span>
                <span
                  className={`shrink-0 font-mono text-xs tabular-nums ${r.ok ? "text-slate-400" : "font-semibold text-red-600"}`}
                >
                  {r.status ?? "no reply"}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {errors.length > 0 && (
        <Panel title={`Console output (${errors.length})`}>
          <div className="space-y-2 p-3">
            {errors.map((c, i) => (
              <div key={i} className="rounded-lg bg-slate-900 px-3 py-2">
                <p className="break-all font-mono text-[11px] leading-relaxed text-slate-200">
                  {c.message}
                </p>
                {c.source_url && (
                  <p className="mt-1 truncate font-mono text-[10px] text-slate-300">
                    {c.source_url}
                    {c.line ? `:${c.line}` : ""}
                  </p>
                )}
              </div>
            ))}
          </div>
        </Panel>
      )}

      {assets.length > 0 && (
        <Panel title={`Files that failed to load (${assets.length})`}>
          <ul className="divide-y divide-slate-100">
            {assets.map((a, i) => (
              <li key={i} className="flex items-center gap-3 px-4 py-2">
                <span className="min-w-0 flex-1 truncate font-mono text-xs text-slate-700">
                  {a.url}
                </span>
                <span className="shrink-0 text-xs text-slate-400">
                  {a.resource_type}
                </span>
                <span className="shrink-0 font-mono text-xs font-semibold text-red-600">
                  {a.status || a.failure}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}

function Panel({ title, children }) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <p className="border-b border-slate-100 px-4 py-2.5 text-xs font-bold uppercase tracking-wide text-slate-500">
        {title}
      </p>
      {children}
    </div>
  );
}

function Shell({ children }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-4xl px-5 py-10 lg:py-14">{children}</div>
    </div>
  );
}
