import { useEffect, useState } from "react";
import { api } from "../lib/api";

export default function History() {
  const [data, setData] = useState(null);
  const [agents, setAgents] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.promptHistory().then(setData).catch((e) => setError(e.message));
    api.agentStatus().then(setAgents).catch(() => {});
  }, []);

  if (error) {
    return (
      <div className="mx-auto max-w-3xl px-5 py-10">
        <p className="rounded-xl bg-red-50 px-4 py-3 text-red-700">{error}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-5 py-10">
      <h1 className="text-2xl font-black tracking-tight text-slate-900">
        Prompt history
      </h1>

      {data && (
        <p className="mt-1 text-slate-600">
          {data.totals.prompt_count} prompt(s) ·{" "}
          <strong>~{data.totals.tokens_saved_estimate.toLocaleString()} tokens</strong>{" "}
          saved against unscoped prompts (estimated)
        </p>
      )}

      {agents && (
        <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">
            Agents
          </h2>
          <p className="mb-3 text-xs text-slate-500">
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

      <div className="mt-6 space-y-3">
        {data?.prompts?.length === 0 && (
          <p className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm text-slate-400">
            No prompts generated yet.
          </p>
        )}
        {data?.prompts?.map((p) => (
          <details key={p.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <summary className="cursor-pointer list-none">
              <span className="font-medium text-slate-800">{p.original_intent}</span>
              <span className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                <code className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">
                  {p.target_selector || "no selector"}
                </code>
                <span>{p.css_property}</span>
                {p.css_value && <span>= {p.css_value}</span>}
                <span className="ml-auto">
                  ~{(p.tokens_saved_estimate || 0).toLocaleString()} tokens saved
                </span>
              </span>
            </summary>
            <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-lg bg-slate-900 p-3 font-mono text-[11px] leading-relaxed text-slate-100">
{p.guarded_prompt}
            </pre>
          </details>
        ))}
      </div>
    </div>
  );
}
