import { ExternalLink, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SchemeItem {
  id: string;
  name: string;
  name_hi?: string | null;
  official_url: string;
  description?: string | null;
  category?: string | null;
  short_title?: string | null;
  score?: number | null;
}

interface SchemeCardProps {
  scheme: SchemeItem;
  /** Tighter spacing for narrow side panels. */
  compact?: boolean;
}

/** Only http(s) links are rendered as links, so a bad data row can never produce a javascript: URL. */
function safeUrl(url: string | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : null;
  } catch {
    return null;
  }
}

export function SchemeCard({ scheme, compact = false }: SchemeCardProps) {
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

      <div className="mt-auto flex items-center justify-between gap-3 border-t border-border pt-4 text-sm">
        <span className="text-muted-foreground">Official source</span>
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 font-semibold text-primary transition-colors hover:text-plum-soft"
          >
            Open scheme <ExternalLink aria-hidden="true" className="size-3.5" />
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        ) : (
          <span className="text-muted-foreground">Link unavailable</span>
        )}
      </div>
    </article>
  );
}
