import { useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import * as api from "../api";
import { useAuth } from "../auth";
import { AuthLayout, Field } from "../components/AuthLayout";
import { usePageTitle } from "../lib/usePageTitle";

export function LoginPage() {
  usePageTitle("Log in");
  const { setSession } = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Keep the redirect target when switching between login and register.
  const keepState = { state: location.state };

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.login(username.trim(), password);
      // GuestOnly sees the new session and redirects to the page the user wanted, or /desk.
      setSession(res.access_token, res.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      setBusy(false);
    }
  }

  function handleQuickFill() {
    setUsername("test_citizen");
    setPassword("password123");
  }

  return (
    <AuthLayout
      eyebrow="Welcome back"
      title="Log in"
      subtitle="Open the voice desk with your username."
      footer={
        <p>
          New here?{" "}
          <Link
            to="/register"
            {...keepState}
            className="font-semibold text-primary underline decoration-lime decoration-2 underline-offset-4"
          >
            Create an account
          </Link>
        </p>
      }
    >
      <form onSubmit={onSubmit} className="grid gap-5">
        <Field
          label="Username"
          name="username"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          minLength={3}
          autoFocus
        />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={6}
        />

        {error && (
          <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {error}
          </p>
        )}

        <Button type="submit" size="lg" className="h-12 rounded-full text-base" disabled={busy}>
          {busy ? "Signing in…" : (
            <>
              Log in <ArrowRight aria-hidden="true" />
            </>
          )}
        </Button>

        <button
          type="button"
          onClick={handleQuickFill}
          className="rounded-full border border-dashed border-border px-4 py-2.5 text-sm font-semibold text-primary transition-colors hover:bg-secondary"
        >
          Quick-fill demo account
        </button>
      </form>
    </AuthLayout>
  );
}
