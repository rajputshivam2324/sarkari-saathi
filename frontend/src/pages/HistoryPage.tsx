import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { ArrowRight, MessageSquare, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import * as api from "../api";
import { useAuth } from "../auth";
import { Pagination } from "../components/Pagination";
import { SiteFooter, SiteHeader } from "../components/SiteChrome";
import { usePageTitle } from "../lib/usePageTitle";

const PAGE_SIZE = 10;

function parsePage(raw: string | null): number {
  const n = Number.parseInt(raw ?? "", 10);
  return Number.isFinite(n) && n >= 1 ? n : 1;
}

const dateFmt = new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" });

function formatWhen(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : dateFmt.format(d);
}

export function HistoryPage() {
  usePageTitle("Conversation history");
  const { token, expireSession } = useAuth();
  const [params] = useSearchParams();
  const page = parsePage(params.get("page"));

  const [data, setData] = useState<api.ChatSessionPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const firstLoad = useRef(true);
  const topRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    api
      .listSessions(token, { page, pageSize: PAGE_SIZE }, controller.signal)
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        if (err instanceof api.ApiError && err.status === 401) {
          expireSession(); // RequireAuth sends the user to /login
          return;
        }
        setError(err instanceof Error ? err.message : "Could not load your conversations");
        setLoading(false);
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, page, reloadKey]);

  useEffect(() => {
    if (loading) return;
    if (firstLoad.current) {
      firstLoad.current = false;
      return;
    }
    topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [page, loading]);

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hrefFor = (p: number) => (p > 1 ? `/history?page=${p}` : "/history");

  async function onDelete(id: string) {
    if (!token) return;
    setDeletingId(id);
    setNotice(null);
    try {
      await api.deleteSession(token, id);
      setConfirmId(null);
      setNotice("Conversation deleted.");
      setReloadKey((k) => k + 1);
    } catch (err) {
      setNotice(err instanceof Error ? `Could not delete: ${err.message}` : "Could not delete the conversation.");
    } finally {
      setDeletingId(null);
    }
  }

  // Stale link to a page past the end (e.g. after deleting the last item on the final page).
  if (data && !loading && total > 0 && page > totalPages) {
    return <Navigate to={hrefFor(totalPages)} replace />;
  }
  if (data && !loading && total === 0 && page > 1) {
    return <Navigate to="/history" replace />;
  }

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <SiteHeader />

      <main className="flex-1 px-5 py-14 md:px-10 md:py-20 2xl:px-16">
        <div className="mx-auto max-w-4xl">
          <p className="text-sm font-bold uppercase tracking-[0.12em] text-plum-soft">Your account</p>
          <h1 className="mt-4 font-display text-4xl font-semibold leading-tight text-primary md:text-5xl">
            Conversation history
          </h1>
          <p className="mt-5 text-lg leading-8 text-muted-foreground">
            Pick up where you left off. Open an earlier conversation to read it or to continue it.
          </p>

          <div ref={topRef} className="mt-10 scroll-mt-6">
            {notice && (
              <p role="status" className="mb-4 rounded-lg border border-border bg-secondary px-4 py-3 text-sm text-primary">
                {notice}
              </p>
            )}

            {error ? (
              <div role="alert" className="rounded-2xl border border-border bg-card p-8 text-center">
                <p className="font-display text-xl font-semibold text-primary">Couldn’t load your conversations</p>
                <p className="mt-2 text-sm text-muted-foreground">{error}</p>
                <Button className="mt-5 rounded-full px-6" onClick={() => setReloadKey((k) => k + 1)}>
                  Try again
                </Button>
              </div>
            ) : loading && !data ? (
              <ul className="grid gap-4" aria-hidden="true">
                {Array.from({ length: 4 }, (_, i) => (
                  <li key={i} className="h-24 animate-pulse rounded-2xl border border-border bg-secondary/60" />
                ))}
              </ul>
            ) : total === 0 ? (
              <div className="rounded-2xl border border-border bg-card p-10 text-center">
                <span className="mx-auto flex size-12 items-center justify-center rounded-full bg-secondary text-primary">
                  <MessageSquare aria-hidden="true" className="size-5" />
                </span>
                <p className="mt-5 font-display text-xl font-semibold text-primary">No conversations yet</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Once you talk to Sarkari Saathi, your conversations will show up here.
                </p>
                <Button asChild size="lg" className="mt-6 h-12 rounded-full px-6 text-base">
                  <Link to="/desk">
                    Start conversation <ArrowRight aria-hidden="true" />
                  </Link>
                </Button>
              </div>
            ) : (
              <>
                <p className="mb-4 text-sm text-muted-foreground" aria-live="polite">
                  <strong className="text-primary">{total.toLocaleString()}</strong>{" "}
                  {total === 1 ? "conversation" : "conversations"}
                </p>
                <ul className={`grid gap-4 transition-opacity ${loading ? "opacity-50" : ""}`} aria-busy={loading}>
                  {data?.sessions.map((s) => {
                    const confirming = confirmId === s.session_id;
                    return (
                      <li
                        key={s.session_id}
                        className="rounded-2xl border border-border bg-card p-5 transition-shadow hover:shadow-sm md:p-6"
                      >
                        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                          <div className="min-w-0">
                            <h2 className="break-words font-display text-lg font-semibold leading-snug text-primary">
                              {s.title}
                            </h2>
                            <p className="mt-1 text-sm text-muted-foreground">
                              {formatWhen(s.last_at)} · {s.message_count} {s.message_count === 1 ? "message" : "messages"}
                            </p>
                          </div>

                          {confirming ? (
                            <div className="flex shrink-0 flex-wrap items-center gap-2" role="group" aria-label="Confirm delete">
                              <span className="text-sm text-muted-foreground">Delete this conversation?</span>
                              <Button
                                variant="destructive"
                                size="sm"
                                className="rounded-full"
                                disabled={deletingId === s.session_id}
                                onClick={() => onDelete(s.session_id)}
                              >
                                {deletingId === s.session_id ? "Deleting…" : "Delete"}
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                className="rounded-full"
                                disabled={deletingId === s.session_id}
                                onClick={() => setConfirmId(null)}
                              >
                                Cancel
                              </Button>
                            </div>
                          ) : (
                            <div className="flex shrink-0 items-center gap-2">
                              <Button asChild size="sm" className="rounded-full px-4">
                                <Link to={`/desk?session=${encodeURIComponent(s.session_id)}`}>
                                  Open <ArrowRight aria-hidden="true" />
                                </Link>
                              </Button>
                              <Button
                                variant="outline"
                                size="icon"
                                className="rounded-full"
                                aria-label={`Delete conversation: ${s.title}`}
                                onClick={() => {
                                  setNotice(null);
                                  setConfirmId(s.session_id);
                                }}
                              >
                                <Trash2 aria-hidden="true" />
                              </Button>
                            </div>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>

                <Pagination className="mt-10" page={page} totalPages={totalPages} hrefFor={hrefFor} label="Conversation pages" />
              </>
            )}
          </div>
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
