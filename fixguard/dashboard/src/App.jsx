import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Nav from "./components/Nav";
import Home from "./pages/Home";
import AuditDetail from "./pages/AuditDetail";
import PromptStudio from "./pages/PromptStudio";
import History from "./pages/History";
import Compare from "./pages/Compare";
import Architecture from "./pages/Architecture";
import SharedReport from "./pages/SharedReport";
import SignIn from "./pages/SignIn";
import { AuthProvider, useAuth } from "./lib/auth";

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
      {!isPublic && !isSignIn && <Nav />}
      <Routes>
        <Route path="/r/:token" element={<SharedReport />} />
        <Route path="/signin" element={<SignedOutOnly><SignIn /></SignedOutOnly>} />

        <Route path="/" element={<RequireAuth><Home /></RequireAuth>} />
        <Route path="/a/:id" element={<RequireAuth><AuditDetail /></RequireAuth>} />
        <Route path="/a/:id/compare" element={<RequireAuth><Compare /></RequireAuth>} />
        <Route path="/prompts" element={<RequireAuth><PromptStudio /></RequireAuth>} />
        <Route path="/history" element={<RequireAuth><History /></RequireAuth>} />
        <Route path="/architecture" element={<RequireAuth><Architecture /></RequireAuth>} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
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
