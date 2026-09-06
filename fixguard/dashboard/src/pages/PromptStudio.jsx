import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

const EXAMPLES = [
  "Make the Send message button background red",
  "Make the main title bigger",
  "Round the corners of the send message button to 12px",
  "Hide the phone field",
];

export default function PromptStudio() {
  const [intent, setIntent] = useState("");
  const [mode, setMode] = useState("url");
  const [pageUrl, setPageUrl] = useState("");
  const [code, setCode] = useState("");
  const [selector, setSelector] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const [totals, setTotals] = useState(null);
  const [tab, setTab] = useState("change");
  const [audits, setAudits] = useState([]);
  const [auditId, setAuditId] = useState("");
  const [fixes, setFixes] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const intentRef = useRef(null);
  const resultRef = useRef(null);

  useEffect(() => {
    api.promptHistory().then((d) => setTotals(d.totals)).catch(() => {});
  }, [result]);

  useEffect(() => {
    if (result || fixes) {
      resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [result, fixes]);

  useEffect(() => {
    if (tab !== "fix") return;
    api
      .listAudits()
      .then((d) => {
        const done = (d.audits || []).filter((a) => a.status === "complete");
        setAudits(done);
        setAuditId((prev) => prev || done[0]?.id || "");
      })
      .catch(() => {});
  }, [tab]);

  async function loadFixes(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      setFixes(await api.fromAudit(auditId.trim()));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function copyFix(fix) {
    try {
      await navigator.clipboard?.writeText(fix.prompt);
      setCopiedId(fix.id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      /* the prompt is selectable below */
    }
  }

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const body = { intent: intent.trim() };
      if (mode === "url") body.page_url = pageUrl.trim();
      if (mode === "code") body.code_context = code;
      if (mode === "selector") body.target_selector = selector.trim();
      setResult(await api.surgify(body));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function copyPrompt() {
    try {
      await navigator.clipboard?.writeText(result.prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* the prompt is selectable below */
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-5 py-8 lg:py-10">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-extrabold tracking-tight text-slate-900">
          Surgical Prompt Studio
        </h1>
        <p className="mt-1 text-slate-600">
          {tab === "fix"
            ? "Pick an audit and FixGuard turns each finding into its own guarded prompt, so you fix one thing at a time instead of asking AI Builder to \u201cfix the site\u201d."
            : "Describe the change you want. FixGuard reads your page, finds the exact element, and writes a prompt scoped so tightly that AI Builder cannot wander off and rewrite the rest of your site."}
        </p>
        {totals?.prompt_count > 0 && (
          <p className="mt-2 text-sm text-slate-500">
            {totals.prompt_count} prompt(s) generated ·{" "}
            <strong className="text-slate-700">
              ~{totals.tokens_saved_estimate.toLocaleString()} tokens
            </strong>{" "}
            saved against unscoped prompts (estimated)
          </p>
        )}
      </header>

      {/* Same segmented control as History and the shared report: two modes
          of one page should not each invent their own switch. */}
      <div className="mb-5 inline-flex rounded-lg border border-slate-300 bg-white p-0.5">
        {[
          ["change", "Make a change"],
          ["fix", "Fix an audit's findings"],
        ].map(([v, label]) => (
          <button
            key={v}
            type="button"
            aria-pressed={tab === v}
            onClick={() => setTab(v)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition ${
              tab === v ? "bg-brand text-white" : "text-slate-600 hover:bg-slate-50"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "fix" ? (
        <form onSubmit={loadFixes} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <label htmlFor="auditPick" className="mb-2 block text-sm font-semibold text-slate-700">
            Which audit do you want to fix?
          </label>
          {audits.length > 0 && (
            <select
              id="auditPick"
              value={audits.some((a) => a.id === auditId) ? auditId : ""}
              onChange={(e) => setAuditId(e.target.value)}
              className="mb-2 w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 outline-none focus:border-brand"
            >
              <option value="">Paste a link or id instead</option>
              {audits.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.health_score}/100 · {a.target_url}
                </option>
              ))}
            </select>
          )}
          <input
            value={auditId}
            onChange={(e) => setAuditId(e.target.value)}
            placeholder="Paste an audit or report link"
            required
            className="w-full rounded-lg border border-slate-300 px-4 py-2.5 font-mono text-sm outline-none focus:border-brand"
          />
          <p className="mt-1 text-xs text-slate-400">
            A dashboard link, a shared report link, or the raw id all work.
          </p>
          <button
            type="submit"
            disabled={busy}
            className="mt-5 w-full rounded-lg bg-brand px-6 py-3 font-semibold text-white transition hover:bg-brand-dark disabled:opacity-50 sm:w-auto"
          >
            {busy ? "Reading the audit..." : "Generate fix prompts"}
          </button>
          {error && (
            <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
          )}
        </form>
      ) : (
      <form onSubmit={submit} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-2 flex items-baseline justify-between">
          <label htmlFor="intent" className="text-sm font-semibold text-slate-700">
            What do you want to change?
          </label>
          <span
            className={`text-xs tabular-nums ${
              intent.length > 450 ? "text-amber-600" : "text-slate-400"
            }`}
          >
            {intent.length}/500
          </span>
        </div>
        <div className="grid max-h-64 overflow-y-auto rounded-lg border border-slate-300 focus-within:border-brand focus-within:ring-2 focus-within:ring-blue-100">
          {/* Invisible replica sizes the grid cell; the textarea fills it. */}
          <div
            aria-hidden="true"
            className="invisible col-start-1 row-start-1 whitespace-pre-wrap break-words px-4 py-3 leading-relaxed"
          >
            {intent + " "}
          </div>
          <textarea
            id="intent"
            ref={intentRef}
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                e.currentTarget.form.requestSubmit();
              }
            }}
            rows={2}
            placeholder="Make the booking button blue"
            maxLength={500}
            required
            className="col-start-1 row-start-1 resize-none overflow-hidden bg-transparent px-4 py-3 leading-relaxed outline-none"
          />
        </div>
        <p className="mt-1 text-xs text-slate-400">
          One change at a time. Ctrl/Cmd + Enter to generate.
        </p>

        <div className="mt-2 flex flex-wrap gap-1.5">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => setIntent(ex)}
              className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-200"
            >
              {ex}
            </button>
          ))}
        </div>

        <fieldset className="mt-5">
          <legend className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">
            Where is this element?
          </legend>
          <div className="mb-3 flex flex-wrap gap-2">
            {[
              ["url", "Page URL"],
              ["code", "Paste HTML"],
              ["selector", "I know the selector"],
            ].map(([v, label]) => (
              <button
                key={v}
                type="button"
                aria-pressed={mode === v}
                onClick={() => setMode(v)}
                className={`rounded-full border px-3 py-1.5 text-sm font-medium transition ${
                  mode === v
                    ? "border-brand bg-blue-50 text-brand"
                    : "border-slate-300 bg-white text-slate-500 hover:bg-slate-50"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {mode === "url" && (
            <input
              value={pageUrl}
              onChange={(e) => setPageUrl(e.target.value)}
              placeholder="yourbakery.com/contact"
              required
              className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-brand"
            />
          )}
          {mode === "code" && (
            <textarea
              value={code}
              onChange={(e) => setCode(e.target.value)}
              rows={6}
              placeholder="<section>...</section>"
              required
              className="w-full rounded-lg border border-slate-300 px-4 py-2.5 font-mono text-xs outline-none focus:border-brand"
            />
          )}
          {mode === "selector" && (
            <input
              value={selector}
              onChange={(e) => setSelector(e.target.value)}
              placeholder="#booking-submit-btn"
              required
              className="w-full rounded-lg border border-slate-300 px-4 py-2.5 font-mono text-sm outline-none focus:border-brand"
            />
          )}
        </fieldset>

        <button
          type="submit"
          disabled={busy}
          className="mt-5 w-full rounded-lg bg-brand px-6 py-3 font-semibold text-white transition hover:bg-brand-dark disabled:opacity-50 sm:w-auto"
        >
          {busy ? "Reading your page..." : "Generate surgical prompt"}
        </button>

        {error && (
          <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
        )}
      </form>
      )}

      <div ref={resultRef}>
        {tab === "fix" ? (
          fixes && <FixList data={fixes} onCopy={copyFix} copiedId={copiedId} />
        ) : result?.out_of_scope ? (
          <OutOfScope result={result} onPick={(v) => setIntent(v)} />
        ) : result ? (
          <Result result={result} onCopy={copyPrompt} copied={copied} />
        ) : null}
      </div>
    </div>
  );
}

function Result({ result, onCopy, copied }) {
  const d = result.diff_preview;
  const s = result.savings;
  const frozen = result.frozen_scope || {};
  const shaky = (result.confidence ?? 0) < 0.5;

  return (
    <div className="mt-8 space-y-4">
      {shaky && (
        <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4">
          <p className="font-semibold text-amber-900">Check this match before using it</p>
          <p className="mt-1 text-sm text-amber-800">
            No element on the page clearly matched your wording, so FixGuard
            picked its best guess. Naming the element's visible text in quotes -
            for example <em>the "Book Now" button</em> - will scope it properly.
          </p>
        </div>
      )}
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="font-display text-lg font-extrabold text-slate-900">Your surgical prompt</h2>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
            {result.engine === "model" ? "model-assisted" : "rules engine"}
          </span>
          <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-brand">
            confidence {Math.round((result.confidence || 0) * 100)}%
          </span>
          <button
            onClick={onCopy}
            className="ml-auto rounded-lg bg-brand px-4 py-1.5 text-sm font-semibold text-white hover:bg-brand-dark"
          >
            {copied ? "Copied" : "Copy for AI Builder"}
          </button>
        </div>
        <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-slate-900 p-4 font-mono text-xs leading-relaxed text-slate-100">
{result.prompt}
        </pre>
      </div>

      {d && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">
            What changes
          </h3>
          <div className="overflow-x-auto rounded-lg border border-slate-200 font-mono text-xs">
            <div className="border-b border-slate-200 bg-slate-50 px-3 py-2 text-slate-600">
              {d.selector} &#123;
            </div>
            <div className="bg-red-50 px-3 py-1.5 text-red-800">
              &nbsp;&nbsp;- {d.property}: {d.before || "not set"};
            </div>
            <div className="bg-emerald-50 px-3 py-1.5 text-emerald-800">
              &nbsp;&nbsp;+ {d.property}: {d.after};
            </div>
            <div className="bg-slate-50 px-3 py-2 text-slate-600">&#125;</div>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            {d.frozen_count} other style group(s) explicitly frozen by the prompt.
          </p>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-500">
            Estimated saving
          </h3>
          <p className="font-display text-3xl font-extrabold text-emerald-600">
            ~{s.tokens_saved_estimate.toLocaleString()}
          </p>
          <p className="text-xs text-slate-500">tokens vs an unscoped prompt</p>
          <p className="mt-2 text-xs text-slate-500">
            About {s.retries_avoided_estimate}{" "}
            {s.retries_avoided_estimate === 1 ? "retry" : "retries"} avoided. {s.basis}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-500">
            Matched element
          </h3>
          <p className="break-all font-mono text-sm text-slate-800">{result.selector || "none"}</p>
          {result.element_label && (
            <p className="mt-1 truncate text-xs text-slate-500">"{result.element_label}"</p>
          )}
          {result.match_reasons?.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs text-slate-500">
              {result.match_reasons.map((r, i) => (
                <li key={i}>· {r}</li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {(frozen.global_tokens?.length > 0 ||
        frozen.parent_layout ||
        frozen.global_font_family) && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-500">
            Frozen so AI Builder cannot touch it
          </h3>
          <ul className="space-y-1 text-sm text-slate-600">
            {frozen.parent_layout?.selector && (
              <li>
                · Parent layout{" "}
                <code className="rounded bg-slate-100 px-1 text-xs">
                  {frozen.parent_layout.selector}
                </code>
              </li>
            )}
            {frozen.global_font_family && <li>· Site font family</li>}
            {frozen.global_tokens?.length > 0 && (
              <li>· {frozen.global_tokens.length} global design token(s)</li>
            )}
            {frozen.shared_selectors?.map((sc, i) => (
              <li key={i}>
                · Shared class <code className="rounded bg-slate-100 px-1 text-xs">.{sc.name}</code>{" "}
                ({sc.used_by} elements)
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.notes?.length > 0 && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
          <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-amber-700">
            Worth knowing
          </h3>
          <ul className="space-y-1.5 text-sm text-amber-900">
            {result.notes.map((n, i) => (
              <li key={i}>· {n}</li>
            ))}
          </ul>
        </div>
      )}

      {result.alternatives?.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-500">
            Did you mean one of these instead?
          </h3>
          <ul className="space-y-1.5 text-sm">
            {result.alternatives.map((a, i) => (
              <li key={i} className="flex gap-2">
                <code className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">
                  {a.selector}
                </code>
                <span className="truncate text-slate-500">{a.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}


function OutOfScope({ result, onPick }) {
  return (
    <div className="mt-8 space-y-4">
      <div className="rounded-2xl border border-amber-300 bg-amber-50 p-5">
        <h2 className="font-display text-lg font-extrabold text-amber-900">
          This one is too broad to scope
        </h2>
        <ul className="mt-2 space-y-2 text-sm leading-relaxed text-amber-900">
          {result.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <h3 className="mb-1 text-sm font-bold uppercase tracking-wide text-slate-500">
          Try one of these instead
        </h3>
        <p className="mb-3 text-xs text-slate-500">
          Taken from elements actually on your page. Pick one to load it.
        </p>
        <div className="flex flex-wrap gap-2">
          {(result.suggestions || []).map((sug) => (
            <button
              key={sug}
              type="button"
              onClick={() => onPick(sug)}
              className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 transition hover:border-brand hover:text-brand"
            >
              {sug}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}


const FIX_SEVERITY = {
  critical: { chip: "bg-red-100 text-red-800", edge: "border-red-300" },
  warning: { chip: "bg-amber-100 text-amber-800", edge: "border-amber-300" },
  info: { chip: "bg-slate-100 text-slate-700", edge: "border-slate-300" },
};

function FixList({ data, onCopy, copiedId }) {
  if (data.total_findings === 0) {
    return (
      <div className="mt-8 rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
        <h2 className="font-display text-lg font-extrabold text-emerald-900">Nothing to fix</h2>
        <p className="mt-1 text-sm text-emerald-800">
          This audit found no issues that need a change to the site.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-8 space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="font-display text-lg font-extrabold text-slate-900">
          {data.fixable_count} prompt{data.fixable_count === 1 ? "" : "s"} to fix{" "}
          {data.host}
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Scored {data.health_score}/100. Paste these into AI Builder one at a
          time, worst first, and re-run the audit afterwards to confirm each fix.
          {data.advisory_count > 0 &&
            ` ${data.advisory_count} finding(s) are hosting settings rather than page changes.`}
        </p>
      </div>

      {data.fixes.map((f, i) => {
        const sev = FIX_SEVERITY[f.severity] || FIX_SEVERITY.info;
        return (
          <div
            key={f.id}
            className={`rounded-2xl border-l-4 border-y border-r border-y-slate-200 border-r-slate-200 bg-white p-5 ${sev.edge}`}
          >
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="text-xs font-bold tabular-nums text-slate-400">
                {String(i + 1).padStart(2, "0")}
              </span>
              <h3 className="font-semibold text-slate-900">{f.title}</h3>
              <span className={`ml-auto rounded-full px-2 py-0.5 text-[11px] font-semibold ${sev.chip}`}>
                {f.severity}
              </span>
            </div>

            {f.problem && <p className="text-sm text-slate-600">{f.problem}</p>}

            {f.evidence && (
              <details className="mt-2">
                <summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-slate-700">
                  What FixGuard observed
                </summary>
                <pre className="mt-1 overflow-x-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 font-mono text-[11px] text-slate-600">
{f.evidence}
                </pre>
              </details>
            )}

            {f.prompt ? (
              <>
                <button
                  onClick={() => onCopy(f)}
                  className="mt-3 rounded-lg bg-brand px-4 py-1.5 text-sm font-semibold text-white hover:bg-brand-dark"
                >
                  {copiedId === f.id ? "Copied" : "Copy for AI Builder"}
                </button>
                <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-lg bg-slate-900 p-4 font-mono text-[11px] leading-relaxed text-slate-100">
{f.prompt}
                </pre>
              </>
            ) : (
              <p className="mt-3 rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-700">
                {f.advisory}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
