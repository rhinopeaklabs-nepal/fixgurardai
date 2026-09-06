import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { MODULE_LABELS, api, downloadPdf } from "../lib/api";
import { Breakdown, FindingCard, FormFinding, ScoreDial } from "../components/Findings";

export default function AuditDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [run, setRun] = useState(null);
  const [log, setLog] = useState([]);
  const [percent, setPercent] = useState(0);
  const [doneModules, setDoneModules] = useState([]);
  const [error, setError] = useState(null);
  const [shareUrl, setShareUrl] = useState(null);
  const [copied, setCopied] = useState(false);
  const [badge, setBadge] = useState(null);
  const [pdfBusy, setPdfBusy] = useState(false);
  const esRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setLog([]);
    setPercent(0);
    setDoneModules([]);
    setError(null);

    async function load() {
      try {
        const data = await api.getReport(id);
        if (cancelled) return;
        setRun(data);
        setShareUrl(data.share_url || null);
        setPercent(data.progress_percent || 0);
        setDoneModules(data.modules_complete || []);
        if (data.status === "complete" || data.status === "failed") return;
        openStream();
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }

    function openStream() {
      const es = new EventSource(api.streamUrl(id));
      esRef.current = es;

      es.addEventListener("progress", (e) => {
        const d = JSON.parse(e.data);
        if (typeof d.percent === "number") setPercent(d.percent);
        if (d.step) {
          setLog((prev) => (prev[prev.length - 1] === d.step ? prev : [...prev, d.step]));
        }
      });
      es.addEventListener("module_complete", (e) => {
        const d = JSON.parse(e.data);
        setDoneModules((prev) => (prev.includes(d.module) ? prev : [...prev, d.module]));
      });

      const finish = async () => {
        es.close();
        try {
          const data = await api.getReport(id);
          if (!cancelled) setRun(data);
        } catch (err) {
          if (!cancelled) setError(err.message);
        }
      };
      es.addEventListener("complete", finish);
      es.addEventListener("failed", finish);
      es.onerror = () => {
        es.close();
        finish();
      };
    }

    load();
    return () => {
      cancelled = true;
      esRef.current?.close();
    };
  }, [id]);

  async function makeShare() {
    let url = shareUrl;
    try {
      url = (await api.share(id)).share_url;
      setShareUrl(url);
    } catch (err) {
      setError(err.message);
      return;
    }
    // Copying is a convenience. Clipboard permission is denied in plenty of
    // contexts, and that must never cost the user their report.
    try {
      await navigator.clipboard?.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* link is shown below for manual copying */
    }
  }

  async function getPdf() {
    setPdfBusy(true);
    try {
      const host = (run.target_url || "site").replace(/^https?:\/\//, "").split("/")[0];
      await downloadPdf(id, `fixguard-${host}-${id.slice(0, 8)}.pdf`);
    } catch (err) {
      setError(err.message);
    } finally {
      setPdfBusy(false);
    }
  }

  async function getBadge() {
    try {
      if (!shareUrl) await makeShare();
      setBadge(await api.badge(id));
    } catch (err) {
      setError(err.message);
    }
  }

  async function retry() {
    try {
      const { audit_id } = await api.retryAudit(id);
      navigate(`/a/${audit_id}`);
    } catch (err) {
      setError(err.message);
    }
  }

  if (error && !run) {
    return (
      <Shell>
        <p className="rounded-xl bg-red-50 px-4 py-3 text-red-700">{error}</p>
      </Shell>
    );
  }
  if (!run) return <Shell><Skeleton /></Shell>;

  const selected = run.modules_selected || [];
  const running = run.status === "queued" || run.status === "running";

  if (running) {
    return (
      <Shell>
        <h1 className="mb-1 text-xl font-bold text-slate-900">Auditing</h1>
        <p className="mb-6 break-all text-sm text-slate-500">{run.target_url}</p>
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <div className="mb-3 flex items-center gap-3">
            <span className="animate-ring h-3 w-3 rounded-full bg-brand" />
            <span className="font-medium text-slate-700">
              {log[log.length - 1] || run.stage || "Starting"}
            </span>
            <span className="ml-auto text-sm font-semibold tabular-nums text-slate-400">
              {percent}%
            </span>
          </div>

          <div
            className="mb-5 h-2 overflow-hidden rounded-full bg-slate-200"
            role="progressbar"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="h-full rounded-full bg-brand transition-all duration-500"
              style={{ width: `${percent}%` }}
            />
          </div>

          <div className="mb-4 flex flex-wrap gap-2">
            {selected.map((m) => (
              <span
                key={m}
                className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                  doneModules.includes(m)
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                {doneModules.includes(m) ? "✓ " : ""}
                {MODULE_LABELS[m] || m}
              </span>
            ))}
          </div>

          <ol className="space-y-1.5 text-sm text-slate-500">
            {log.map((m, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-emerald-500">✓</span>
                <span>{m}</span>
              </li>
            ))}
          </ol>
        </div>
      </Shell>
    );
  }

  if (run.status === "failed") {
    return (
      <Shell>
        <FindingCard
          severity="critical"
          title="This audit could not complete"
          badge={run.error_code}
        >
          <p className="break-all">{run.error_detail}</p>
          {run.retryable ? (
            <button
              onClick={retry}
              className="mt-3 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-dark"
            >
              Retry this audit
            </button>
          ) : (
            <p className="mt-2 text-slate-500">
              Check the address is public and reachable, then try again.
            </p>
          )}
        </FindingCard>
      </Shell>
    );
  }

  const forms = run.form_results || [];
  const router = run.router_result || {};
  const rerender = router.rerender || {};
  const routesMap = router.routes_map || [];
  const consoleErrors = (run.console_errors || []).filter(
    (c) => c.severity === "critical",
  );
  const assets = run.asset_issues || [];
  const sb = run.score_breakdown || {};
  const reach = run.reachability;
  const auth = run.auth_info;
  const a11y = run.accessibility;
  const perf = run.performance;
  const mobile = run.mobile;
  const reachSeverity = !reach
    ? "info"
    : reach.dns_resolved === false || reach.ip_blocked || reach.tls?.valid === false
      ? "critical"
      : reach.issues?.length
        ? "warning"
        : "ok";
  // Agent 1 explanations, keyed by the raw message each one explains.
  const parsedById = Object.fromEntries(
    (run.parsed_errors || []).map((x) => [x.message, x]),
  );

  return (
    <Shell>
      {error && (
        <p className="mb-4 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {error}
        </p>
      )}

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Site Health Report</h1>
          <p className="break-all text-sm text-slate-500">{run.target_url}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={getPdf}
            disabled={pdfBusy}
            className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-dark disabled:opacity-50"
          >
            {pdfBusy ? "Building..." : "Download certificate"}
          </button>
          <button
            onClick={makeShare}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            {copied ? "Link copied" : shareUrl ? "Copy share link" : "Create share link"}
          </button>
          <Link
            to={`/a/${id}/compare`}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Compare to last run
          </Link>
          <button
            onClick={getBadge}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Get badge
          </button>
        </div>
      </div>

      {sb.grade === "not_assessed" && (
        <div className="mb-5 rounded-2xl border-l-4 border-amber-500 border-y border-r border-y-slate-200 border-r-slate-200 bg-white p-5">
          <h2 className="font-bold text-slate-900">This site was not assessed</h2>
          <p className="mt-1 text-slate-700">{sb.not_assessed_reason}</p>
          {run.partial_reason && (
            <p className="mt-2 text-sm text-slate-600">
              What stopped it: {run.partial_reason}
            </p>
          )}
          <p className="mt-2 text-sm text-slate-500">
            No score is shown, because a score here would describe checks that
            never ran.
          </p>
        </div>
      )}

      {run.partial_reason && sb.grade !== "not_assessed" && (
        <div className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <p className="font-semibold text-amber-900">Partial audit</p>
          <p className="mt-1 text-sm text-amber-800">
            The page could not be opened in a browser ({run.partial_reason}), so
            the {(run.modules_failed || []).join(", ")} check
            {(run.modules_failed || []).length === 1 ? "" : "s"} could not run.
            The score below is calculated only from what was measured.
          </p>
        </div>
      )}

      {run.executive_summary && (
        <div className="mb-5 rounded-2xl border border-slate-200 bg-white p-5">
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-500">
            Summary
          </h2>
          <p className="leading-relaxed text-slate-700">{run.executive_summary}</p>
        </div>
      )}

      {badge && (
        <div className="mb-5 rounded-2xl border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">
            Verification badge
          </h2>
          <div className="mb-3" dangerouslySetInnerHTML={{ __html: badge.preview_svg }} />
          <p className="mb-2 text-xs text-slate-500">
            Paste this into your site footer. It fetches the latest score on load,
            so re-running an audit updates it everywhere.
          </p>
          <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-[11px] text-slate-100">
{badge.embed_script}
          </pre>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <ScoreDial
            score={run.health_score}
            grade={run.grade}
            letter={sb.letter}
            label={sb.label}
          />
          {sb.capped_by_critical && (
            <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
              Score capped: a critical issue is present, so this site cannot be
              rated higher regardless of what else passes.
            </p>
          )}
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">
            Breakdown
          </h3>
          <Breakdown breakdown={sb.breakdown} />
        </div>
      </div>

      {selected.includes("form") && (
        <Section title="Forms">
          {forms.length === 0 ? (
            <Empty>No forms were found on this page.</Empty>
          ) : (
            forms.map((f, i) => <FormFinding key={i} form={f} />)
          )}
        </Section>
      )}

      {selected.includes("router") && (
        <>
          <Section title="Navigation">
            {router.has_navigation_loop ? (
              <FindingCard
                severity="critical"
                title="Redirect loop detected"
                badge="navigation loop"
              >
                <p>
                  The page navigated to the same address {router.loop_count} times
                  within {router.window_seconds} seconds. Visitors will see a
                  frozen or flickering page.
                </p>
                {router.page_load_blocked_by_loop && (
                  <p className="mt-2">
                    The loop is severe enough that the page never finished loading.
                  </p>
                )}
                {router.loop_url && (
                  <p className="mt-2 break-all font-mono text-xs text-slate-500">
                    {router.loop_url}
                  </p>
                )}
              </FindingCard>
            ) : (
              <FindingCard severity="ok" title="No redirect loops">
                {router.total_navigations} navigation(s) observed, none repeating.
              </FindingCard>
            )}

            <FindingCard
              severity={rerender.suspected_infinite_rerender ? "critical" : "ok"}
              title={
                rerender.suspected_infinite_rerender
                  ? "Suspected infinite re-render"
                  : "Rendering is stable"
              }
              badge={rerender.suspected_infinite_rerender ? "re-render loop" : undefined}
            >
              {rerender.suspected_infinite_rerender ? (
                <p>
                  The page changed {rerender.peak_mutations_in_window} DOM nodes in{" "}
                  {rerender.window_ms}ms with no user input, well past the
                  threshold of {rerender.threshold}. This is the signature of a{" "}
                  <code className="rounded bg-slate-100 px-1">useEffect</code>{" "}
                  that updates state on every render. It burns battery and CPU
                  without logging any error.
                </p>
              ) : (
                <p>
                  Peak DOM churn was {rerender.peak_mutations_in_window ?? 0} changes
                  per {rerender.window_ms ?? 2000}ms, within normal range.
                </p>
              )}
            </FindingCard>
          </Section>

          <Section
            title={`Routes discovered (${router.routes_crawled ?? 0} of ${
              router.links_discovered ?? 0
            } found)`}
          >
            {router.discovery_sources?.length > 0 && (
              <p className="mb-2 text-sm text-slate-600">
                Found via {router.discovery_sources.join(", ")}
                {router.queue_remaining > 0 && (
                  <>
                    {" "}
                    &mdash; {router.queue_remaining} more were found but not
                    checked. Raise the page limit to include them.
                  </>
                )}
              </p>
            )}
            {routesMap.length === 0 ? (
              <Empty>No internal links were found to follow.</Empty>
            ) : (
              <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                {routesMap.map((r, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 border-b border-slate-100 px-4 py-2.5 last:border-0"
                  >
                    <span
                      className={`h-2 w-2 shrink-0 rounded-full ${
                        r.ok ? "bg-emerald-500" : "bg-red-500"
                      }`}
                    />
                    <span className="min-w-0 flex-1 truncate font-mono text-xs text-slate-700">
                      {r.path}
                    </span>
                    {r.soft_404 && (
                      <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
                        renders "not found"
                      </span>
                    )}
                    <span className="shrink-0 text-xs tabular-nums text-slate-400">
                      {r.status ?? "no response"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Section>
        </>
      )}

      {selected.includes("reach") && reach && (
        <Section title="DNS, TLS and reachability">
          <FindingCard
            severity={reachSeverity}
            title={
              reach.issues?.length
                ? `${reach.issues.length} reachability issue(s)`
                : "Reachable, with a valid certificate"
            }
          >
            <ul className="space-y-1">
              <li>
                DNS {reach.dns_resolved ? "resolves" : "does not resolve"}
                {reach.ip_addresses?.length ? ` to ${reach.ip_addresses.join(", ")}` : ""}
              </li>
              <li>
                HTTP {reach.status_code ?? "no response"}
                {reach.response_time_ms != null ? ` in ${reach.response_time_ms}ms` : ""}
              </li>
              {reach.tls?.checked && (
                <li>
                  TLS certificate{" "}
                  {reach.tls.valid === true
                    ? `valid${
                        reach.tls.days_remaining != null
                          ? `, expires in ${reach.tls.days_remaining} days`
                          : ""
                      }`
                    : reach.tls.valid === false
                      ? "invalid"
                      : "could not be checked"}
                  {reach.tls.issuer ? ` (${reach.tls.issuer})` : ""}
                </li>
              )}
            </ul>
            {reach.issues?.length > 0 && (
              <ul className="mt-2 space-y-1 text-slate-700">
                {reach.issues.map((x, i) => (
                  <li key={i}>&middot; {x}</li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs text-slate-400">{reach.multi_region_note}</p>
          </FindingCard>
        </Section>
      )}

      {auth?.used && (
        <Section title="Signed-in audit">
          <FindingCard
            severity={auth.verified ? "ok" : "warning"}
            title={
              auth.verified
                ? "Audited while signed in"
                : "The session could not be confirmed"
            }
            badge={auth.cookie_names?.length ? `${auth.cookie_names.length} cookie(s)` : undefined}
          >
            <p>{auth.detail}</p>
            {auth.cookie_names?.length > 0 && (
              <p className="mt-2 text-xs text-slate-500">
                Sent: {auth.cookie_names.join(", ")}. Only the names are stored
                &mdash; the values were used for this audit and never saved.
              </p>
            )}
            {auth.skipped_links?.length > 0 && (
              <>
                <p className="mt-3 font-medium text-slate-700">
                  {auth.skipped_links.length} link(s) deliberately not followed:
                </p>
                <ul className="mt-1 space-y-0.5 text-xs">
                  {auth.skipped_links.slice(0, 8).map((l, i) => (
                    <li key={i} className="flex flex-wrap gap-2">
                      <code className="rounded bg-slate-100 px-1 font-mono text-slate-600">
                        {l.url.replace(/^https?:\/\/[^/]+/, "")}
                      </code>
                      <span className="text-slate-500">{l.reason}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </FindingCard>
        </Section>
      )}

      {mobile?.measured && (
        <Section title="On a phone">
          <FindingCard
            severity={
              mobile.issue_count === 0
                ? "ok"
                : mobile.groups?.some((g) => g.impact === "critical")
                  ? "critical"
                  : "warning"
            }
            title={
              mobile.issue_count === 0
                ? "The layout works on a phone"
                : `${mobile.issue_count} mobile layout issue(s)`
            }
            badge={`${mobile.viewport_width}px viewport`}
          >
            {mobile.issue_count === 0 ? (
              <p>
                No sideways scrolling, tap targets are large enough, and text is
                readable at phone size.
              </p>
            ) : (
              <IssueGroups groups={mobile.groups} />
            )}
          </FindingCard>
        </Section>
      )}

      {a11y?.measured && (
        <Section title={`Accessibility (${a11y.issue_count} issue(s))`}>
          <FindingCard
            severity={
              a11y.issue_count === 0
                ? "ok"
                : a11y.groups?.some((g) => g.impact === "critical")
                  ? "critical"
                  : "warning"
            }
            title={
              a11y.issue_count === 0
                ? "No accessibility problems found"
                : "People using assistive technology will hit these"
            }
          >
            {a11y.issue_count === 0 ? (
              <p>
                Images have alt text, form fields have labels, and text contrast
                passes at the sizes checked.
              </p>
            ) : (
              <IssueGroups groups={a11y.groups} />
            )}
          </FindingCard>
        </Section>
      )}

      {perf?.measured && (
        <Section title="Speed">
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <div className="grid gap-3 sm:grid-cols-4">
              <Metric
                label="Largest paint"
                value={fmtMs(perf.metrics?.lcp_ms)}
                band={perf.bands?.lcp_ms}
              />
              <Metric
                label="First paint"
                value={fmtMs(perf.metrics?.fcp_ms)}
                band={perf.bands?.fcp_ms}
              />
              <Metric
                label="Layout shift"
                value={perf.metrics?.cls ?? "--"}
                band={perf.bands?.cls}
              />
              <Metric
                label="Blocking time"
                value={fmtMs(perf.metrics?.tbt_ms)}
                band={perf.bands?.tbt_ms}
              />
            </div>
            {perf.notes?.length > 0 && (
              <ul className="mt-4 space-y-1 border-t border-slate-100 pt-3 text-sm text-slate-600">
                {perf.notes.map((n, i) => (
                  <li key={i}>&middot; {n}</li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-xs text-slate-400">
              Measured on one load from this server, so treat it as a smoke test
              rather than field data from real visitors.
            </p>
          </div>
        </Section>
      )}

      {run.pages_audited > 1 && (
        <Section title={`Pages audited (${run.pages_audited})`}>
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            <div className="flex items-center gap-3 border-b border-slate-100 bg-slate-50 px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              <span className="flex-1">Page</span>
              <span className="w-12 text-right">Forms</span>
              <span className="w-12 text-right">A11y</span>
              <span className="w-12 text-right">Speed</span>
            </div>
            <div className="flex items-center gap-3 border-b border-slate-100 px-4 py-2.5">
              <span className="min-w-0 flex-1 truncate font-mono text-xs text-slate-700">
                {run.target_url} <em className="not-italic text-slate-400">(entry)</em>
              </span>
              <span className="w-12 text-right text-xs tabular-nums text-slate-500">
                {forms.length}
              </span>
              <span className="w-12 text-right text-xs tabular-nums text-slate-500">
                {a11y?.score ?? "--"}
              </span>
              <span className="w-12 text-right text-xs tabular-nums text-slate-500">
                {perf?.score ?? "--"}
              </span>
            </div>
            {(run.pages || []).map((pg, i) => (
              <div
                key={i}
                className="flex items-center gap-3 border-b border-slate-100 px-4 py-2.5 last:border-0"
              >
                <span className="min-w-0 flex-1 truncate font-mono text-xs text-slate-700">
                  {pg.url}
                </span>
                <span className="w-12 text-right text-xs tabular-nums text-slate-500">
                  {pg.forms_tested ?? 0}
                </span>
                <span className="w-12 text-right text-xs tabular-nums text-slate-500">
                  {pg.a11y?.score ?? "--"}
                </span>
                <span className="w-12 text-right text-xs tabular-nums text-slate-500">
                  {pg.performance?.score ?? "--"}
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title={`Console errors (${consoleErrors.length})`}>
        {consoleErrors.length === 0 ? (
          <Empty>No JavaScript errors were logged.</Empty>
        ) : (
          <div className="space-y-2">
            {consoleErrors.slice(0, 15).map((c, i) => {
              const parsed = parsedById[c.message];
              return (
                <div key={i} className="rounded-lg border border-slate-200 bg-white p-3">
                  {parsed && (
                    <>
                      <p className="font-medium text-slate-800">{parsed.meaning}</p>
                      <p className="mt-0.5 text-sm text-slate-600">{parsed.action}</p>
                    </>
                  )}
                  <p className="mt-2 break-all font-mono text-xs text-slate-500">
                    {c.message}
                  </p>
                  {c.source_url && (
                    <p className="mt-0.5 truncate font-mono text-[11px] text-slate-400">
                      {c.source_url}
                      {c.line ? `:${c.line}` : ""}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Section>

      {selected.includes("assets") && assets.length > 0 && (
        <Section title={`Broken assets (${assets.length})`}>
          <div className="space-y-2">
            {assets.map((a, i) => (
              <div key={i} className="rounded-lg border border-slate-200 bg-white p-3">
                <p className="truncate font-mono text-xs text-slate-700">{a.url}</p>
                <p className="text-[11px] text-slate-400">
                  {a.resource_type} - {a.status || a.failure}
                </p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {shareUrl && (
        <p className="mt-8 break-all rounded-xl bg-slate-100 px-4 py-3 text-xs text-slate-600">
          Public report:{" "}
          <a className="text-brand underline" href={shareUrl}>
            {shareUrl}
          </a>
        </p>
      )}
    </Shell>
  );
}

function Shell({ children }) {
  return (
    <div className="mx-auto max-w-3xl px-5 py-10">
      <Link to="/" className="mb-6 inline-block text-sm font-medium text-brand hover:underline">
        &larr; New audit
      </Link>
      {children}
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section className="mt-8">
      <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">{title}</h2>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Empty({ children }) {
  return (
    <p className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-6 text-center text-sm text-slate-400">
      {children}
    </p>
  );
}

function Skeleton() {
  return (
    <div className="space-y-3">
      <div className="h-28 animate-pulse rounded-2xl bg-slate-200" />
      <div className="h-20 animate-pulse rounded-2xl bg-slate-200" />
    </div>
  );
}


function fmtMs(v) {
  if (v == null) return "--";
  return v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${v}ms`;
}

const BAND_STYLE = {
  good: "text-emerald-600",
  needs_improvement: "text-amber-600",
  poor: "text-red-600",
  unknown: "text-slate-400",
};

function Metric({ label, value, band }) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </div>
      <div className={`text-xl font-bold tabular-nums ${BAND_STYLE[band] || "text-slate-700"}`}>
        {value}
      </div>
      <div className="text-[11px] text-slate-400">
        {(band || "").replace("_", " ") || "not measured"}
      </div>
    </div>
  );
}

const IMPACT_CHIP = {
  critical: "bg-red-100 text-red-800",
  serious: "bg-orange-100 text-orange-800",
  moderate: "bg-slate-100 text-slate-700",
  minor: "bg-slate-100 text-slate-600",
};

function IssueGroups({ groups }) {
  return (
    <ul className="space-y-2.5">
      {(groups || []).map((g) => (
        <li key={g.rule}>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                IMPACT_CHIP[g.impact] || IMPACT_CHIP.minor
              }`}
            >
              {g.impact}
            </span>
            <span className="text-sm font-medium text-slate-800">
              {g.count > 1 ? `${g.count}x ` : ""}
              {g.rule}
            </span>
          </div>
          <p className="mt-0.5 text-sm text-slate-600">{g.message}</p>
          {g.examples?.[0]?.selector && (
            <p className="mt-0.5 font-mono text-[11px] text-slate-400">
              {g.examples.map((e) => e.selector).filter(Boolean).slice(0, 3).join("  ")}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
