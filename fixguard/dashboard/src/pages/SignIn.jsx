import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

/**
 * Sign in, or create an account.
 *
 * One screen for both, because the two forms differ by a single field and
 * sending people to a separate page to discover they are on the wrong one is
 * the most common way this flow wastes somebody's time.
 */
export default function SignIn({ mode: initial }) {
  const location = useLocation();
  // "Create account" on the landing page should land on the create form,
  // not on sign-in with an extra click to find it.
  const [mode, setMode] = useState(
    initial || location.state?.mode || "signin",
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [reveal, setReveal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const { signIn, signUp } = useAuth();
  const navigate = useNavigate();
  const from = location.state?.from || "/";

  const isSignUp = mode === "signup";

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (isSignUp) await signUp(email, password, name);
      else await signIn(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message || "That did not work. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_1.1fr]">
      {/* ---------------- the form ---------------- */}
      <div className="flex items-center justify-center px-6 py-14">
        <div className="w-full max-w-sm">
          <Link
            to="/"
            className="font-display text-lg font-extrabold tracking-tight text-brand"
          >
            FixGuard AI
          </Link>

          <h1 className="mt-8 font-display text-2xl font-extrabold tracking-tight text-slate-900">
            {isSignUp ? "Create your account" : "Sign in"}
          </h1>
          <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
            {isSignUp
              ? "Your audits and prompts stay private to your account."
              : "Welcome back."}
          </p>

          <form onSubmit={submit} className="mt-7 space-y-4" noValidate>
            {isSignUp && (
              <Field label="Your name" hint="Optional">
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoComplete="name"
                  className={INPUT}
                  placeholder="Alex Morgan"
                />
              </Field>
            )}

            <Field label="Email">
              <input
                type="email"
                required
                autoFocus={!isSignUp}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                className={INPUT}
                placeholder="you@yourcompany.com"
              />
            </Field>

            <Field
              label="Password"
              hint={isSignUp ? "At least 10 characters" : undefined}
            >
              <div className="relative">
                <input
                  type={reveal ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete={isSignUp ? "new-password" : "current-password"}
                  className={`${INPUT} pr-16`}
                  placeholder={isSignUp ? "a few ordinary words" : ""}
                />
                <button
                  type="button"
                  onClick={() => setReveal((v) => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded px-2 py-1 text-xs font-semibold text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                >
                  {reveal ? "Hide" : "Show"}
                </button>
              </div>
            </Field>

            {isSignUp && (
              <p className="text-xs leading-relaxed text-slate-500">
                A few ordinary words in a row is stronger than one short word
                with symbols in it.
              </p>
            )}

            {error && (
              <p
                role="alert"
                className="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700"
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-brand px-4 py-2.5 font-semibold text-white transition hover:bg-brand-dark disabled:opacity-60"
            >
              {busy
                ? isSignUp
                  ? "Creating account…"
                  : "Signing in…"
                : isSignUp
                  ? "Create account"
                  : "Sign in"}
            </button>
          </form>

          <p className="mt-6 text-sm text-slate-600">
            {isSignUp ? "Already have an account?" : "No account yet?"}{" "}
            <button
              onClick={() => {
                setMode(isSignUp ? "signin" : "signup");
                setError(null);
              }}
              className="font-semibold text-brand hover:underline"
            >
              {isSignUp ? "Sign in" : "Create one"}
            </button>
          </p>

          <p className="mt-8 border-t border-slate-200 pt-5 text-xs leading-relaxed text-slate-500">
            This password is for FixGuard only. FixGuard never asks for the
            password to any site it audits &mdash; to check a page behind a
            login, you sign in yourself and hand it the resulting session.
          </p>
        </div>
      </div>

      {/* ---------------- what it does ---------------- */}
      <aside className="hidden flex-col justify-center bg-slate-900 px-12 py-14 lg:flex">
        {/* On the dark panel the brand blue falls to 3.21:1. Same hue,
            lightened until it reads, and only here. */}
        <p className="text-xs font-semibold uppercase tracking-wider text-brand-on-dark">
          Pre-flight QA for AI Builder sites
        </p>
        <h2 className="mt-4 max-w-md font-display text-3xl font-extrabold leading-tight tracking-tight text-white">
          Find what is broken before your customers do
        </h2>
        <p className="mt-4 max-w-md leading-relaxed text-slate-300">
          FixGuard opens your site in a real browser, submits your forms,
          follows your routes, and reports what actually happens rather than
          what the page claims.
        </p>

        <ul className="mt-9 max-w-md space-y-4">
          {[
            [
              "Silent form failures",
              "A contact form that shows a success message and sends nothing is the failure nobody reports to you.",
            ],
            [
              "Routes that lead nowhere",
              "Every internal link followed, not just listed, with redirect loops and soft 404s named.",
            ],
            [
              "Who your visitors reach",
              "Every third party that receives a request from your page, grouped by what it is for.",
            ],
          ].map(([title, body]) => (
            <li key={title} className="flex gap-3">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
              <div>
                <p className="font-semibold text-white">{title}</p>
                {/* On the dark panel the ramp inverts: 400 is 3.24:1 here,
                    300 is 11.47:1. */}
                <p className="mt-0.5 text-sm leading-relaxed text-slate-300">
                  {body}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

const INPUT =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-brand focus:ring-2 focus:ring-brand/20";

function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-baseline justify-between">
        <span className="text-sm font-semibold text-slate-700">{label}</span>
        {hint && <span className="text-xs text-slate-400">{hint}</span>}
      </span>
      {children}
    </label>
  );
}
