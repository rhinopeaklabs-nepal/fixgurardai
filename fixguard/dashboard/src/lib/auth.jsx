import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";

/**
 * Who is signed in, for the whole app.
 *
 * The session itself lives in an httpOnly cookie, so this context never holds
 * a credential - only the answer to "who is this", which the server gives on
 * request. That means there is nothing here for a stray script to steal, and
 * nothing to keep in sync with the real session: if the cookie expires, the
 * next call fails and the app finds out.
 */
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // Three states, not two. Before the first answer arrives we do not know
  // whether this person is signed in, and rendering the sign-in screen during
  // that gap makes every reload flash a login form at someone already signed
  // in.
  const [status, setStatus] = useState("checking");

  const refresh = useCallback(async () => {
    try {
      const { user: u } = await api.me();
      setUser(u || null);
      setStatus(u ? "signed-in" : "signed-out");
      return u || null;
    } catch {
      // A failure here means the API is unreachable, not that the person is
      // signed out - but there is nothing they can do with the app either
      // way, and the sign-in screen is the honest place to land.
      setUser(null);
      setStatus("signed-out");
      return null;
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const signIn = useCallback(async (email, password) => {
    const { user: u } = await api.login(email, password);
    setUser(u);
    setStatus("signed-in");
    return u;
  }, []);

  const signUp = useCallback(async (email, password, name) => {
    const { user: u } = await api.signup(email, password, name);
    setUser(u);
    setStatus("signed-in");
    return u;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      // Clear locally even if the request failed. Leaving the UI signed in
      // after somebody pressed Sign out is the worse of the two wrong states,
      // especially on a shared machine.
      setUser(null);
      setStatus("signed-out");
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, status, refresh, signIn, signUp, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
