import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";

/**
 * The architecture of the site under audit.
 *
 * The page is ordered by what a site owner actually needs to know, not by what
 * is easiest to collect. The dependency graph leads, because "who else
 * receives a request from my visitors" is the finding people have never seen
 * before; structure and composition are reference material and sit below it.
 *
 * Everything is observed from a real page load. The host list comes from
 * requests the browser actually made, so a tracker loaded by another tracker
 * still appears.
 */

// Semantic, and ordered by how much a site owner should care.
const KINDS = {
  "first party": { label: "Your own domain", bar: "#334155", dot: "bg-slate-700", chip: "bg-slate-200 text-slate-800", watching: false },
  advertising: { label: "Advertising", bar: "#e11d48", dot: "bg-rose-500", chip: "bg-rose-100 text-rose-800", watching: true },
  analytics: { label: "Analytics", bar: "#7c3aed", dot: "bg-violet-500", chip: "bg-violet-100 text-violet-800", watching: true },
  "support chat": { label: "Support chat", bar: "#4f46e5", dot: "bg-indigo-500", chip: "bg-indigo-100 text-indigo-800", watching: true },
  "form handling": { label: "Form handling", bar: "#65a30d", dot: "bg-lime-600", chip: "bg-lime-100 text-lime-800", watching: true },
  payments: { label: "Payments", bar: "#059669", dot: "bg-emerald-500", chip: "bg-emerald-100 text-emerald-800", watching: false },
  "bot protection": { label: "Bot protection", bar: "#0d9488", dot: "bg-teal-500", chip: "bg-teal-100 text-teal-800", watching: false },
  media: { label: "Media", bar: "#c026d3", dot: "bg-fuchsia-500", chip: "bg-fuchsia-100 text-fuchsia-800", watching: false },
  cdn: { label: "CDN", bar: "#0284c7", dot: "bg-sky-500", chip: "bg-sky-100 text-sky-800", watching: false },
  fonts: { label: "Fonts", bar: "#d97706", dot: "bg-amber-500", chip: "bg-amber-100 text-amber-800", watching: false },
  other: { label: "Uncategorised", bar: "#94a3b8", dot: "bg-slate-400", chip: "bg-slate-100 text-slate-600", watching: true },
};

const kindOf = (k) => KINDS[k] || KINDS.other;

export default function Architecture() {
  const [audits, setAudits] = useState([]);
  const [auditId, setAuditId] = useState("");
  const [run, setRun] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .listAudits()
      .then((d) => {
        const seen = new Set();
        const done = (d.audits || []).filter((a) => {
          if (a.status !== "complete" || seen.has(a.target_url)) return false;
          seen.add(a.target_url);
          return true;
        });
        setAudits(done);
        setAuditId((prev) => prev || done[0]?.id || "");
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!auditId) return;
    setRun(null);
    api.getReport(auditId).then(setRun).catch((e) => setError(e.message));
  }, [auditId]);

  const map = run?.site_map;

  return (
    <div className="mx-auto max-w-4xl px-5 py-10">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-extrabold tracking-tight text-slate-900">
            Site architecture
          </h1>
          <p className="mt-1 max-w-xl text-slate-600">
            What this site is built from, and who else receives a request when
            someone visits it.
          </p>
        </div>

        {audits.length > 0 && (
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            <span className="mb-1 block">Site</span>
            <select
              value={auditId}
              onChange={(e) => setAuditId(e.target.value)}
              className="max-w-xs rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-slate-800 outline-none focus:border-brand"
            >
              {audits.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.target_url.replace(/^https?:\/\//, "")}
                </option>
              ))}
            </select>
          </label>
        )}
      </header>

      {error && <p className="rounded-xl bg-red-50 px-4 py-3 text-red-700">{error}</p>}

      {!error && audits.length === 0 && (
        <Empty>Run an audit first — this page maps whatever site you point FixGuard at.</Empty>
      )}

      {auditId && !run && !error && <Skeleton />}

      {run && !map?.measured && (
        <Empty>
          This audit ran before the structure map existed, or the page never
          loaded. Re-run it to map this site.
        </Empty>
      )}

      {map?.measured && <SiteMap map={map} run={run} />}

      <BuiltWith />
    </div>
  );
}

