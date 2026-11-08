import { useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import * as api from "../api";
import { useAuth } from "../auth";
import { AuthLayout, Field } from "../components/AuthLayout";
import { usePageTitle } from "../lib/usePageTitle";

export function RegisterPage() {
  usePageTitle("Create an account");
  const { setSession } = useAuth();
  const location = useLocation();
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const keepState = { state: location.state };

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.register(username.trim(), password, name.trim() || undefined);
      // GuestOnly sees the new session and redirects to /desk (or the page the user wanted).
      setSession(res.access_token, res.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
      setBusy(false);
    }
  }

  function handleQuickFill() {
    const randomId = Math.floor(1000 + Math.random() * 9000);
    setName("Ramesh Citizen");
    setUsername(`citizen_${randomId}`);
    setPassword("password123");
  }

  return (
    <AuthLayout
      eyebrow="Get started"
      title="Create an account"
      subtitle="Username and password only. Then start speaking."
      footer={
        <p>
          Already registered?{" "}
          <Link
            to="/login"
            {...keepState}
            className="font-semibold text-primary underline decoration-lime decoration-2 underline-offset-4"
          >
            Log in
          </Link>
        </p>
      }
    >
      <form onSubmit={onSubmit} className="grid gap-5">
        <Field
          label="Name (optional)"
          name="name"
          autoComplete="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={120}
          autoFocus
        />
        <Field
          label="Username"
          name="username"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          minLength={3}
          maxLength={64}
          hint="At least 3 characters."
        />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={6}
          hint="At least 6 characters."
        />

        {error && (
          <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {error}
          </p>
        )}

        <Button type="submit" size="lg" className="h-12 rounded-full text-base" disabled={busy}>
          {busy ? "Creating…" : (
            <>
              Start speaking <ArrowRight aria-hidden="true" />
            </>
          )}
        </Button>

        <button
          type="button"
          onClick={handleQuickFill}
          className="rounded-full border border-dashed border-border px-4 py-2.5 text-sm font-semibold text-primary transition-colors hover:bg-secondary"
        >
          Quick-fill demo profile
        </button>
      </form>
    </AuthLayout>
  );
}
