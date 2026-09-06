import { Link, useSearchParams } from "react-router-dom";

/**
 * The public landing page.
 *
 * The hero is the report, not an illustration of one. Everything on this page
 * that looks like FixGuard output is shaped like real FixGuard output - the
 * same severities, the same evidence lines, the same wording - because the
 * product's whole claim is that it tells you what actually happened, and a
 * landing page full of invented screenshots would undercut that on the first
 * screen.
 */
export default function Landing() {
  // A visitor sent here from the marketing page arrives with their address in
  // the query string. Signing up has to carry it through, or they type it a
  // second time and the handoff was for nothing.
  const [params] = useSearchParams();
  const handedOver = (params.get("url") || "").trim();
  const next = handedOver ? `/?url=${encodeURIComponent(handedOver)}` : "/";

  return (
    <div className="min-h-screen bg-white">
      <Header next={next} />
      <Hero next={next} handedOver={handedOver} />
      <Failures />
      <HowItWorks />
      <Deliverables />
      <Limits />
      <FinalCta next={next} />
      <Footer />
    </div>
  );
}

/* ------------------------------------------------------------------ header */

function Header({ next = "/" }) {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-3.5">
        <span className="font-display text-lg font-extrabold tracking-tight text-brand">
          FixGuard AI
        </span>
        <nav className="ml-auto flex items-center gap-1">
          <Link
            to="/signin"
            state={{ from: next }}
            className="rounded-lg px-3.5 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
          >
            Sign in
          </Link>
          <Link
            to="/signin"
            state={{ mode: "signup", from: next }}
            className="rounded-lg bg-brand px-3.5 py-2 text-sm font-semibold text-white transition hover:bg-brand-dark"
          >
            Create account
          </Link>
        </nav>
      </div>
    </header>
  );
}

/* -------------------------------------------------------------------- hero */

