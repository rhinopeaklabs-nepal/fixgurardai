import { Suspense, lazy } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Nav from "./components/Nav";
import Home from "./pages/Home";
import SharedReport from "./pages/SharedReport";
import SignIn from "./pages/SignIn";
import { AuthProvider, useAuth } from "./lib/auth";

// Only three things are in the first download: the audit console somebody
// signs in to use, the sign-in page, and the public report a client opens
// from a link. Everything else is fetched when it is first opened.
//
// This is not only about weight. The admin console described the shape of
// the operations data - route names, table names, thresholds - to every
// visitor who ever loaded the dashboard, including the ones who could never
// open it. Splitting it out means it is downloaded by people who use it.
const AuditDetail = lazy(() => import("./pages/AuditDetail"));
const PromptStudio = lazy(() => import("./pages/PromptStudio"));
const History = lazy(() => import("./pages/History"));
const Compare = lazy(() => import("./pages/Compare"));
const Architecture = lazy(() => import("./pages/Architecture"));
const Admin = lazy(() => import("./pages/Admin"));

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}

function Shell() {
  const location = useLocation();

  // The public report is standalone: a client following a shared link has no
  // account here and should not see the owner's navigation, or be asked to
  // sign in to read a report that was deliberately shared with them.
  const isPublic = location.pathname.startsWith("/r/");
  const isSignIn = location.pathname === "/signin";

  return (
    <>
      {/* The first thing a keyboard reaches on every page. Without it, getting
          to the audit form means tabbing past the whole navigation on every
          single load, which is the one journey a keyboard user repeats most. */}
      <a
        href="#main"
        className="sr-only left-3 top-3 z-50 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white focus:not-sr-only focus:absolute"
      >
        Skip to content
      </a>
      {!isPublic && !isSignIn && <Nav />}
      <main id="main">
      {/* The same placeholder the session check uses. A lazy chunk arriving
          looks to the reader exactly like a page deciding whether they are
          signed in, and it should: both are the app not knowing yet. */}
      <Suspense fallback={<Waiting />}>
      <Routes>
        <Route path="/r/:token" element={<SharedReport />} />
        <Route path="/signin" element={<SignedOutOnly><SignIn /></SignedOutOnly>} />

        <Route path="/" element={<RequireAuth><Home /></RequireAuth>} />
        <Route path="/a/:id" element={<RequireAuth><AuditDetail /></RequireAuth>} />
        <Route path="/a/:id/compare" element={<RequireAuth><Compare /></RequireAuth>} />
        <Route path="/prompts" element={<RequireAuth><PromptStudio /></RequireAuth>} />
        <Route path="/history" element={<RequireAuth><History /></RequireAuth>} />
        <Route path="/architecture" element={<RequireAuth><Architecture /></RequireAuth>} />

        {/* The server answers 404 to a non-admin, so this route being
            reachable gives nothing away. Gating it here as well keeps a
            mistyped URL from showing a signed-in user a broken page. */}
        <Route path="/admin" element={<RequireAdmin><Admin /></RequireAdmin>} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
      </main>
    </>
  );
}

/**
 * Gate a page behind a session.
 *
 * While the first /me call is still in flight the answer is genuinely unknown,
 * and rendering either the page or the sign-in screen would be a guess. A
 * quiet placeholder is the only honest third option, and it stops every
 * reload flashing a login form at somebody who is already signed in.
 */
function RequireAuth({ children }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "checking") return <Waiting />;
  if (status === "signed-out") {
    // Carry the whole destination, search string included. Keeping only the
    // path silently drops ?url=, which is how a visitor handed over from the
    // marketing page would have to retype the address they just typed there.
    return (
      <Navigate
        to="/signin"
        replace
        state={{ from: location.pathname + location.search }}
      />
    );
  }
  return children;
}

/**
 * Admin is decided by the server on every /me, not by anything this bundle
 * can set. Redirecting rather than rendering an error keeps the console
 * invisible to an account that has no business knowing it is there.
 */
function RequireAdmin({ children }) {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === "checking") return <Waiting />;
  if (status === "signed-out") {
    return (
      <Navigate
        to="/signin"
        replace
        state={{ from: location.pathname + location.search }}
      />
    );
  }
  if (!user?.is_admin) return <Navigate to="/" replace />;
  return children;
}


function SignedOutOnly({ children }) {
  const { status } = useAuth();
  if (status === "checking") return <Waiting />;
  if (status === "signed-in") return <Navigate to="/" replace />;
  return children;
}

function Waiting() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <span className="h-6 w-6 animate-ring rounded-full border-2 border-slate-300 border-t-brand" />
    </div>
  );
}
