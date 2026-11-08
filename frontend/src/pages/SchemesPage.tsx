import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import * as api from "../api";
import { Pagination } from "../components/Pagination";
import { SchemeCard } from "../components/SchemeCard";
import { SiteFooter, SiteHeader } from "../components/SiteChrome";
import { usePageTitle } from "../lib/usePageTitle";

const PAGE_SIZE = 12;

function parsePage(raw: string | null): number {
  const n = Number.parseInt(raw ?? "", 10);
  return Number.isFinite(n) && n >= 1 ? n : 1;
}

export function SchemesPage() {
  const [params, setParams] = useSearchParams();
  const page = parsePage(params.get("page"));
  const q = (params.get("q") ?? "").trim();

  const [draft, setDraft] = useState(q);
  const [data, setData] = useState<api.SchemePage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const resultsRef = useRef<HTMLDivElement | null>(null);
  const firstLoad = useRef(true);

  usePageTitle(q ? `Schemes: ${q}` : page > 1 ? `Schemes, page ${page}` : "Schemes");

  // Keep the search box in sync when the URL changes (back/forward, links).
  useEffect(() => setDraft(q), [q]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    api
      .listSchemes({ page, pageSize: PAGE_SIZE, q }, controller.signal)
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Could not load schemes");
        setLoading(false);
      });
    return () => controller.abort();
  }, [page, q, reloadKey]);

  // After the first load, bring the top of the results into view when the page changes.
  useEffect(() => {
    if (loading) return;
    if (firstLoad.current) {
      firstLoad.current = false;
      return;
    }
    resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [page, q, loading]);

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function hrefFor(p: number) {
    const next = new URLSearchParams();
    if (q) next.set("q", q);
    if (p > 1) next.set("page", String(p));
    const qs = next.toString();
    return qs ? `/schemes?${qs}` : "/schemes";
  }

  function onSearch(e: FormEvent) {
    e.preventDefault();
    const next = new URLSearchParams();
    if (draft.trim()) next.set("q", draft.trim());
    setParams(next);
  }

  function clearSearch() {
    setDraft("");
    setParams(new URLSearchParams());
  }

  // Page number beyond the last page (stale link): go to the real last page.
  if (data && !loading && total > 0 && page > totalPages) {
    return <Navigate to={hrefFor(totalPages)} replace />;
  }

  const from = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE, total);

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <SiteHeader />

      <main className="flex-1 px-5 py-14 md:px-10 2xl:px-16 md:py-20">
        <div className="mx-auto max-w-[1680px]">
          <div className="max-w-2xl">
            <p className="text-sm font-bold uppercase tracking-[0.12em] text-plum-soft">Scheme directory</p>
            <h1 className="mt-4 font-display text-4xl font-semibold leading-tight text-primary md:text-5xl">
              Browse government schemes.
            </h1>
            <p className="mt-5 text-lg leading-8 text-muted-foreground">
              Every entry links to its official page. Prefer to talk instead?{" "}
              <Link to="/desk" className="font-semibold text-primary underline decoration-lime decoration-2 underline-offset-4">
                Open the voice desk
              </Link>
              .
            </p>
          </div>

          <form onSubmit={onSearch} role="search" className="mt-10 flex max-w-xl items-center gap-2">
            <label htmlFor="scheme-search" className="sr-only">
              Search schemes
            </label>
            <div className="relative flex-1">
              <Search aria-hidden="true" className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <input
                id="scheme-search"
                type="search"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Search by name, e.g. pension or kisan"
                className="h-12 w-full rounded-full border border-border bg-card pl-11 pr-4 text-base text-foreground outline-none placeholder:text-muted-foreground focus:border-plum-soft focus:ring-4 focus:ring-plum-soft/15"
                maxLength={120}
              />
            </div>
            <Button type="submit" size="lg" className="h-12 rounded-full px-6 text-base">
              Search
            </Button>
          </form>

          <div ref={resultsRef} className="mt-10 scroll-mt-6">
            <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground" aria-live="polite">
              {error ? (
                <span />
              ) : loading && !data ? (
                <span>Loading schemes…</span>
              ) : total === 0 ? (
                <span>No schemes found{q ? ` for “${q}”` : ""}.</span>
              ) : (
                <span>
                  Showing <strong className="text-primary">{from.toLocaleString()}–{to.toLocaleString()}</strong> of{" "}
                  <strong className="text-primary">{total.toLocaleString()}</strong> schemes
                  {q ? <> matching “{q}”</> : null}
                </span>
              )}
              {q && (
                <button
                  type="button"
                  onClick={clearSearch}
                  className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 font-semibold text-primary hover:bg-secondary"
                >
                  <X aria-hidden="true" className="size-3.5" /> Clear search
                </button>
              )}
            </div>

            {error ? (
              <div role="alert" className="mt-6 rounded-2xl border border-border bg-card p-8 text-center">
                <p className="font-display text-xl font-semibold text-primary">Couldn’t load schemes</p>
                <p className="mt-2 text-sm text-muted-foreground">{error}</p>
                <Button className="mt-5 rounded-full px-6" onClick={() => setReloadKey((k) => k + 1)}>
                  Try again
                </Button>
              </div>
            ) : loading && !data ? (
              <ul className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4" aria-hidden="true">
                {Array.from({ length: 6 }, (_, i) => (
                  <li key={i} className="h-44 animate-pulse rounded-2xl border border-border bg-secondary/60" />
                ))}
              </ul>
            ) : total === 0 ? (
              <div className="mt-6 rounded-2xl border border-border bg-card p-10 text-center">
                <p className="font-display text-xl font-semibold text-primary">Nothing matched.</p>
                <p className="mt-2 text-sm text-muted-foreground">Try a shorter word, or clear the search to see every scheme.</p>
              </div>
            ) : (
              <ul
                className={`mt-6 grid gap-5 transition-opacity sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 ${loading ? "opacity-50" : ""}`}
                aria-busy={loading}
              >
                {data?.schemes.map((s) => (
                  <li key={s.id}>
                    <SchemeCard scheme={s} />
                  </li>
                ))}
              </ul>
            )}

            {!error && total > 0 && (
              <Pagination
                className="mt-10"
                page={page}
                totalPages={totalPages}
                hrefFor={hrefFor}
                label="Scheme pages"
              />
            )}
          </div>
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
