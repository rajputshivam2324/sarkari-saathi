import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";
import * as api from "./api";

type AuthState = {
  token: string | null;
  user: api.User | null;
  ready: boolean;
  setSession: (token: string, user: api.User) => void;
  /** User-initiated sign out: goes to the home page first, then clears the session. */
  logout: () => void;
  /** Silent sign out for an expired/invalid token. Protected pages then send the user to /login. */
  expireSession: () => void;
};

const AuthCtx = createContext<AuthState | null>(null);
const KEY = "ss_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(KEY));
  const [user, setUser] = useState<api.User | null>(null);
  const [ready, setReady] = useState(false);
  const [pendingLogout, setPendingLogout] = useState(false);
  const navigate = useNavigate();
  const { pathname } = useLocation();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!token) {
        setUser(null);
        setReady(true);
        return;
      }
      try {
        const u = await api.me(token);
        if (!cancelled) setUser(u);
      } catch (err) {
        // Only an explicit 401 means the session is invalid. A network error or
        // 5xx must not log the user out.
        if (err instanceof api.ApiError && err.status === 401) {
          localStorage.removeItem(KEY);
          if (!cancelled) {
            setToken(null);
            setUser(null);
          }
        }
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const setSession = (t: string, u: api.User) => {
    localStorage.setItem(KEY, t);
    setToken(t);
    setUser(u);
  };

  const expireSession = useCallback(() => {
    localStorage.removeItem(KEY);
    setToken(null);
    setUser(null);
  }, []);

  // Leave the current page before the session disappears, otherwise the route guard on a
  // protected page would win the race and redirect to /login instead of home.
  const logout = () => {
    if (pathname === "/") {
      expireSession();
      return;
    }
    setPendingLogout(true);
    navigate("/", { replace: true });
  };

  useEffect(() => {
    if (pendingLogout && pathname === "/") {
      expireSession();
      setPendingLogout(false);
    }
  }, [pendingLogout, pathname, expireSession]);

  return (
    <AuthCtx.Provider value={{ token, user, ready, setSession, logout, expireSession }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth outside provider");
  return ctx;
}
