/**
 * The building blocks a report is made of, shared by the owner's view and the
 * public one.
 *
 * The governing rule here is that a passing check and a failing one must not
 * look the same. Every finding used to be a white card with a coloured left
 * edge, so "Navigation is stable" carried the same visual weight as
 * "submissions are being lost" - and a reader scanning the page had to read
 * every card to find the one that mattered. Failures are now loud and
 * everything that passed is quiet, which is what makes the page scannable at
 * a glance rather than only after reading it.
 */

const SEVERITY = {
  critical: {
    card: "border-red-200 bg-red-50/60",
    bar: "bg-red-500",
    chip: "bg-red-600 text-white",
    dot: "bg-red-500",
    label: "Critical",
  },
  warning: {
    card: "border-amber-200 bg-amber-50/60",
    bar: "bg-amber-500",
    chip: "bg-amber-500 text-white",
    dot: "bg-amber-500",
    label: "Warning",
  },
  ok: {
    card: "border-slate-200 bg-white",
    bar: "bg-emerald-500",
    chip: "bg-emerald-100 text-emerald-700",
    dot: "bg-emerald-500",
    label: "Passing",
  },
  info: {
    card: "border-slate-200 bg-white",
    bar: "bg-slate-400",
    chip: "bg-slate-100 text-slate-600",
    dot: "bg-slate-400",
    label: "Info",
  },
};

// Keyed by the SRS grade values (FR-4.1).
const GRADE_COLOR = {
  not_assessed: "text-slate-400",
  verified_healthy: "text-emerald-600",
  minor_issues: "text-emerald-600",
  needs_attention: "text-amber-600",
  critical: "text-red-600",
};

export function ScoreDial({ score, grade, label, letter }) {
  const unscored = score == null;
  const pct = unscored ? 0 : Math.max(0, Math.min(100, score));
  const hue = unscored
    ? "#cbd5e1"
    : pct >= 80
      ? "#059669"
      : pct >= 55
        ? "#d97706"
        : "#dc2626";
  return (
    <div className="flex items-center gap-5">
      <div
        className="relative grid h-28 w-28 shrink-0 place-items-center rounded-full"
        style={{ background: `conic-gradient(${hue} ${pct * 3.6}deg, #e5e7eb 0deg)` }}
      >
        <div className="grid h-[86px] w-[86px] place-items-center rounded-full bg-white">
          <span
            className={`font-display font-extrabold tabular-nums ${
              unscored ? "text-lg text-slate-400" : "text-3xl text-slate-900"
            }`}
          >
            {unscored ? "n/a" : score}
          </span>
        </div>
      </div>
      <div className="min-w-0">
        <div
          className={`font-display text-4xl font-extrabold leading-none ${
            GRADE_COLOR[grade] || "text-slate-500"
          }`}
        >
          {letter || "?"}
        </div>
        <div className="mt-1.5 font-medium text-slate-700">{label || ""}</div>
        <div className="text-xs text-slate-400">Site Health Score</div>
      </div>
    </div>
  );
}

