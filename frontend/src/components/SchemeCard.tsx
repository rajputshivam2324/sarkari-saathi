import { useState } from "react";
import { ExternalLink, FileText, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { safeUrl } from "../lib/safeUrl";
import { SchemeDetailsDialog } from "./SchemeDetailsDialog";

export interface SchemeItem {
  id: string;
  name: string;
  name_hi?: string | null;
  official_url: string;
  description?: string | null;
  category?: string | null;
  short_title?: string | null;
  score?: number | null;
  /** myScheme id: when present, the full official record (eligibility, how to apply, ...) can be opened. */
  slug?: string | null;
}

interface SchemeCardProps {
  scheme: SchemeItem;
  /** Tighter spacing for narrow side panels. */
  compact?: boolean;
  /** Language the details open in. */
  lang?: "en" | "hi";
}

export function SchemeCard({ scheme, compact = false, lang = "en" }: SchemeCardProps) {
  const [open, setOpen] = useState(false);
  const href = safeUrl(scheme.official_url);
  const shortTitle = scheme.short_title && scheme.short_title !== scheme.name ? scheme.short_title : null;
  const description =
    scheme.description && scheme.description !== scheme.name && scheme.description !== shortTitle
      ? scheme.description
      : null;
  const highMatch = typeof scheme.score === "number" && scheme.score > 0.7;

  return (
    <article
      className={cn(
        "flex h-full flex-col rounded-2xl border border-border bg-card text-card-foreground transition-shadow hover:shadow-sm",
        compact ? "p-4" : "p-5 md:p-6",
      )}
    >
      {(scheme.category || shortTitle || highMatch) && (
        <div className="flex flex-wrap gap-2">
          {scheme.category && (
            <span className="rounded-full bg-secondary px-2.5 py-1 text-xs font-semibold capitalize text-primary">
              {scheme.category}
            </span>
          )}
          {shortTitle && (
            <span className="rounded-full border border-border px-2.5 py-1 text-xs font-semibold text-plum-soft">
              {shortTitle}
            </span>
          )}
          {highMatch && (
            <span className="inline-flex items-center gap-1 rounded-full bg-lime px-2.5 py-1 text-xs font-bold text-primary">
              <Sparkles aria-hidden="true" className="size-3" /> Strong match
            </span>
          )}
        </div>
      )}

      <h3
        className={cn(
          "font-display font-semibold leading-snug text-primary",
          compact ? "mt-3 text-base" : "mt-4 text-lg",
          !scheme.category && !shortTitle && !highMatch && "mt-0",
        )}
      >
        {scheme.name}
      </h3>
      {scheme.name_hi && scheme.name_hi !== scheme.name && (
        <p lang="hi" className="mt-1 text-sm text-muted-foreground">
          {scheme.name_hi}
        </p>
      )}
      {description && (
        <p className={cn("mt-2 text-muted-foreground", compact ? "text-xs leading-5" : "text-sm leading-6")}>
          {description}
        </p>
      )}

      <div className="mt-auto flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-t border-border pt-4 text-sm">
        {scheme.slug ? (
          <button
            type="button"
            onClick={() => setOpen(true)}
            aria-haspopup="dialog"
            className="inline-flex items-center gap-1.5 rounded-full bg-primary px-3.5 py-1.5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <FileText aria-hidden="true" className="size-3.5" /> Details
            <span className="sr-only"> for {scheme.name}: eligibility, benefits, how to apply</span>
          </button>
        ) : (
          <span className="text-muted-foreground">Official source</span>
        )}
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 font-semibold text-primary transition-colors hover:text-plum-soft"
          >
            Official site <ExternalLink aria-hidden="true" className="size-3.5" />
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        ) : (
          <span className="text-muted-foreground">Link unavailable</span>
        )}
      </div>
      {open && scheme.slug && (
        <SchemeDetailsDialog slug={scheme.slug} title={scheme.name} initialLang={lang} fallbackUrl={scheme.official_url} onClose={() => setOpen(false)} />
      )}
    </article>
  );
}
