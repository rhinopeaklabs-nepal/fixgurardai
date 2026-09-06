import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";

const VERDICT = {
  improved: {
    chip: "bg-emerald-100 text-emerald-800",
    ring: "border-emerald-300",
    title: "This site got better",
  },
  regressed: {
    chip: "bg-red-100 text-red-800",
    ring: "border-red-300",
    title: "This site got worse",
  },
  changed: {
    chip: "bg-amber-100 text-amber-800",
    ring: "border-amber-300",
    title: "Same score, different problems",
  },
  unchanged: {
    chip: "bg-slate-100 text-slate-700",
    ring: "border-slate-300",
    title: "Nothing changed",
  },
  unknown: {
    chip: "bg-slate-100 text-slate-700",
    ring: "border-slate-300",
    title: "Not comparable",
  },
};

const SEV = {
  critical: "bg-red-100 text-red-800",
  serious: "bg-orange-100 text-orange-800",
  warning: "bg-amber-100 text-amber-800",
  moderate: "bg-slate-100 text-slate-700",
  minor: "bg-slate-100 text-slate-600",
};

export default function Compare() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setError(null);
    api
      .compare(id, params.get("baseline"))
      .then(setData)
      .catch((e) => setError(e.message));
  }, [id, params]);

  if (error) {
    return (
      <Wrap id={id}>
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <p className="text-slate-700">{error}</p>
          <p className="mt-2 text-sm text-slate-500">
            Comparisons need two completed audits of the same address. Apply a
            fix, run the audit again, and this page will show what changed.
          </p>
        </div>
      </Wrap>
    );
  }
  if (!data) {
    return (
      <Wrap id={id}>
        <div className="h-40 animate-pulse rounded-2xl bg-slate-200" />
      </Wrap>
    );
  }

  const v = VERDICT[data.verdict] || VERDICT.unknown;
  const up = (data.score_delta ?? 0) > 0;

  return (
    <Wrap id={id}>
      <header className="mb-6">
        <h1 className="text-2xl font-black tracking-tight text-slate-900">
          What changed
        </h1>
        <p className="break-all text-sm text-slate-500">{data.target_url}</p>
      </header>

      <div className={`rounded-2xl border-l-4 border-y border-r border-y-slate-200 border-r-slate-200 bg-white p-6 ${v.ring}`}>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-bold text-slate-900">{v.title}</h2>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${v.chip}`}>
            {data.verdict}
          </span>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-4">
          <Score label="Before" score={data.before.score} at={data.before.at} />
          <span
            className={`text-2xl font-black ${up ? "text-emerald-600" : data.score_delta < 0 ? "text-red-600" : "text-slate-400"}`}
            aria-hidden="true"
          >
            &rarr;
          </span>
          <Score label="After" score={data.after.score} at={data.after.at} big />
          {data.score_delta != null && data.score_delta !== 0 && (
            <span
              className={`rounded-full px-3 py-1 text-lg font-black tabular-nums ${
                up ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
              }`}
            >
              {data.score_delta > 0 ? "+" : ""}
              {data.score_delta}
            </span>
          )}
        </div>

        <p className="mt-4 leading-relaxed text-slate-700">{data.headline}</p>
      </div>

      <Section title="By category">
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          {data.categories.map((c) => (
            <div
              key={c.category}
              className="flex items-center gap-3 border-b border-slate-100 px-4 py-2.5 last:border-0"
            >
              <span className="flex-1 text-sm text-slate-700">{c.label}</span>
              <span className="w-10 text-right text-sm tabular-nums text-slate-400">
                {c.before ?? "--"}
              </span>
              <span className="text-slate-300">&rarr;</span>
              <span className="w-10 text-right text-sm font-semibold tabular-nums text-slate-700">
                {c.after ?? "--"}
              </span>
              <span
                className={`w-14 text-right text-sm font-semibold tabular-nums ${
                  !c.delta
                    ? "text-slate-300"
                    : c.delta > 0
                      ? "text-emerald-600"
                      : "text-red-600"
                }`}
              >
                {c.delta ? (c.delta > 0 ? `+${c.delta}` : c.delta) : "-"}
              </span>
            </div>
          ))}
        </div>
      </Section>

      <FindingList
        title={`Fixed (${data.counts.resolved})`}
        findings={data.resolved}
        tone="good"
        empty="No issues were resolved between these two runs."
      />
      <FindingList
        title={`New problems (${data.counts.introduced})`}
        findings={data.introduced}
        tone="bad"
        empty="No new problems appeared. "
      />
      <FindingList
        title={`Still present (${data.counts.remaining})`}
        findings={data.remaining}
        tone="neutral"
        empty="Nothing carried over."
      />
    </Wrap>
  );
}

function Score({ label, score, at, big }) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </div>
      <div className={`font-black tabular-nums ${big ? "text-4xl" : "text-3xl"} text-slate-900`}>
        {score ?? "--"}
      </div>
      {at && (
        <div className="text-[11px] text-slate-400">
          {new Date(at).toLocaleString()}
        </div>
      )}
    </div>
  );
}

function FindingList({ title, findings, tone, empty }) {
  const dot =
    tone === "good" ? "bg-emerald-500" : tone === "bad" ? "bg-red-500" : "bg-slate-300";
  return (
    <Section title={title}>
      {findings.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-5 text-center text-sm text-slate-400">
          {empty}
        </p>
      ) : (
        <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white">
          {findings.map((f) => (
            <li key={f.key} className="flex items-start gap-3 px-4 py-3">
              <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dot}`} />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium text-slate-800">
                  {f.label}
                </span>
                {f.detail && (
                  <span className="block truncate text-xs text-slate-500">
                    {f.detail}
                  </span>
                )}
              </span>
              <span
                className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                  SEV[f.severity] || SEV.minor
                }`}
              >
                {f.severity}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function Section({ title, children }) {
  return (
    <section className="mt-8">
      <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Wrap({ id, children }) {
  return (
    <div className="mx-auto max-w-3xl px-5 py-10">
      <Link
        to={`/a/${id}`}
        className="mb-6 inline-block text-sm font-medium text-brand hover:underline"
      >
        &larr; Back to the report
      </Link>
      {children}
    </div>
  );
}
