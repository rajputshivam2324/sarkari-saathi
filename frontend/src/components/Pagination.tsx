import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

type PaginationProps = {
  /** Current page, 1-based. */
  page: number;
  totalPages: number;
  /** Link mode: URL for a page (used for shareable, crawlable, back-button-friendly pagination). */
  hrefFor?: (page: number) => string;
  /** Button mode: callback for local (in-memory) pagination. */
  onPageChange?: (page: number) => void;
  className?: string;
  /** Compact variant for narrow panels (prev / "x of y" / next). */
  compact?: boolean;
  label?: string;
};

/** Returns page numbers with `null` marking an ellipsis, e.g. [1, null, 6, 7, 8, null, 99]. */
export function pageWindow(page: number, totalPages: number): (number | null)[] {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
  const out: (number | null)[] = [1];
  const start = Math.max(2, page - 1);
  const end = Math.min(totalPages - 1, page + 1);
  if (start > 2) out.push(null);
  for (let p = start; p <= end; p++) out.push(p);
  if (end < totalPages - 1) out.push(null);
  out.push(totalPages);
  return out;
}

const base =
  "inline-flex h-10 min-w-10 items-center justify-center rounded-full border px-3 text-sm font-semibold transition-colors";
const idle = "border-border bg-card text-primary hover:border-primary/40 hover:bg-secondary";
const current = "border-primary bg-primary text-primary-foreground";
const disabled = "pointer-events-none border-border bg-transparent text-muted-foreground/50";

export function Pagination({
  page,
  totalPages,
  hrefFor,
  onPageChange,
  className,
  compact = false,
  label = "Pagination",
}: PaginationProps) {
  if (totalPages <= 1) return null;

  const prev = page - 1;
  const next = page + 1;
  const hasPrev = prev >= 1;
  const hasNext = next <= totalPages;

  function item(target: number, content: React.ReactNode, cls: string, ariaLabel: string, isDisabled = false) {
    const aria = { "aria-label": ariaLabel };
    if (isDisabled) {
      return (
        <span {...aria} aria-disabled="true" className={cn(base, cls)}>
          {content}
        </span>
      );
    }
    if (hrefFor) {
      return (
        <Link {...aria} to={hrefFor(target)} className={cn(base, cls)}>
          {content}
        </Link>
      );
    }
    return (
      <button type="button" {...aria} onClick={() => onPageChange?.(target)} className={cn(base, cls)}>
        {content}
      </button>
    );
  }

  return (
    <nav aria-label={label} className={cn("flex flex-wrap items-center justify-center gap-2", className)}>
      {item(prev, <ChevronLeft aria-hidden="true" className="size-4" />, hasPrev ? idle : disabled, "Previous page", !hasPrev)}

      {compact ? (
        <span className="px-2 text-sm font-medium text-muted-foreground" aria-live="polite">
          Page {page} of {totalPages}
        </span>
      ) : (
        pageWindow(page, totalPages).map((p, i) =>
          p === null ? (
            <span key={`gap-${i}`} aria-hidden="true" className="px-1 text-muted-foreground">
              …
            </span>
          ) : p === page ? (
            <span key={p} aria-current="page" aria-label={`Page ${p}, current page`} className={cn(base, current)}>
              {p}
            </span>
          ) : (
            <span key={p}>{item(p, p, idle, `Go to page ${p}`)}</span>
          ),
        )
      )}

      {item(next, <ChevronRight aria-hidden="true" className="size-4" />, hasNext ? idle : disabled, "Next page", !hasNext)}
    </nav>
  );
}