export function Breakdown({ breakdown }) {
  if (!breakdown) return null;
  const rows = [
    ["form", "Forms"],
    ["router", "Navigation & console"],
    ["assets", "Assets"],
    ["geo", "Reachability"],
    ["a11y", "Accessibility"],
    ["perf", "Speed"],
    ["mobile", "Mobile layout"],
  ];
  return (
    <div className="space-y-3">
      {rows.map(([key, name]) => {
        const b = breakdown[key];
        if (!b) return null;

        if (b.measured === false) {
          return (
            <p key={key} className="text-xs leading-relaxed text-slate-400">
              <span className="font-medium text-slate-500">{name}</span> — not
              measured. {b.reason} Its {b.spec_weight}% is redistributed across
              the categories above.
            </p>
          );
        }

        const color =
          b.score >= 80 ? "bg-emerald-500" : b.score >= 55 ? "bg-amber-500" : "bg-red-500";
        return (
          <div key={key}>
            <div className="mb-1 flex items-baseline justify-between gap-3 text-xs">
              <span className="font-medium text-slate-700">
                {name}{" "}
                <span className="text-slate-400">
                  ({b.weight}%{b.in_spec === false ? ", added" : ""})
                </span>
              </span>
              <span className="font-display text-sm font-extrabold tabular-nums text-slate-700">
                {b.score}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
              <div className={`h-full rounded-full ${color}`} style={{ width: `${b.score}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function FindingCard({ severity, title, children, badge }) {
  const s = SEVERITY[severity] || SEVERITY.info;
  return (
    <div className={`flex gap-3.5 rounded-xl border p-4 ${s.card}`}>
      <span className={`w-1 shrink-0 rounded-full ${s.bar}`} aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <h4 className="font-semibold text-slate-900">{title}</h4>
          <span
            className={`ml-auto shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${s.chip}`}
          >
            {badge || s.label}
          </span>
        </div>
        <div className="mt-1.5 text-sm leading-relaxed text-slate-700">{children}</div>
      </div>
    </div>
  );
}

/**
 * The checks that passed, as one line each.
 *
 * Anything that is fine still has to be listed - a report that only shows
 * problems cannot be told apart from a report that did not run. It does not
 * need a card each, though, and giving it one is what buried the failures.
 */
export function PassedStrip({ items }) {
  if (!items?.length) return null;
  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      <p className="border-b border-slate-100 px-4 py-2.5 text-xs font-bold uppercase tracking-wide text-slate-500">
        {items.length} check{items.length === 1 ? "" : "s"} passed
      </p>
      <ul className="divide-y divide-slate-50">
        {items.map((item) => (
          <li key={item.title} className="flex items-start gap-2.5 px-4 py-2.5">
            <span
              className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500"
              aria-hidden
            />
            <span className="min-w-0">
              <span className="text-sm font-medium text-slate-800">
                {item.title}
              </span>
              {item.detail && (
                <span className="block text-xs leading-relaxed text-slate-500">
                  {item.detail}
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Observed lines - request lines, selectors, paths - set as what they are. */
export function Evidence({ lines }) {
  if (!lines?.length) return null;
  return (
    <div className="mt-2.5 overflow-x-auto rounded-lg bg-slate-900 px-3 py-2.5 font-mono text-[11px] leading-relaxed text-slate-300">
      {lines.map((line, i) => (
        <div key={i} className="whitespace-pre">
          {line}
        </div>
      ))}
    </div>
  );
}

const VERDICT_TITLE = {
  silent_failure: "Silent failure — visitors think this form works",
  no_submission: "Form is not connected to anything",
  js_crash: "JavaScript crashed on submit",
  endpoint_error: "The server rejected the submission",
  blocked_by_protection: "Blocked by bot protection, so not tested",
  error_shown: "The form showed an error to the visitor",
  no_feedback: "Submission works but gives no confirmation",
  no_submit_control: "No submit button found",
  submit_click_failed: "Submit button could not be clicked",
  probe_error: "This form could not be tested",
  skipped: "Skipped by design",
  pass: "Form is working",
};

export function FormFinding({ form }) {
  const title = VERDICT_TITLE[form.verdict] || `Form result: ${form.verdict}`;
  const name =
    form.heading || form.submit_text || `Form ${(form.form_index ?? 0) + 1}`;
  const requests = Array.isArray(form.submission_requests)
    ? form.submission_requests
    : [];

  return (
    <FindingCard
      severity={form.severity || "info"}
      title={title}
      badge={form.verdict}
    >
      <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-400">
        {name}
      </p>
      <p>{form.explanation}</p>
      <Evidence
        lines={
          requests.length
            ? requests.map(
                (r) => `${r.method}  ${r.status ?? r.failure ?? "pending"}  ${r.url}`,
              )
            : form.verdict === "silent_failure" || form.verdict === "no_submission"
              ? ["submit  ->  no network request was made"]
              : null
        }
      />
    </FindingCard>
  );
}