function Hero({ next = "/", handedOver = "" }) {
  return (
    <section className="relative overflow-hidden border-b border-slate-200">
      {/* A faint measurement grid, because this is an instrument. Masked so it
          fades out rather than stopping at a hard edge. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "linear-gradient(to right, #e2e8f0 1px, transparent 1px), linear-gradient(to bottom, #e2e8f0 1px, transparent 1px)",
          backgroundSize: "56px 56px",
          maskImage:
            "radial-gradient(ellipse 80% 60% at 30% 40%, black, transparent)",
          WebkitMaskImage:
            "radial-gradient(ellipse 80% 60% at 30% 40%, black, transparent)",
        }}
      />

      <div className="relative mx-auto grid max-w-6xl gap-14 px-6 py-16 lg:grid-cols-[1.05fr_1fr] lg:items-center lg:py-24">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Pre-flight QA for AI Builder sites
          </p>

          <h1 className="mt-6 font-display text-[2.6rem] font-extrabold leading-[1.05] tracking-tight text-slate-900 sm:text-6xl">
            Your form says{" "}
            <span className="whitespace-nowrap text-emerald-600">
              &ldquo;Thanks!&rdquo;
            </span>
            <br />
            It sent nothing.
          </h1>

          <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-600">
            That is the failure nobody reports to you. The visitor saw a
            success message and left. FixGuard opens your site in a real
            browser, fills your forms in, presses submit, and watches the
            network to see whether anything actually left the page.
          </p>

          {/* Say the address back. Somebody handed over from the marketing
              page has already typed it once and needs to see it survived,
              otherwise the next screen asking for it again reads as a bug. */}
          {handedOver && (
            <p className="mt-6 inline-block rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
              Ready to audit{" "}
              <span className="font-mono font-medium text-slate-900">
                {handedOver.replace(/^https?:\/\//, "")}
              </span>
            </p>
          )}

          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link
              to="/signin"
              state={{ mode: "signup", from: next }}
              className="rounded-xl bg-brand px-6 py-3.5 font-semibold text-white shadow-sm transition hover:bg-brand-dark"
            >
              {handedOver ? "Create account and run it" : "Audit my site"}
            </Link>
            <Link
              to="/signin"
              className="rounded-xl border border-slate-300 px-6 py-3.5 font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
            >
              Sign in
            </Link>
          </div>

          <p className="mt-5 text-sm text-slate-500">
            One URL. Around 30 seconds. No snippet to install, nothing to add
            to your site.
          </p>
        </div>

        <ReportPreview />
      </div>
    </section>
  );
}

/** The artefact the product actually produces, at rest and readable. */
function ReportPreview() {
  return (
    <div className="relative">
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl shadow-slate-900/5">
        <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
          <ScoreDial value={49} />
          <div className="min-w-0">
            <p className="truncate font-semibold text-slate-900">
              yourbakery.com
            </p>
            <p className="text-sm text-red-600">
              Critical &middot; 1 blocking issue
            </p>
          </div>
          <span className="ml-auto shrink-0 rounded-full bg-slate-100 px-2.5 py-1 font-mono text-[11px] text-slate-500">
            18.4s
          </span>
        </div>

        {/* Extra bottom padding on wider screens is not decoration: the
            score-change badge below hangs over this corner, and without the
            clearance it sits on top of the last finding's evidence line. */}
        <div className="space-y-2.5 p-4 sm:pb-14">
          <Finding
            severity="critical"
            title="Contact form &mdash; submissions are being lost"
            body="The form showed its success message, but no network request left the page."
            evidence={[
              'form#contact  submit  ->  no request made',
              "success banner shown after 120ms",
            ]}
          />
          <Finding
            severity="warning"
            title="2 links lead nowhere"
            body="Visitors clicking these reach a dead page."
            evidence={["GET /pricing   404", "GET /about-us  404"]}
          />
          <Finding
            severity="info"
            title="24 other companies receive a request"
            body="Nine are advertising or analytics services."
            evidence={["flagcdn.com  220 requests"]}
          />
        </div>
      </div>

      {/* Deliberately not a floating decoration: it names the one number a
          reader will otherwise have to hunt for. */}
      <div className="absolute -bottom-5 -left-5 hidden rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-lg sm:block">
        <p className="font-display text-2xl font-extrabold leading-none text-emerald-600">
          49 &rarr; 97
        </p>
        <p className="mt-1 text-xs text-slate-500">after the fixes, re-checked</p>
      </div>
    </div>
  );
}

function ScoreDial({ value }) {
  const r = 22;
  const c = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 56 56" className="h-14 w-14 shrink-0" aria-hidden>
      <circle cx="28" cy="28" r={r} fill="none" stroke="#e2e8f0" strokeWidth="6" />
      <circle
        cx="28"
        cy="28"
        r={r}
        fill="none"
        stroke="#dc2626"
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={`${(value / 100) * c} ${c}`}
        transform="rotate(-90 28 28)"
      />
      <text
        x="28"
        y="33"
        textAnchor="middle"
        className="fill-slate-900 font-bold"
        style={{ fontSize: "16px" }}
      >
        {value}
      </text>
    </svg>
  );
}

const SEVERITY = {
  critical: { bar: "bg-red-500", chip: "bg-red-100 text-red-700", label: "critical" },
  warning: { bar: "bg-amber-500", chip: "bg-amber-100 text-amber-700", label: "warning" },
  info: { bar: "bg-slate-400", chip: "bg-slate-100 text-slate-600", label: "info" },
};

function Finding({ severity, title, body, evidence }) {
  const s = SEVERITY[severity];
  return (
    <div className="flex gap-3 rounded-xl bg-slate-50 p-3.5">
      <span className={`w-1 shrink-0 rounded-full ${s.bar}`} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-2">
          <span
            className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${s.chip}`}
          >
            {s.label}
          </span>
          <p className="text-sm font-semibold text-slate-900">{title}</p>
        </div>
        <p className="mt-1 text-sm leading-relaxed text-slate-600">{body}</p>
        {evidence?.length > 0 && (
          <div className="mt-2 overflow-x-auto rounded-lg bg-white px-2.5 py-2 font-mono text-[11px] leading-relaxed text-slate-500">
            {evidence.map((line) => (
              <div key={line} className="whitespace-pre">
                {line}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- failures */

const FAILURES = [
  {
    kicker: "Forms",
    title: "The success message that means nothing",
    body: "A form can show a confirmation and send no request at all, or send one that comes back 500. FixGuard fills it in with clearly-labelled test data, submits it, and reports which of those three actually happened.",
    evidence: ["POST /contact", "-> no request made", "banner: “Thanks! We'll be in touch.”"],
  },
  {
    kicker: "Routes",
    title: "Links that lead nowhere",
    body: "Every internal link is followed, not just listed. Redirect loops, pages that return 200 while rendering “not found”, and routes that quietly 404 are all named with the path a visitor would have clicked.",
    evidence: ["GET /pricing        404", "GET /shop           200  “Page not found”", "GET /home  ->  /home  537x"],
  },
  {
    kicker: "Third parties",
    title: "Everyone your visitors reach",
    body: "Every host that receives a request when someone opens your page, grouped by what it is for. Not the scripts you added: the ones those scripts loaded too.",
    evidence: ["advertising    4 hosts   312 req", "analytics      5 hosts   140 req", "cdn            3 hosts   1019 req"],
  },
];

function Failures() {
  return (
    <section className="border-b border-slate-200 bg-slate-50">
      <div className="mx-auto max-w-6xl px-6 py-16 lg:py-20">
        <h2 className="max-w-2xl font-display text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
          Three things a page will not tell you about itself
        </h2>
        <p className="mt-4 max-w-2xl text-lg leading-relaxed text-slate-600">
          Every one of these looks fine to the person who built the site. All
          three are only visible from the outside, in a browser, watching what
          the page does rather than reading what it says.
        </p>

        <div className="mt-12 grid gap-5 lg:grid-cols-3">
          {FAILURES.map((f) => (
            <article
              key={f.title}
              className="flex flex-col rounded-2xl border border-slate-200 bg-white p-6"
            >
              <p className="text-xs font-bold uppercase tracking-wider text-brand">
                {f.kicker}
              </p>
              <h3 className="mt-3 font-display text-xl font-bold leading-snug text-slate-900">
                {f.title}
              </h3>
              <p className="mt-3 flex-1 leading-relaxed text-slate-600">
                {f.body}
              </p>
              <div className="mt-5 overflow-x-auto rounded-lg bg-slate-900 px-3 py-2.5 font-mono text-[11px] leading-relaxed text-slate-300">
                {f.evidence.map((line) => (
                  <div key={line} className="whitespace-pre">
                    {line}
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------- steps */

const STEPS = [
  {
    title: "Paste your address",
    body: "One URL. Choose whether to check just that page or let FixGuard find your other routes from your sitemap and your own links.",
  },
  {
    title: "It opens the site for real",
    body: "A real Chromium browser loads the page, watches the console and the network, submits your forms with test data, and follows your links. Nothing is installed on your site.",
  },
  {
    title: "You get evidence, not adjectives",
    body: "A score out of 100, every finding with the request or selector that produced it, and a PDF you can hand to whoever is going to fix it.",
  },
];

function HowItWorks() {
  return (
    <section className="border-b border-slate-200">
      <div className="mx-auto max-w-6xl px-6 py-16 lg:py-20">
        <div className="grid gap-12 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <h2 className="font-display text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
              How it works
            </h2>
            <p className="mt-4 max-w-md text-lg leading-relaxed text-slate-600">
              There is no snippet to add and no account to connect. FixGuard
              only needs the address a visitor would type.
            </p>
          </div>

          {/* Numbered because this genuinely is a sequence - the steps happen
              in this order and none of them makes sense out of it. */}
          <ol className="space-y-8">
            {STEPS.map((s, i) => (
              <li key={s.title} className="flex gap-5">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-slate-300 font-mono text-sm font-bold text-slate-500">
                  {i + 1}
                </span>
                <div>
                  <h3 className="font-display text-lg font-bold text-slate-900">
                    {s.title}
                  </h3>
                  <p className="mt-1.5 leading-relaxed text-slate-600">
                    {s.body}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------ deliverables */

function Deliverables() {
  return (
    <section className="border-b border-slate-200 bg-slate-900">
      <div className="mx-auto max-w-6xl px-6 py-16 lg:py-20">
        <h2 className="max-w-2xl font-display text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
          What you walk away with
        </h2>

        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {[
            [
              "A score you can argue with",
              "0 to 100, with the weight of every check shown. A run that could not measure anything says so instead of inventing a number.",
            ],
            [
              "A PDF certificate",
              "Every page that was audited, every finding, and the observation behind it. Made to be forwarded, not just read.",
            ],
            [
              "A shareable link",
              "A client-safe version of the report with the developer detail stripped out. It expires.",
            ],
            [
              "A before and after",
              "Re-run it once the fixes land and FixGuard compares the two runs: what was fixed, what is still there, what is new.",
            ],
          ].map(([title, body]) => (
            <div key={title} className="rounded-2xl bg-white/5 p-6 ring-1 ring-white/10">
              <h3 className="font-display text-lg font-bold text-white">
                {title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">
                {body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ limits */

const LIMITS = [
  [
    "It never asks for a password to your site",
    "To check pages behind a login, you sign in yourself and hand FixGuard the resulting session. A session is scoped, expiring and revocable. A password is none of those. Forms containing a password, card or ID field are never submitted.",
  ],
  [
    "It cannot tell you the email arrived",
    "FixGuard sees whether your form's request left the page and what came back. The mail your host then sends goes to you, not to FixGuard, so nothing here claims to have watched it land in an inbox.",
  ],
  [
    "It checks reachability from one region",
    "DNS, TLS and the response code are measured from where FixGuard runs. It will say so rather than implying it tested your site from everywhere.",
  ],
  [
    "It stores no cookie or token values",
    "If you hand it a session, the names of the cookies are recorded and the values are not. Sign-out links and anything that looks like it deletes data are never followed.",
  ],
];

function Limits() {
  return (
    <section className="border-b border-slate-200">
      <div className="mx-auto max-w-6xl px-6 py-16 lg:py-20">
        <div className="grid gap-12 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-brand">
              Worth knowing before you start
            </p>
            <h2 className="mt-3 font-display text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
              What FixGuard will not do
            </h2>
            <p className="mt-4 max-w-md leading-relaxed text-slate-600">
              A tool that reports what actually happened has to be equally
              plain about what it did not look at. These are the limits, in the
              same words the reports use.
            </p>
          </div>

          <dl className="divide-y divide-slate-200 border-y border-slate-200">
            {LIMITS.map(([title, body]) => (
              <div key={title} className="py-5">
                <dt className="font-display font-bold text-slate-900">
                  {title}
                </dt>
                <dd className="mt-1.5 leading-relaxed text-slate-600">{body}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}

/* --------------------------------------------------------------------- cta */

function FinalCta({ next = "/" }) {
  return (
    <section className="border-b border-slate-200 bg-slate-50">
      <div className="mx-auto max-w-3xl px-6 py-20 text-center">
        <h2 className="font-display text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
          Find out before your customers do
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-lg leading-relaxed text-slate-600">
          Point FixGuard at your site and read what actually happens when
          somebody uses it.
        </p>
        <Link
          to="/signin"
          state={{ mode: "signup", from: next }}
          className="mt-8 inline-block rounded-xl bg-brand px-8 py-4 font-semibold text-white shadow-sm transition hover:bg-brand-dark"
        >
          Create your account
        </Link>
        <p className="mt-4 text-sm text-slate-500">
          Your audits stay private to your account.
        </p>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-6 py-8 text-sm text-slate-500">
      <span className="font-display font-extrabold text-slate-700">
        FixGuard AI
      </span>
      <span>Built for the Hostinger Startup Challenge.</span>
      <Link to="/signin" className="ml-auto font-medium hover:text-slate-800">
        Sign in
      </Link>
    </footer>
  );
}
