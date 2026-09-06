const SEVERITY = {
  critical: { ring: "border-red-300", chip: "bg-red-100 text-red-800", dot: "bg-red-500", label: "Critical" },
  warning: { ring: "border-amber-300", chip: "bg-amber-100 text-amber-800", dot: "bg-amber-500", label: "Warning" },
  ok: { ring: "border-emerald-300", chip: "bg-emerald-100 text-emerald-800", dot: "bg-emerald-500", label: "Passing" },
  info: { ring: "border-slate-300", chip: "bg-slate-100 text-slate-700", dot: "bg-slate-400", label: "Info" },
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
    : pct >= 80 ? "#059669" : pct >= 55 ? "#d97706" : "#dc2626";
  return (
    <div className="flex items-center gap-5">
      <div
        className="relative grid h-28 w-28 place-items-center rounded-full"
        style={{ background: `conic-gradient(${hue} ${pct * 3.6}deg, #e5e7eb 0deg)` }}
      >
        <div className="grid h-[86px] w-[86px] place-items-center rounded-full bg-white">
          <span
            className={`font-bold tabular-nums ${
              unscored ? "text-lg text-slate-400" : "text-3xl"
            }`}
          >
            {unscored ? "n/a" : score}
          </span>
        </div>
      </div>
      <div>
        <div className={`text-4xl font-black leading-none ${GRADE_COLOR[grade] || "text-slate-500"}`}>
          {letter || "?"}
        </div>
        <div className="mt-1 text-sm font-medium text-slate-600">{label || ""}</div>
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
    <div className="space-y-2.5">
      {rows.map(([key, name]) => {
        const b = breakdown[key];
        if (!b) return null;
        if (b.measured === false) {
          return (
            <div key={key} className="text-xs text-slate-400">
              <span className="font-medium">{name}</span> - not measured.{" "}
              {b.reason} Its {b.spec_weight}% is redistributed across the
              categories above.
            </div>
          );
        }
        const color = b.score >= 80 ? "bg-emerald-500" : b.score >= 55 ? "bg-amber-500" : "bg-red-500";
        return (
          <div key={key}>
            <div className="mb-1 flex justify-between text-xs">
              <span className="font-medium text-slate-700">
                {name}{" "}
                <span className="text-slate-400">
                  ({b.weight}%{b.in_spec === false ? ", added" : ""})
                </span>
              </span>
              <span className="font-semibold tabular-nums text-slate-600">{b.score}</span>
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
    <div className={`rounded-xl border-l-4 bg-white p-4 shadow-sm ${s.ring} border-y border-r border-y-slate-200 border-r-slate-200`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${s.dot}`} />
        <h4 className="font-semibold text-slate-900">{title}</h4>
        <span className={`ml-auto rounded-full px-2 py-0.5 text-[11px] font-semibold ${s.chip}`}>
          {badge || s.label}
        </span>
      </div>
      <div className="mt-2 text-sm leading-relaxed text-slate-600">{children}</div>
    </div>
  );
}

const VERDICT_TITLE = {
  silent_failure: "Silent failure - visitors think this form works",
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
  const name = form.heading || form.submit_text || `Form ${(form.form_index ?? 0) + 1}`;
  return (
    <FindingCard severity={form.severity || "info"} title={title} badge={form.verdict}>
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">{name}</p>
      <p>{form.explanation}</p>
      {Array.isArray(form.submission_requests) && form.submission_requests.length > 0 && (
        <ul className="mt-2 space-y-1 font-mono text-xs text-slate-500">
          {form.submission_requests.map((r, i) => (
            <li key={i} className="truncate">
              {r.method} {r.status ?? r.failure ?? "pending"} - {r.url}
            </li>
          ))}
        </ul>
      )}
    </FindingCard>
  );
}
