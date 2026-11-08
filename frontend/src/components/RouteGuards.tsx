import { Navigate, Outlet, useLocation } from "react-router-dom";
import { AudioLines } from "lucide-react";
import { useAuth } from "../auth";

type FromState = { from?: { pathname?: string; search?: string; hash?: string } } | null;

function Splash() {
  return (
    <div
      className="flex min-h-screen items-center justify-center bg-background text-primary"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-3">
        <span className="flex size-10 animate-pulse items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <AudioLines aria-hidden="true" className="size-5" />
        </span>
        <span className="font-display text-lg font-semibold">Loading…</span>
      </div>
    </div>
  );
}

/** Only for signed-in users. Sends everyone else to /login and remembers where they were going. */
export function RequireAuth() {
  const { token, ready } = useAuth();
  const location = useLocation();

  if (!ready) return <Splash />;
  if (!token) return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}

/** Only for signed-out users (login / register). Signed-in users go back where they were headed, or to the desk. */
export function GuestOnly() {
  const { token, ready } = useAuth();
  const location = useLocation();

  if (!ready) return <Splash />;
  if (token) {
    const from = (location.state as FromState)?.from;
    const target =
      from?.pathname && from.pathname.startsWith("/") && !from.pathname.startsWith("//")
        ? `${from.pathname}${from.search ?? ""}${from.hash ?? ""}`
        : "/desk";
    return <Navigate to={target} replace />;
  }
  return <Outlet />;
}
