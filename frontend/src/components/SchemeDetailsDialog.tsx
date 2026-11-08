import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { ArrowUpRight, Building2, ExternalLink, Landmark, Users, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import * as api from "../api";
import { safeUrl } from "../lib/safeUrl";
import { Markdown } from "./Markdown";

type Lang = "en" | "hi";

// Keep what was already fetched, so re-opening a scheme (or switching language back) is instant.
const cache = new Map<string, api.SchemeDetails>();

const COPY = {
  en: {
    about: "About this scheme",
    benefits: "What you get",
    eligible: "Who can apply",
    excluded: "Who is not eligible",
    apply: "How to apply",
    openPortal: "Open application page",
    links: "Official links and guidelines",
    source: "Source: myScheme.gov.in. This is a first guide, not a decision. Always confirm on the official website.",
    viewOn: "View on myScheme",
    loading: "Loading official details…",
    unavailable: "Official details are not available for this scheme yet.",
    retry: "Try again",
    close: "Close",
    for: "Meant for",
    docsHint: "Documents you need are listed inside the application steps below.",
  },
  hi: {
    about: "योजना के बारे में",
    benefits: "आपको क्या मिलता है",
    eligible: "कौन आवेदन कर सकता है",
    excluded: "कौन पात्र नहीं है",
    apply: "आवेदन कैसे करें",
    openPortal: "आवेदन पेज खोलें",
    links: "आधिकारिक लिंक और दिशानिर्देश",
    source: "स्रोत: myScheme.gov.in. यह एक शुरुआती मार्गदर्शन है, अंतिम फ़ैसला नहीं। हमेशा आधिकारिक वेबसाइट पर पुष्टि करें।",
    viewOn: "myScheme पर देखें",
    loading: "आधिकारिक जानकारी लोड हो रही है…",
    unavailable: "इस योजना की आधिकारिक जानकारी अभी उपलब्ध नहीं है।",
    retry: "फिर कोशिश करें",
    close: "बंद करें",
    for: "किनके लिए",
    docsHint: "ज़रूरी दस्तावेज़ नीचे आवेदन के चरणों में बताए गए हैं।",
  },
} as const;

function Section({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={cn("border-t border-border pt-5", className)}>
      <h3 className="font-display text-lg font-semibold text-primary">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

type Props = {
  slug: string;
  /** Scheme name shown while the full record loads. */
  title: string;
  initialLang?: Lang;
  /** Where to send people if there is no record: the scheme's own official site. */
  fallbackUrl?: string | null;
  onClose: () => void;
};

export function SchemeDetailsDialog({ slug, title, initialLang = "en", fallbackUrl, onClose }: Props) {
  const [lang, setLang] = useState<Lang>(initialLang);
  const [data, setData] = useState<api.SchemeDetails | null>(cache.get(`${slug}:${initialLang}`) ?? null);
  const [loading, setLoading] = useState(!data);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const opener = useRef<Element | null>(null);
  const t = COPY[lang];

  useEffect(() => {
    const hit = cache.get(`${slug}:${lang}`);
    if (hit) {
      setData(hit);
      setLoading(false);
      setFailed(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setFailed(false);
    api
      .getSchemeDetails(slug, lang, controller.signal)
      .then((d) => {
        cache.set(`${slug}:${lang}`, d);
        setData(d);
        setLoading(false);
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setFailed(true);
        setLoading(false);
      });
    return () => controller.abort();
  }, [slug, lang, attempt]);

  // Focus in, lock background scroll, close on Escape, give focus back.
  useEffect(() => {
    opener.current = document.activeElement;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panelRef.current?.focus();
    return () => {
      document.body.style.overflow = prevOverflow;
      if (opener.current instanceof HTMLElement) opener.current.focus();
    };
  }, []);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      // keep Tab inside the dialog
      const nodes = panelRef.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), summary, [tabindex]:not([tabindex="-1"])',
      );
      if (!nodes || nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === panelRef.current)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    },
    [onClose],
  );

  const pageUrl = safeUrl(data?.page_url) ?? safeUrl(fallbackUrl);
  const primaryApply = data?.apply.map((a) => safeUrl(a.url)).find(Boolean) ?? null;

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-end justify-center bg-primary/50 p-0 backdrop-blur-[2px] sm:items-center sm:p-6"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        className="flex max-h-[92dvh] w-full max-w-3xl flex-col overflow-hidden rounded-t-3xl bg-background text-foreground shadow-2xl outline-none sm:rounded-3xl"
      >
        {/* header */}
        <div className="flex items-start justify-between gap-4 border-b border-border bg-card px-5 py-4 sm:px-7">
          <div className="min-w-0">
            <h2 id={titleId} className="font-display text-xl font-semibold leading-snug text-primary sm:text-2xl">
              {data?.name || title}
            </h2>
            {data && (
              <div className="mt-2 flex flex-wrap gap-2 text-xs font-semibold">
                {data.level && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-primary">
                    <Landmark aria-hidden="true" className="size-3" /> {data.level}
                  </span>
                )}
                {data.ministry && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-primary">
                    <Building2 aria-hidden="true" className="size-3" /> {data.ministry}
                  </span>
                )}
                {data.beneficiaries.length > 0 && (
                  <span className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1 text-plum-soft">
                    <Users aria-hidden="true" className="size-3" /> {t.for}: {data.beneficiaries.join(", ")}
                  </span>
                )}
              </div>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <div role="group" aria-label="Language" className="flex rounded-full border border-border p-0.5 text-xs font-semibold">
              {(["en", "hi"] as const).map((l) => (
                <button
                  key={l}
                  type="button"
                  aria-pressed={lang === l}
                  onClick={() => setLang(l)}
                  className={cn(
                    "rounded-full px-2.5 py-1 transition-colors",
                    lang === l ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-primary",
                  )}
                >
                  {l === "en" ? "EN" : "हिं"}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t.close}
              className="flex size-9 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-secondary hover:text-primary"
            >
              <X aria-hidden="true" className="size-5" />
            </button>
          </div>
        </div>

        {/* body */}
        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-6 sm:px-7" aria-busy={loading}>
          {loading && !data && (
            <div role="status" className="space-y-3" aria-live="polite">
              <p className="text-sm text-muted-foreground">{t.loading}</p>
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-16 animate-pulse rounded-xl bg-secondary/70" />
              ))}
            </div>
          )}

          {failed && !data && (
            <div role="alert" className="rounded-2xl border border-border bg-card p-6 text-center">
              <p className="font-display text-lg font-semibold text-primary">{t.unavailable}</p>
              <div className="mt-4 flex flex-wrap justify-center gap-3">
                <Button variant="outline" className="rounded-full" onClick={() => setAttempt((n) => n + 1)}>
                  {t.retry}
                </Button>
                {safeUrl(fallbackUrl) && (
                  <Button asChild className="rounded-full">
                    <a href={safeUrl(fallbackUrl)!} target="_blank" rel="noopener noreferrer">
                      {t.viewOn} <ExternalLink aria-hidden="true" />
                    </a>
                  </Button>
                )}
              </div>
            </div>
          )}

          {data && (
            <div className={cn("space-y-6 transition-opacity", loading && "opacity-50")}>
              {(data.brief || data.description_md) && (
                <section>
                  <h3 className="font-display text-lg font-semibold text-primary">{t.about}</h3>
                  <div className="mt-3">
                    <Markdown text={data.brief || data.description_md} />
                  </div>
                </section>
              )}
              {data.benefits_md && (
                <Section title={t.benefits}>
                  <Markdown text={data.benefits_md} />
                </Section>
              )}
              {data.eligibility_md && (
                <Section title={t.eligible}>
                  <Markdown text={data.eligibility_md} />
                </Section>
              )}
              {data.exclusions_md && (
                <details className="group border-t border-border pt-5">
                  <summary className="cursor-pointer list-none font-display text-lg font-semibold text-primary marker:hidden">
                    {t.excluded}
                    <span aria-hidden="true" className="ml-2 text-sm text-plum-soft group-open:hidden">+</span>
                    <span aria-hidden="true" className="ml-2 hidden text-sm text-plum-soft group-open:inline">–</span>
                  </summary>
                  <div className="mt-3">
                    <Markdown text={data.exclusions_md} />
                  </div>
                </details>
              )}
              {data.apply.length > 0 && (
                <Section title={t.apply}>
                  <p className="mb-4 text-sm text-muted-foreground">{t.docsHint}</p>
                  <div className="space-y-4">
                    {data.apply.map((a, i) => {
                      const href = safeUrl(a.url);
                      return (
                        <div key={i} className="rounded-2xl border border-border bg-card p-4 sm:p-5">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <h4 className="font-display text-base font-semibold text-primary">{a.mode || t.apply}</h4>
                            {href && (
                              <Button asChild size="sm" className="rounded-full">
                                <a href={href} target="_blank" rel="noopener noreferrer">
                                  {t.openPortal} <ArrowUpRight aria-hidden="true" />
                                </a>
                              </Button>
                            )}
                          </div>
                          {a.steps_md && <Markdown text={a.steps_md} className="mt-3" />}
                        </div>
                      );
                    })}
                  </div>
                </Section>
              )}
              {data.references.length > 0 && (
                <Section title={t.links}>
                  <ul className="space-y-1.5 text-[15px]">
                    {data.references.map((r, i) => {
                      const href = safeUrl(r.url);
                      return href ? (
                        <li key={i}>
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 font-medium text-plum-soft underline underline-offset-2 hover:text-primary"
                          >
                            {r.title || href} <ExternalLink aria-hidden="true" className="size-3.5" />
                          </a>
                        </li>
                      ) : null;
                    })}
                  </ul>
                </Section>
              )}
            </div>
          )}
        </div>

        {/* footer */}
        <div className="flex flex-col gap-3 border-t border-border bg-card px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-7">
          <p className="text-xs leading-5 text-muted-foreground">{t.source}</p>
          <div className="flex shrink-0 flex-wrap gap-2">
            {primaryApply && data && (
              <Button asChild className="rounded-full">
                <a href={primaryApply} target="_blank" rel="noopener noreferrer">
                  {t.openPortal} <ArrowUpRight aria-hidden="true" />
                </a>
              </Button>
            )}
            {pageUrl && (
              <Button asChild variant="outline" className="rounded-full">
                <a href={pageUrl} target="_blank" rel="noopener noreferrer">
                  {t.viewOn} <ExternalLink aria-hidden="true" />
                </a>
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