function SiteMap({ map, run }) {
  const hosts = map.hosts || [];
  const thirdParty = hosts.filter((h) => !h.first_party);

  // Group by purpose, because "who is watching" is the question, not "which
  // hostnames appeared".
  const groups = useMemo(() => {
    const by = new Map();
    for (const h of hosts) {
      const k = h.kind || "other";
      if (!by.has(k)) by.set(k, { kind: k, hosts: [], requests: 0, failed: 0 });
      const g = by.get(k);
      g.hosts.push(h);
      g.requests += h.requests || 0;
      g.failed += h.failed || 0;
    }
    const order = Object.keys(KINDS);
    return [...by.values()].sort(
      (a, b) => order.indexOf(a.kind) - order.indexOf(b.kind),
    );
  }, [hosts]);

  const total = map.total_requests || hosts.reduce((n, h) => n + h.requests, 0) || 1;
  const watchers = thirdParty.filter((h) => kindOf(h.kind).watching);
  const c = map.counts || {};
  const scriptForms = (map.forms || []).filter((f) => f.handled_by_script).length;
  const offsiteForms = (map.forms || []).filter((f) => f.action_host).length;

  return (
    <>
      {/* ---------- identity + at a glance ---------- */}
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="p-5">
          <h2 className="text-lg font-bold leading-snug text-slate-900">
            {map.title || "Untitled page"}
          </h2>
          <p className="break-all text-sm text-slate-500">
            {map.origin}
            {map.path}
          </p>
          {map.description && (
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-600">
              {map.description}
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Fact label="language" value={map.lang || "not declared"} bad={!map.lang} />
            <Fact
              label="viewport"
              value={map.has_viewport_meta ? "declared" : "missing"}
              bad={!map.has_viewport_meta}
            />
            <Fact label="canonical" value={map.canonical ? "set" : "none"} />
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-px border-t border-slate-200 bg-slate-200 sm:grid-cols-4">
          <Stat n={total} label="requests to load it" />
          <Stat
            n={thirdParty.length}
            label="other companies contacted"
            tone={thirdParty.length > 10 ? "warn" : undefined}
          />
          <Stat n={(map.forms || []).length} label="forms on the page" />
          <Stat n={c.scripts} label="scripts" />
        </dl>
      </section>

      {/* ---------- the headline finding ---------- */}
      <Section
        title="Who this page talks to"
        note={`${total} requests across ${hosts.length} host${hosts.length === 1 ? "" : "s"}`}
      >
        {thirdParty.length === 0 ? (
          <Empty>
            Everything loaded from this site's own domain. No third party
            received a request.
          </Empty>
        ) : (
          <>
            {watchers.length > 0 && (
              <p className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-900">
                <strong>{watchers.length}</strong> of these are advertising,
                analytics or uncategorised services. Each one receives your
                visitor's IP address and the page they are on, whether or not
                they interact with it.
              </p>
            )}

            {/* One bar, so proportion is read rather than calculated. */}
            <div className="mb-1.5 flex h-3 w-full overflow-hidden rounded-full bg-slate-100">
              {groups.map((g) => {
                const pct = (g.requests / total) * 100;
                if (pct < 0.4) return null;
                return (
                  <span
                    key={g.kind}
                    title={`${kindOf(g.kind).label}: ${g.requests} requests`}
                    style={{ width: `${pct}%`, background: kindOf(g.kind).bar }}
                  />
                );
              })}
            </div>
            <p className="mb-5 text-xs text-slate-400">
              Share of requests by purpose
            </p>

            <div className="space-y-2">
              {groups.map((g) => (
                <HostGroup key={g.kind} group={g} total={total} />
              ))}
            </div>
          </>
        )}
      </Section>

      {/* ---------- forms ---------- */}
      <Section
        title="Forms, and where they send"
        note={
          scriptForms || offsiteForms
            ? [
                scriptForms && `${scriptForms} handled by JavaScript`,
                offsiteForms && `${offsiteForms} sent off-site`,
              ]
                .filter(Boolean)
                .join(" · ")
            : undefined
        }
      >
        {(map.forms || []).length === 0 ? (
          <Empty>No forms on this page.</Empty>
        ) : (
          <div className="space-y-2">
            {map.forms.map((f) => (
              <FormRow key={f.index} form={f} />
            ))}
          </div>
        )}
      </Section>

      {/* ---------- structure, secondary ---------- */}
      <Section title="Structure">
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title={`Heading outline (${(map.outline || []).length})`}>
            {(map.outline || []).length === 0 ? (
              <Empty small>
                No headings, so nothing gives this page an outline for screen
                readers or search engines.
              </Empty>
            ) : (
              <ol className="max-h-72 overflow-y-auto">
                {map.outline.map((h, i) => (
                  <li
                    key={i}
                    className="flex gap-2.5 border-b border-slate-100 py-1.5 last:border-0"
                    style={{ paddingLeft: `${(h.level - 1) * 0.9}rem` }}
                  >
                    <span className="shrink-0 font-mono text-[10px] leading-5 text-slate-400">
                      h{h.level}
                    </span>
                    <span className="text-sm leading-5 text-slate-700">{h.text}</span>
                  </li>
                ))}
              </ol>
            )}
          </Panel>

          <Panel
            title={`Links (${(map.internal_links || []).length} internal, ${
              (map.external_links || []).length
            } external)`}
          >
            <div className="max-h-72 overflow-y-auto">
              {(map.internal_links || []).map((l) => {
                const broken = (run?.router_result?.broken_routes_list || []).includes(
                  l.path,
                );
                return (
                  <div
                    key={`i-${l.path}`}
                    className="flex items-center gap-2 border-b border-slate-100 py-1.5 last:border-0"
                  >
                    <span
                      className={`min-w-0 flex-1 truncate font-mono text-xs ${
                        broken ? "text-red-600 line-through" : "text-slate-700"
                      }`}
                    >
                      {l.path}
                    </span>
                    {broken && (
                      <span className="shrink-0 rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-700">
                        broken
                      </span>
                    )}
                    <span className="shrink-0 text-[11px] tabular-nums text-slate-400">
                      {l.count}
                    </span>
                  </div>
                );
              })}
              {(map.external_links || []).map((l) => (
                <div
                  key={`e-${l.host}`}
                  className="flex items-center gap-2 border-b border-slate-100 py-1.5 last:border-0"
                >
                  <span className="min-w-0 flex-1 truncate font-mono text-xs text-slate-500">
                    ↗ {l.host}
                  </span>
                  <span className="shrink-0 text-[11px] tabular-nums text-slate-400">
                    {l.count}
                  </span>
                </div>
              ))}
            </div>
            {(map.mailto_links > 0 || map.tel_links > 0) && (
              <p className="mt-2 text-xs text-slate-500">
                Plus {map.mailto_links} email and {map.tel_links} phone link(s).
              </p>
            )}
          </Panel>
        </div>
      </Section>

      {/* ---------- reference ---------- */}
      <Section title="Reference">
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="Page composition">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-3">
              {[
                ["elements", c.elements],
                ["images", c.images],
                ["scripts", c.scripts],
                ["stylesheets", c.stylesheets],
                ["iframes", c.iframes],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2">
                  <dt className="text-slate-500">{k}</dt>
                  <dd className="font-semibold tabular-nums text-slate-800">
                    {v ?? "--"}
                  </dd>
                </div>
              ))}
            </dl>
          </Panel>

          <Panel title="Detected on the page">
            {(map.libraries || []).length === 0 ? (
              <Empty small>No frameworks or trackers identified by name.</Empty>
            ) : (
              <ul className="space-y-1.5">
                {map.libraries.map((l) => (
                  <li key={l.name} className="flex flex-wrap items-baseline gap-2">
                    <span className="text-sm font-medium text-slate-800">{l.name}</span>
                    <span className="font-mono text-[10px] text-slate-400">
                      via {l.evidence}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </Section>
    </>
  );
}

/** One purpose-group of hosts, collapsed until asked for. */
function HostGroup({ group, total }) {
  const [open, setOpen] = useState(group.kind === "advertising");
  const k = kindOf(group.kind);
  const pct = Math.round((group.requests / total) * 100);

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-slate-50"
      >
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${k.dot}`} />
        <span className="font-semibold text-slate-800">{k.label}</span>
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${k.chip}`}>
          {group.hosts.length} host{group.hosts.length === 1 ? "" : "s"}
        </span>
        {group.failed > 0 && (
          <span className="rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-semibold text-red-700">
            {group.failed} failed
          </span>
        )}
        <span className="ml-auto text-sm tabular-nums text-slate-500">
          {group.requests}
          <span className="ml-1 text-xs text-slate-400">({pct}%)</span>
        </span>
        <span className={`text-slate-400 transition-transform ${open ? "rotate-90" : ""}`}>
          ›
        </span>
      </button>

      {open && (
        <ul className="border-t border-slate-100">
          {group.hosts
            .slice()
            .sort((a, b) => b.requests - a.requests)
            .map((h) => (
              <li
                key={h.host}
                className="flex items-center gap-3 border-b border-slate-50 px-4 py-2 pl-10 last:border-0"
              >
                <span className="min-w-0 flex-1 truncate font-mono text-xs text-slate-700">
                  {h.host}
                </span>
                {h.failed > 0 && (
                  <span className="shrink-0 text-[11px] font-semibold text-red-600">
                    {h.failed} failed
                  </span>
                )}
                <span className="shrink-0 text-xs tabular-nums text-slate-400">
                  {h.requests}
                </span>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}

function FormRow({ form: f }) {
  const offsite = Boolean(f.action_host);
  return (
    <div
      className={`rounded-xl border bg-white p-4 ${
        f.handled_by_script || offsite ? "border-amber-200" : "border-slate-200"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-semibold text-slate-900">{f.name}</h3>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-600">
          {f.method}
        </span>
        <span className="ml-auto text-xs text-slate-400">
          {f.field_count} field{f.field_count === 1 ? "" : "s"}
        </span>
      </div>

      <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
        {f.handled_by_script ? (
          <>
            No <code className="rounded bg-slate-100 px-1">action</code> attribute
            — JavaScript decides where this goes, so it stops working the moment
            that code breaks.
          </>
        ) : (
          <>
            Sends to <code className="rounded bg-slate-100 px-1 text-xs">{f.action}</code>
            {offsite && (
              <>
                {" "}
                — an external service (
                <span className="font-mono text-xs">{f.action_host}</span>), which
                therefore receives whatever visitors type in.
              </>
            )}
          </>
        )}
      </p>

      {f.fields?.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {f.fields.map((fl, i) => (
            <span
              key={i}
              className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-600"
            >
              {fl.name || fl.type}
              {fl.required && <span className="text-red-500">*</span>}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function BuiltWith() {
  const [open, setOpen] = useState(false);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    if (!open) return;
    api.health().then(setHealth).catch(() => setHealth(false));
  }, [open]);

  const rows = [
    ["VPS", "FastAPI, Playwright Chromium, SQLite, PDF rendering"],
    ["Web Hosting", "This dashboard, audit reports, public shared reports"],
    ["AI Builder", "Marketing page and lead capture"],
    ["Hostinger Agent", "Provisioning, VPS diagnostics, deployment debugging"],
  ];

  return (
    <section className="mt-10 border-t border-slate-200 pt-5">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="text-sm font-medium text-slate-500 hover:text-slate-800"
      >
        {open ? "Hide" : "How FixGuard itself is built"}
      </button>

      {open && (
        <div className="mt-3 space-y-2">
          <p className="text-sm text-slate-600">
            FixGuard runs on four Hostinger products.{" "}
            {health === false
              ? "The audit engine is not responding right now."
              : health
                ? `The engine is up: ${health.service} v${health.version}.`
                : "Checking the engine…"}
          </p>
          <ul className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            {rows.map(([name, role]) => (
              <li
                key={name}
                className="flex flex-wrap gap-x-3 border-b border-slate-100 px-4 py-2 last:border-0"
              >
                <span className="w-32 shrink-0 text-sm font-semibold text-slate-800">
                  {name}
                </span>
                <span className="text-sm text-slate-600">{role}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

/* ---------------- small pieces ---------------- */

function Stat({ n, label, tone }) {
  return (
    <div className="bg-white px-4 py-3">
      <dt
        className={`text-2xl font-bold tabular-nums ${
          tone === "warn" ? "text-amber-600" : "text-slate-900"
        }`}
      >
        {n ?? "--"}
      </dt>
      <dd className="mt-0.5 text-xs leading-snug text-slate-500">{label}</dd>
    </div>
  );
}

function Fact({ label, value, bad }) {
  return (
    <span
      className={`rounded-full px-2.5 py-1 text-xs ${
        bad ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-600"
      }`}
    >
      <span className="font-semibold">{label}:</span> {value}
    </span>
  );
}

function Section({ title, note, children }) {
  return (
    <section className="mt-9">
      <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="text-sm font-bold uppercase tracking-wide text-slate-500">
          {title}
        </h2>
        {note && <span className="text-xs text-slate-400">{note}</span>}
      </div>
      {children}
    </section>
  );
}

function Panel({ title, children }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">
        {title}
      </h3>
      {children}
    </div>
  );
}

function Empty({ children, small }) {
  return (
    <p
      className={`rounded-xl border border-dashed border-slate-300 bg-white text-center text-slate-400 ${
        small ? "px-3 py-3 text-xs" : "px-4 py-5 text-sm"
      }`}
    >
      {children}
    </p>
  );
}

function Skeleton() {
  return (
    <div className="space-y-4">
      <div className="h-40 animate-pulse rounded-2xl bg-slate-200" />
      <div className="h-24 animate-pulse rounded-2xl bg-slate-200" />
    </div>
  );
}
