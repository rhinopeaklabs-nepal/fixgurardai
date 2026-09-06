import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

/**
 * History.
 *
 * This page used to show only the prompt log, which meant the "History" link
 * in the navigation answered a question nobody had asked: somebody clicking
 * it next to "Prompt Studio" is looking for the audits they ran, and there
 * was nowhere in the app that listed more than the last eight. Audits are now
 * the page, and the prompt log is a tab on it.
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

export default function History() {
  const [tab, setTab] = useState("audits");
  const [audits, setAudits] = useState(null);
  const [prompts, setPrompts] = useState(null);
  const [agents, setAgents] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.listAudits(100).then((d) => setAudits(d.audits || [])).catch((e) => setError(e.message));
    api.promptHistory().then(setPrompts).catch(() => {});
    api.agentStatus().then(setAgents).catch(() => {});
  }, []);

  return (
    <div className="mx-auto max-w-4xl px-5 py-8 lg:py-10">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-extrabold tracking-tight text-slate-900">
          History
        </h1>
        <p className="mt-1 text-slate-600">
          Everything you have run, newest first.
        </p>
      </header>

      <div className="mb-5 inline-flex rounded-lg border border-slate-300 bg-white p-0.5">
        {[
          ["audits", `Audits${audits ? ` (${audits.length})` : ""}`],
          ["prompts", `Prompts${prompts ? ` (${prompts.prompts.length})` : ""}`],
        ].map(([value, label]) => (
          <button
            key={value}
            onClick={() => setTab(value)}
            aria-pressed={tab === value}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition ${
              tab === value ? "bg-brand text-white" : "text-slate-600 hover:bg-slate-50"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {error && (
        <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-700">
          {error}
        </p>
      )}

      {tab === "audits" ? (
        <Audits audits={audits} />
      ) : (
        <Prompts data={prompts} agents={agents} />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ audits */

function Audits({ audits }) {
  if (!audits) return <Skeleton />;

  if (audits.length === 0) {
    return (
      <Empty>
        No audits yet.{" "}
        <Link to="/" className="font-medium text-brand hover:underline">
          Run your first one.
        </Link>
      </Empty>
    );
  }

  // Grouped by day, because "when did I last check this site" is the question
  // this page exists to answer, and a flat list of timestamps answers it
  // slowly.
  const groups = [];
  for (const a of audits) {
    const day = new Date(a.created_at).toLocaleDateString(undefined, {
      weekday: "long",
      day: "numeric",
      month: "long",
    });
    if (groups.at(-1)?.day !== day) groups.push({ day, runs: [] });
    groups.at(-1).runs.push(a);
  }

  return (
    <div className="space-y-6">
      {groups.map((g) => (
        <section key={g.day}>
          <h2 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">
            {g.day}
          </h2>
          <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white">
            {g.runs.map((a) => (
              <li key={a.id}>
                <Link
                  to={`/a/${a.id}`}
                  className="flex items-center gap-3.5 px-4 py-3 transition hover:bg-slate-50"
                >
                  <span
                    className={`grid h-10 w-10 shrink-0 place-items-center rounded-lg font-display font-extrabold ${
                      GRADE_CHIP[a.grade] || "bg-slate-100 text-slate-400"
                    }`}
                  >
                    {GRADE_LETTER[a.grade] || "–"}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-slate-800">
                      {a.target_url.replace(/^https?:\/\//, "")}
                    </span>
                    <span className="block text-xs text-slate-400">
                      {new Date(a.created_at).toLocaleTimeString(undefined, {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                      {a.duration_ms ? ` · ${(a.duration_ms / 1000).toFixed(1)}s` : ""}
                      {a.error_code ? ` · ${a.error_code}` : ""}
                    </span>
                  </span>
                  <Status run={a} />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function Status({ run }) {
  if (run.status === "complete")
    return (
      <span className="shrink-0 font-display text-lg font-extrabold tabular-nums text-slate-700">
        {run.health_score ?? "n/a"}
      </span>
    );
  if (run.status === "failed")
    return (
      <span className="shrink-0 rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-semibold text-red-700">
        failed
      </span>
    );
  return (
    <span className="flex shrink-0 items-center gap-1.5 text-[11px] font-medium text-slate-500">
      <span className="h-1.5 w-1.5 animate-ring rounded-full bg-brand" />
      {run.status}
    </span>
  );
}

/* ----------------------------------------------------------------- prompts */

function Prompts({ data, agents }) {
  if (!data) return <Skeleton />;

  return (
    <div className="space-y-5">
      {data.totals && (
        <div className="flex flex-wrap gap-x-8 gap-y-3 rounded-xl border border-slate-200 bg-white px-5 py-4">
          <Stat n={data.totals.prompt_count} label="prompts generated" />
          <Stat
            n={`~${(data.totals.tokens_saved_estimate || 0).toLocaleString()}`}
            label="tokens saved against unscoped prompts (estimated)"
          />
        </div>
      )}

      {agents && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">
            Agents
          </h2>
          <p className="mb-3 text-sm leading-relaxed text-slate-600">
            {agents.llm_configured
              ? `Model-backed via ${agents.provider}. The rules engine still runs first and vetoes any selector the model invents.`
              : "No model configured, so every agent is running on its deterministic engine. This is a supported mode, not a degraded one."}
          </p>
          <ul className="space-y-2">
            {Object.entries(agents.agents).map(([key, a]) => (
              <li key={key} className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-mono text-xs text-slate-500">{key}</span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
                  {a.mode}
                </span>
                <span className="text-slate-600">{a.role}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.prompts.length === 0 ? (
        <Empty>
          No prompts generated yet.{" "}
          <Link to="/prompts" className="font-medium text-brand hover:underline">
            Open the Prompt Studio.
          </Link>
        </Empty>
      ) : (
        <div className="space-y-2.5">
          {data.prompts.map((p) => (
            <details
              key={p.id}
              className="group overflow-hidden rounded-xl border border-slate-200 bg-white"
            >
              <summary className="cursor-pointer list-none px-4 py-3.5">
                <span className="font-medium text-slate-800">
                  {p.original_intent}
                </span>
                <span className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                  <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-600">
                    {p.target_selector || "no selector"}
                  </code>
                  {p.css_property && <span>{p.css_property}</span>}
                  {p.css_value && <span>= {p.css_value}</span>}
                  <span className="ml-auto shrink-0">
                    ~{(p.tokens_saved_estimate || 0).toLocaleString()} tokens saved
                  </span>
                </span>
              </summary>
              <pre className="overflow-x-auto whitespace-pre-wrap border-t border-slate-100 bg-slate-900 p-4 font-mono text-[11px] leading-relaxed text-slate-100">
{p.guarded_prompt}
              </pre>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ pieces */

function Stat({ n, label }) {
  return (
    <div>
      <p className="font-display text-2xl font-extrabold tabular-nums text-slate-900">
        {n}
      </p>
      <p className="mt-0.5 max-w-[16rem] text-xs leading-snug text-slate-500">
        {label}
      </p>
    </div>
  );
}

function Empty({ children }) {
  return (
    <p className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-12 text-center text-sm text-slate-500">
      {children}
    </p>
  );
}

function Skeleton() {
  return (
    <div className="space-y-3">
      <div className="h-16 animate-pulse rounded-xl bg-slate-200" />
      <div className="h-16 animate-pulse rounded-xl bg-slate-200" />
      <div className="h-16 animate-pulse rounded-xl bg-slate-200" />
    </div>
  );
}
