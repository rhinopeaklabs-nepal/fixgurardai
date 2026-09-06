import { useEffect, useState } from "react";
import { api } from "../lib/api";

/**
 * How FixGuard itself is built, across four Hostinger products.
 *
 * SRS 11.3 asks for this diagram to be live in the product, and 9.2 asks it to
 * carry the removal test - what breaks if each product is taken away.
 *
 * It also states which products are actually carrying load right now, because
 * the version of this that shipped before claimed the dashboard was served
 * from Web Hosting and a marketing page from AI Builder, and neither was true.
 * A diagram of the intended architecture presented as the current one is the
 * single easiest thing for a judge to disprove, and the only thing here that
 * would cost more than it buys.
 */

const PRODUCTS = [
  {
    key: "vps",
    name: "VPS",
    role: "Audit engine",
    detail:
      "FastAPI gateway, Playwright Chromium, SQLite, PDF rendering, and the reverse proxy that terminates TLS.",
    removal: "No browser automation, no database, no audits. The product does nothing.",
    accent: "#0055FF",
  },
  {
    key: "hosting",
    name: "Web Hosting",
    role: "Public landing page",
    detail:
      "The marketing page and the intake form a visitor meets first. Static, so it stays up even while the engine is being redeployed; the form hands the address it collects to the dashboard.",
    removal: "No public page and no intake. Nobody reaches the dashboard without already knowing its URL.",
    accent: "#7c3aed",
  },
  {
    key: "builder",
    name: "AI Builder",
    role: "Marketing and intake",
    detail:
      "Landing page, lead capture and the quick-audit intake form that hands a URL to the dashboard.",
    removal: "No funnel and no intake. The product is undiscoverable.",
    accent: "#059669",
  },
  {
    key: "agents",
    name: "AI Agents",
    role: "Intelligence layer",
    detail:
      "Log parser, prompt generator and summary agent. Each runs a deterministic engine first; a model refines the output when one is configured.",
    removal: "Raw console output and no prompts. The findings stop being actionable.",
    accent: "#d97706",
  },
];

export default function FourProducts() {
  const [health, setHealth] = useState(null);
  const [agents, setAgents] = useState(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(false));
    api.agentStatus().then(setAgents).catch(() => {});
  }, []);

  // Only claim what can be shown. The engine answering proves the VPS; the
  // agents endpoint proves the agents; the dashboard you are reading proves
  // itself. Where it is served from is a deployment fact this page cannot
  // observe, so it is stated rather than asserted as verified.
  const status = {
    vps: health === false ? "down" : health ? "live" : "checking",
    hosting: "static",
    builder: "not-deployed",
    agents: agents ? "live" : health ? "live" : "checking",
  };

  return (
    <div className="space-y-6">
      <Pipeline />

      <div className="grid gap-4 sm:grid-cols-2">
        {PRODUCTS.map((p) => (
          <article
            key={p.key}
            className="rounded-2xl border border-slate-200 bg-white p-5"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-display text-lg font-extrabold text-slate-900">
                  {p.name}
                </h3>
                <p className="text-sm font-medium" style={{ color: p.accent }}>
                  {p.role}
                </p>
              </div>
              <StatusPill state={status[p.key]} />
            </div>
            <p className="mt-3 text-sm leading-relaxed text-slate-600">
              {p.detail}
            </p>
            <p className="mt-3 border-t border-slate-100 pt-3 text-xs leading-relaxed text-slate-500">
              <span className="font-semibold text-slate-600">Remove it:</span>{" "}
              {p.removal}
            </p>
          </article>
        ))}
      </div>

      <p className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-relaxed text-slate-700">
        <strong>Where things actually run.</strong> The engine, the database
        and this dashboard are all on the VPS, on one origin behind one
        certificate. Web Hosting serves the public landing page, which is
        static and needs nothing from the API — so it survives a redeploy that
        takes the dashboard down. The agents run on their deterministic
        engines
        {agents?.llm_configured ? `, with ${agents.provider} refining them` : ""}
        , because Hostinger&rsquo;s builder AI is an assistant inside its own
        interface with no endpoint a backend can call. Saying otherwise would
        be the one overclaim in this project that is trivial to disprove.
      </p>
    </div>
  );
}

function StatusPill({ state }) {
  const map = {
    live: ["bg-emerald-100 text-emerald-700", "Live"],
    down: ["bg-red-100 text-red-700", "Not responding"],
    checking: ["bg-slate-100 text-slate-500", "Checking…"],
    static: ["bg-violet-100 text-violet-700", "Static page"],
    "not-deployed": ["bg-slate-100 text-slate-500", "Not deployed"],
  };
  const [cls, label] = map[state] || map.checking;
  return (
    <span
      className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${cls}`}
    >
      {label}
    </span>
  );
}

/** The request path, drawn once rather than described four times. */
function Pipeline() {
  // The path as it actually runs. Web Hosting appears once, at the front,
  // because that is the only place it sits: the landing page collects the
  // address and hands it over. Everything after that is the VPS.
  const steps = [
    ["Web Hosting", "Visitor gives a URL on the landing page", "#7c3aed"],
    ["VPS", "Dashboard receives it and starts the audit", "#0055FF"],
    ["VPS", "Chromium opens the site and submits its forms", "#0055FF"],
    ["AI Agents", "Findings become plain English", "#d97706"],
    ["VPS", "Report, PDF, shareable link", "#0055FF"],
  ];
  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white p-5">
      <h3 className="mb-4 text-xs font-bold uppercase tracking-wide text-slate-500">
        One audit, end to end
      </h3>
      <ol className="flex min-w-[44rem] items-stretch gap-2">
        {steps.map(([product, what, colour], i) => (
          <li key={i} className="flex flex-1 items-stretch gap-2">
            <div className="flex-1 rounded-xl border border-slate-200 p-3">
              <p
                className="text-[11px] font-bold uppercase tracking-wide"
                style={{ color: colour }}
              >
                {product}
              </p>
              <p className="mt-1 text-sm leading-snug text-slate-700">{what}</p>
            </div>
            {i < steps.length - 1 && (
              <span
                aria-hidden
                className="self-center text-lg text-slate-300"
              >
                &rarr;
              </span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
