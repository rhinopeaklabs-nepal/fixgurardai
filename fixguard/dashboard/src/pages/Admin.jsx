import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

/**
 * The operator's console.
 *
 * Not a dashboard to read: a screen somebody opens when they suspect
 * something is wrong, so it is ordered by what would make them act. Anything
 * needing attention is at the top and absent when there is nothing to say;
 * the steady-state numbers sit under it; the tables are last.
 *
 * It refreshes itself and says when it last managed to. A monitoring page
 * that silently stops updating is worse than one that never did, because
 * stale numbers look exactly like fresh ones.
 */
const REFRESH_MS = 15000;

export default function Admin() {
  const [data, setData] = useState(null);
  const [users, setUsers] = useState(null);
  const [audits, setAudits] = useState(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState(null);
  const [fetchedAt, setFetchedAt] = useState(null);
  const [live, setLive] = useState(true);
  const alive = useRef(true);

  const load = useCallback(async () => {
    try {
      const d = await api.adminOverview(30);
      if (!alive.current) return;
      setData(d);
      setFetchedAt(new Date());
      setError(null);
    } catch (err) {
      if (alive.current) setError(err.message);
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    load();
    api.adminUsers().then((d) => alive.current && setUsers(d.users)).catch(() => {});
    return () => {
      alive.current = false;
    };
  }, [load]);

  useEffect(() => {
    api
      .adminAudits(60, filter || null)
      .then((d) => alive.current && setAudits(d.audits))
      .catch(() => {});
  }, [filter]);

  // Polling a hidden tab spends the box's one core on a screen nobody is
  // looking at, and this is the same machine that has to drive Chromium.
  useEffect(() => {
    if (!live) return;
    const t = setInterval(() => {
      if (!document.hidden) load();
    }, REFRESH_MS);
    return () => clearInterval(t);
  }, [live, load]);

  if (error && !data) {
    return (
      <Page>
        <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-700">
          {error}
        </p>
      </Page>
    );
  }
  if (!data) {
    return (
      <Page>
        <div className="h-24 animate-pulse rounded-2xl bg-slate-200" />
      </Page>
    );
  }

  const a = data.audits;
  const runner = data.live;
  const proc = data.process;
  const database = data.database;
  const requests = data.requests;
  const attention = buildAttention(data.stuck, proc, a, runner);

  return (
    <Page>
      <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-slate-400">
            Operations
          </p>
          <h1 className="mt-1 font-display text-2xl font-extrabold tracking-tight text-slate-900">
            System
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Up {formatDuration(proc.uptime_seconds)} · since{" "}
            {new Date(proc.started_at).toLocaleString()}
          </p>
        </div>
        <Freshness
          at={fetchedAt}
          live={live}
          stale={Boolean(error)}
          onToggle={() => setLive((v) => !v)}
        />
      </header>

      {attention.length > 0 && (
        <section className="mb-7">
          <h2 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">
            Needs attention
          </h2>
          <ul className="space-y-2">
            {attention.map((item) => (
              <li
                key={item.title}
                className={`flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-xl border-l-4 px-4 py-3 ${
                  item.level === "critical"
                    ? "border-l-red-500 bg-red-50 text-red-900"
                    : "border-l-amber-500 bg-amber-50 text-amber-900"
                }`}
              >
                <span className="font-semibold">{item.title}</span>
                <span className="text-sm">{item.detail}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* --------------------------------------------------------- headline */}
      <section className="mb-8 grid gap-px overflow-hidden rounded-2xl border border-slate-200 bg-slate-200 sm:grid-cols-2 lg:grid-cols-4">
        <Tile
          label="Running now"
          value={runner.in_flight.length}
          note={
            runner.slots_free === null
              ? `${runner.concurrency_limit} at a time`
              : `${runner.slots_free} of ${runner.concurrency_limit} slots free`
          }
          tone={runner.slots_free === 0 ? "busy" : "ok"}
        />
        <Tile
          label="Audits finished"
          value={(a.by_status.complete || 0) + (a.by_status.failed || 0)}
          note={
            a.success_rate === null
              ? "none yet"
              : `${a.success_rate}% completed cleanly`
          }
          tone={a.success_rate !== null && a.success_rate < 90 ? "warn" : "ok"}
        />
        <Tile
          label="Median audit"
          value={a.duration_ms.p50 ? `${(a.duration_ms.p50 / 1000).toFixed(1)}s` : "–"}
          note={
            a.duration_ms.p90
              ? `p90 ${(a.duration_ms.p90 / 1000).toFixed(1)}s · ${a.duration_ms.samples} runs`
              : "not enough runs yet"
          }
        />
        <Tile
          label="Requests served"
          value={requests.total.toLocaleString()}
          note={`since this process started · ${requests.by_status["5xx"] || 0} 5xx`}
          tone={(requests.by_status["5xx"] || 0) > 0 ? "warn" : "ok"}
        />
      </section>

      {/* ----------------------------------------------------------- volume */}
      <section className="mb-8 grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <Panel title={`Audits per day · last ${a.window_days} days`}>
          <DailyBars daily={a.daily} />
        </Panel>

        <Panel title="Why runs failed">
          {a.failures.length === 0 ? (
            <Quiet>No failures in this window.</Quiet>
          ) : (
            <ul className="divide-y divide-slate-100">
              {a.failures.map((f) => (
                <li
                  key={`${f.code}-${f.retryable}`}
                  className="flex items-center gap-3 px-4 py-2.5"
                >
                  <code className="min-w-0 flex-1 truncate font-mono text-xs text-slate-700">
                    {f.code}
                  </code>
                  {f.retryable && (
                    <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                      retryable
                    </span>
                  )}
                  <span className="shrink-0 font-display text-sm font-extrabold tabular-nums text-slate-800">
                    {f.count}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </section>

      {/* --------------------------------------------------------- capacity */}
      <section className="mb-8 grid gap-5 md:grid-cols-2">
        <Panel title="This container">
          <dl className="divide-y divide-slate-100">
            <Row
              k="Memory in use"
              v={bytes(proc.container_memory_bytes ?? proc.rss_bytes)}
            />
            <Row
              k="Memory limit"
              v={
                proc.container_memory_limit_bytes
                  ? bytes(proc.container_memory_limit_bytes)
                  : "no limit set"
              }
            />
            <Row
              k="Disk"
              v={
                proc.disk
                  ? `${bytes(proc.disk.free_bytes)} free · ${proc.disk.used_percent}% used`
                  : "unavailable"
              }
            />
            <Row k="Python" v={proc.python} />
            <Row
              k="Prompt engine"
              v={proc.llm_provider === "none" ? "deterministic rules" : proc.llm_provider}
            />
          </dl>
        </Panel>

        <Panel title="Database">
          <dl className="divide-y divide-slate-100">
            <Row k="File" v={bytes(database.db_bytes)} />
            <Row k="Write-ahead log" v={bytes(database.wal_bytes)} />
            {Object.entries(database.rows).map(([table, n]) => (
              <Row key={table} k={table.split("_").join(" ")} v={n.toLocaleString()} />
            ))}
          </dl>
        </Panel>
      </section>

      {/* ------------------------------------------------------------ quota */}
      {data.quota_pressure.length > 0 && (
        <section className="mb-8">
          <Panel title="Hourly quota, last 60 minutes">
            <ul className="divide-y divide-slate-100">
              {data.quota_pressure.map((q) => (
                <li key={q.key_hash} className="flex items-center gap-3 px-4 py-2.5">
                  <code className="shrink-0 font-mono text-xs text-slate-500">
                    {q.key_hash}
                  </code>
                  <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                    <span
                      className={`block h-full rounded-full ${
                        q.used >= q.limit ? "bg-red-500" : "bg-brand"
                      }`}
                      style={{ width: `${Math.min(100, (q.used / q.limit) * 100)}%` }}
                    />
                  </span>
                  <span className="shrink-0 font-mono text-xs tabular-nums text-slate-600">
                    {q.used}/{q.limit}
                  </span>
                </li>
              ))}
            </ul>
            <p className="border-t border-slate-100 px-4 py-2.5 text-xs leading-relaxed text-slate-500">
              Keys are stored hashed, so this shows how hard the limit is being
              pushed without naming who is pushing it.
            </p>
          </Panel>
        </section>
      )}

      {/* ------------------------------------------------------------ users */}
      <section className="mb-8">
        <Panel title={`Accounts${users ? ` (${users.length})` : ""}`}>
          {!users ? (
            <Quiet>Loading.</Quiet>
          ) : users.length === 0 ? (
            <Quiet>No accounts yet.</Quiet>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-4 py-2 font-bold">Account</th>
                    <th className="px-4 py-2 text-right font-bold">Audits</th>
                    <th className="px-4 py-2 text-right font-bold">Failed</th>
                    <th className="px-4 py-2 text-right font-bold">Sessions</th>
                    <th className="px-4 py-2 font-bold">Last audit</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td className="max-w-0 px-4 py-2.5">
                        <span className="flex items-center gap-2">
                          <span className="truncate font-medium text-slate-800">
                            {u.email}
                          </span>
                          {u.is_admin ? (
                            <span className="shrink-0 rounded-full bg-brand/10 px-2 py-0.5 text-[11px] font-semibold text-brand">
                              admin
                            </span>
                          ) : null}
                        </span>
                        <span className="block truncate text-xs text-slate-400">
                          joined {new Date(u.created_at).toLocaleDateString()}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-slate-700">
                        {u.audits}
                      </td>
                      <td
                        className={`px-4 py-2.5 text-right tabular-nums ${
                          u.failed ? "font-semibold text-red-600" : "text-slate-400"
                        }`}
                      >
                        {u.failed}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-slate-500">
                        {u.active_sessions}
                      </td>
                      <td className="px-4 py-2.5 text-slate-500">
                        {u.last_audit_at
                          ? new Date(u.last_audit_at).toLocaleDateString()
                          : "never"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </section>

      {/* ----------------------------------------------------------- audits */}
      <section className="mb-8">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xs font-bold uppercase tracking-wide text-slate-500">
            All audits
          </h2>
          <div className="inline-flex rounded-lg border border-slate-300 bg-white p-0.5">
            {[
              ["", "All"],
              ["running", "Running"],
              ["failed", "Failed"],
              ["complete", "Complete"],
            ].map(([value, label]) => (
              <button
                key={value || "all"}
                onClick={() => setFilter(value)}
                aria-pressed={filter === value}
                className={`min-h-11 rounded-md px-3 text-sm font-medium transition ${
                  filter === value
                    ? "bg-brand text-white"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <Panel>
          {!audits ? (
            <Quiet>Loading.</Quiet>
          ) : audits.length === 0 ? (
            <Quiet>Nothing matches that filter.</Quiet>
          ) : (
            <ul className="divide-y divide-slate-100">
              {audits.map((r) => (
                <li key={r.id}>
                  <Link
                    to={`/a/${r.id}`}
                    className="flex items-center gap-3 px-4 py-2.5 transition hover:bg-slate-50"
                  >
                    <StatusDot status={r.status} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-slate-800">
                        {hostOf(r.target_url)}
                      </span>
                      <span className="block truncate text-xs text-slate-400">
                        {r.owner_email || "no account"}
                        {r.error_code ? ` · ${r.error_code}` : ""}
                        {r.duration_ms ? ` · ${(r.duration_ms / 1000).toFixed(1)}s` : ""}
                      </span>
                    </span>
                    <span className="shrink-0 text-right">
                      <span className="block font-display text-sm font-extrabold tabular-nums text-slate-700">
                        {r.health_score ?? "–"}
                      </span>
                      <span className="block text-xs text-slate-400">
                        {new Date(r.created_at).toLocaleDateString(undefined, {
                          day: "numeric",
                          month: "short",
                        })}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </section>

      {/* --------------------------------------------------- what is absent */}
      <section className="rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-4">
        <h2 className="text-xs font-bold uppercase tracking-wide text-slate-500">
          What this page does not measure
        </h2>
        <ul className="mt-2 space-y-1.5 text-sm leading-relaxed text-slate-600">
          <li>
            <strong className="font-semibold">Host CPU and memory.</strong> This
            container can read the whole VPS&rsquo;s figures, but they describe
            four other applications as well as this one.
          </li>
          <li>
            <strong className="font-semibold">Request latency percentiles.</strong>{" "}
            Nothing records per-request timings, so there is no honest number to
            put here. The slowest single call since boot was {requests.slowest_ms}
            ms{requests.slowest_path ? ` on ${requests.slowest_path}` : ""}.
          </li>
          <li>
            <strong className="font-semibold">Anything before this deploy.</strong>{" "}
            Request counters live in memory and reset when the process restarts.
            The audit figures come from the database and do not.
          </li>
        </ul>
      </section>
    </Page>
  );
}

/* ------------------------------------------------------------------ pieces */

/**
 * What an operator should act on, in the order they should act on it.
 *
 * Built here rather than server-side so the thresholds sit next to the words
 * that explain them; a number without the sentence saying what to do about it
 * is what makes monitoring pages ignorable.
 */
function buildAttention(stuck, proc, a, runner) {
  const out = [];
  if (stuck.length) {
    out.push({
      level: "critical",
      title: `${stuck.length} audit${stuck.length === 1 ? "" : "s"} stuck`,
      detail:
        "In flight for over twenty minutes. A restart closes these; one appearing while the server is up has lost its task.",
    });
  }
  if (proc.disk && proc.disk.used_percent >= 90) {
    out.push({
      level: "critical",
      title: `Disk ${proc.disk.used_percent}% full`,
      detail: `${bytes(proc.disk.free_bytes)} left. SQLite starts failing writes before a disk is completely full.`,
    });
  }
  if (a.success_rate !== null && a.success_rate < 90) {
    out.push({
      level: "warn",
      title: `${a.success_rate}% of runs completed`,
      detail: "Check which codes are firing below before assuming it is the sites.",
    });
  }
  if (runner.slots_free === 0) {
    out.push({
      level: "warn",
      title: "Every audit slot is busy",
      detail: "New runs are waiting. Normal under load on one core.",
    });
  }
  return out;
}

function Freshness({ at, live, onToggle, stale }) {
  const [, tick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);
  const ago = at ? Math.round((Date.now() - at.getTime()) / 1000) : null;

  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-2">
      <span
        className={`h-2 w-2 shrink-0 rounded-full ${
          stale ? "bg-red-500" : live ? "animate-ring bg-emerald-500" : "bg-slate-300"
        }`}
        aria-hidden
      />
      <span className="text-sm text-slate-600" aria-live="polite">
        {stale
          ? "Last refresh failed"
          : ago === null
            ? "Loading"
            : ago < 2
              ? "Updated just now"
              : `Updated ${ago}s ago`}
      </span>
      <button
        onClick={onToggle}
        className="min-h-11 rounded-lg px-2 text-sm font-medium text-brand transition hover:bg-slate-50"
      >
        {live ? "Pause" : "Resume"}
      </button>
    </div>
  );
}

function Tile({ label, value, note, tone }) {
  const accent =
    tone === "busy"
      ? "text-amber-600"
      : tone === "warn"
        ? "text-red-600"
        : "text-slate-900";
  return (
    <div className="bg-white px-5 py-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className={`mt-1.5 font-display text-3xl font-extrabold tabular-nums ${accent}`}>
        {value}
      </p>
      <p className="mt-1 text-xs leading-snug text-slate-500">{note}</p>
    </div>
  );
}

/**
 * Volume per day, with the failed share inside each bar rather than beside
 * it - the question is what proportion of that day went wrong, and two
 * separate bars make that a subtraction the reader has to do.
 *
 * Drawn rather than charted: at most thirty values does not justify shipping
 * a charting library to every visitor.
 */
function DailyBars({ daily }) {
  if (!daily.length) return <Quiet>No audits in this window.</Quiet>;
  const peak = Math.max(...daily.map((d) => d.total), 1);

  return (
    <div className="px-4 py-4">
      <div className="flex h-32 items-end gap-1">
        {daily.map((d) => (
          <div
            key={d.day}
            className="flex-1"
            style={{ height: `${Math.max(4, (d.total / peak) * 100)}%` }}
            title={`${d.day}: ${d.total} run${d.total === 1 ? "" : "s"}, ${d.failed} failed`}
          >
            <div className="flex h-full w-full flex-col justify-end overflow-hidden rounded-t bg-brand/70">
              <div
                className="w-full bg-red-500"
                style={{ height: `${d.total ? (d.failed / d.total) * 100 : 0}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-2 flex items-center justify-between gap-3 text-xs text-slate-500">
        <span>{daily[0].day}</span>
        <span className="flex items-center gap-3">
          <Legend className="bg-brand/70">run</Legend>
          <Legend className="bg-red-500">failed</Legend>
        </span>
        <span>{daily[daily.length - 1].day}</span>
      </div>
    </div>
  );
}

function Legend({ className, children }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`h-2 w-2 rounded-sm ${className}`} aria-hidden />
      {children}
    </span>
  );
}

function StatusDot({ status }) {
  const tone =
    {
      complete: "bg-emerald-500",
      failed: "bg-red-500",
      running: "bg-brand animate-ring",
      queued: "bg-slate-300",
    }[status] || "bg-slate-300";
  return (
    <span className="flex shrink-0 items-center">
      <span className={`h-2 w-2 rounded-full ${tone}`} aria-hidden />
      <span className="sr-only">{status}</span>
    </span>
  );
}

function Panel({ title, children }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      {title && (
        <p className="border-b border-slate-100 px-4 py-2.5 text-xs font-bold uppercase tracking-wide text-slate-500">
          {title}
        </p>
      )}
      {children}
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="flex items-center justify-between gap-4 px-4 py-2">
      <dt className="text-sm text-slate-600">{k}</dt>
      <dd className="font-mono text-xs tabular-nums text-slate-800">{v}</dd>
    </div>
  );
}

function Quiet({ children }) {
  return <p className="px-4 py-8 text-center text-sm text-slate-500">{children}</p>;
}

function Page({ children }) {
  return <div className="mx-auto max-w-6xl px-5 py-8 lg:py-10">{children}</div>;
}

/* -------------------------------------------------------------- formatting */

function bytes(n) {
  if (n === null || n === undefined) return "unavailable";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = n;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value < 10 && i > 0 ? value.toFixed(1) : Math.round(value)} ${units[i]}`;
}

function formatDuration(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ${m % 60}m`;
  return `${Math.floor(h / 24)}d ${h % 24}h`;
}

function hostOf(url) {
  return (url || "").split("://").pop().split("/")[0] || url;
}
