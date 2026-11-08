import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Link, useLocation } from "react-router-dom";
import { ChevronDown, History, LayoutGrid, LogOut, Mic } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "../auth";

function initialsOf(label: string): string {
  const words = label.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return Array.from(words[0]).slice(0, 2).join("").toUpperCase();
  return (Array.from(words[0])[0] + Array.from(words[words.length - 1])[0]).toUpperCase();
}

const itemClass =
  "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium text-foreground outline-none transition-colors hover:bg-secondary focus-visible:bg-secondary";

/** Signed-in account control: avatar + dropdown with the user's destinations and Log out. */
export function AccountMenu({ className }: { className?: string }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const menuId = useId();

  const displayName = (user?.name || user?.username || "Account").trim();
  const initials = initialsOf(displayName);

  // Close when the route changes.
  useEffect(() => setOpen(false), [location.pathname, location.search]);

  // Close on outside press / Escape.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Move focus into the menu when it opens.
  useEffect(() => {
    if (open) menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
  }, [open]);

  function onMenuKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);
    if (items.length === 0) return;
    const i = items.indexOf(document.activeElement as HTMLElement);
    let next = -1;
    if (e.key === "ArrowDown") next = (i + 1) % items.length;
    else if (e.key === "ArrowUp") next = (i - 1 + items.length) % items.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = items.length - 1;
    else if (e.key === "Tab") {
      setOpen(false);
      return;
    }
    if (next >= 0) {
      e.preventDefault();
      items[next].focus();
    }
  }

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={`Account menu for ${displayName}`}
        onClick={() => setOpen((v) => !v)}
        className="flex h-10 items-center gap-2 rounded-full border border-border bg-card py-1 pl-1 pr-2 text-foreground transition-colors hover:border-primary/40 hover:bg-secondary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-plum-soft sm:pr-3"
      >
        <span
          aria-hidden="true"
          className="flex size-8 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground"
        >
          {initials}
        </span>
        <span className="hidden max-w-[120px] truncate text-sm font-semibold sm:inline">{displayName}</span>
        <ChevronDown aria-hidden="true" className={cn("size-4 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div
          ref={menuRef}
          id={menuId}
          role="menu"
          aria-label="Account"
          onKeyDown={onMenuKeyDown}
          className="absolute right-0 top-full z-50 mt-2 w-64 rounded-xl border border-border bg-card p-1.5 text-left shadow-lg"
        >
          <div className="border-b border-border px-3 pb-3 pt-2" role="none">
            <p className="truncate text-sm font-semibold text-primary">{displayName}</p>
            {user?.username && <p className="truncate text-xs text-muted-foreground">@{user.username}</p>}
          </div>
          <div className="py-1.5" role="none">
            <Link to="/desk" role="menuitem" className={itemClass}>
              <Mic aria-hidden="true" className="size-4 text-plum-soft" /> Voice desk
            </Link>
            <Link to="/history" role="menuitem" className={itemClass}>
              <History aria-hidden="true" className="size-4 text-plum-soft" /> Conversation history
            </Link>
            <Link to="/schemes" role="menuitem" className={itemClass}>
              <LayoutGrid aria-hidden="true" className="size-4 text-plum-soft" /> Browse schemes
            </Link>
          </div>
          <div className="border-t border-border pt-1.5" role="none">
            <button
              type="button"
              role="menuitem"
              className={itemClass}
              onClick={() => {
                setOpen(false);
                logout();
              }}
            >
              <LogOut aria-hidden="true" className="size-4 text-plum-soft" /> Log out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
