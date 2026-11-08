import { Link, NavLink } from "react-router-dom";
import { ArrowRight, AudioLines } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAuth } from "../auth";
import { AccountMenu } from "./AccountMenu";

const navClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "text-sm font-medium transition-colors hover:text-foreground",
    isActive ? "text-primary underline decoration-lime decoration-2 underline-offset-8" : "text-muted-foreground",
  );

/** Header for inner pages. Same visual language as the landing page header. */
export function SiteHeader() {
  const { token } = useAuth();

  return (
    <header className="relative z-10 border-b border-border/70 bg-background">
      <div className="mx-auto flex max-w-[1680px] flex-wrap items-center justify-between gap-x-3 gap-y-3 px-4 py-3 sm:gap-x-6 sm:px-5 md:h-[76px] md:flex-nowrap md:px-10 2xl:px-16 md:py-0">
        <Link to="/" className="flex items-center gap-3" aria-label="Sarkari Saathi home">
          <span className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <AudioLines aria-hidden="true" className="size-5" />
          </span>
          <span className="font-display text-lg font-semibold leading-tight">Sarkari Saathi</span>
        </Link>

        <nav
          aria-label="Main navigation"
          className="order-3 flex w-full items-center gap-6 border-t border-border/70 pt-3 md:order-none md:w-auto md:border-0 md:pt-0"
        >
          <NavLink to="/" end className={navClass}>
            Home
          </NavLink>
          <NavLink to="/schemes" className={navClass}>
            Schemes
          </NavLink>
          <NavLink to="/desk" className={navClass}>
            Voice desk
          </NavLink>
          {token && (
            <NavLink to="/history" className={navClass}>
              History
            </NavLink>
          )}
          {!token && (
            // On phones there is no room beside the brand, so "Log in" lives in this row.
            <Link
              to="/login"
              className="ml-auto text-sm font-semibold text-primary transition-colors hover:text-plum-soft sm:hidden"
            >
              Log in
            </Link>
          )}
        </nav>

        <div className="flex items-center gap-2 sm:gap-4">
          {token ? (
            <AccountMenu />
          ) : (
            <>
              <Link
                to="/login"
                className="hidden px-2 text-sm font-semibold text-primary transition-colors hover:text-plum-soft sm:inline"
              >
                Log in
              </Link>
              <Button asChild className="h-10 rounded-full px-4 sm:px-5">
                <Link to="/register">
                  <span className="sm:hidden">Get started</span>
                  <span className="hidden sm:inline">Meet your guide</span> <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-border px-5 py-7 md:px-10 2xl:px-16">
      <div className="mx-auto flex max-w-[1680px] flex-col gap-3 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <Link to="/" className="font-display font-semibold text-primary">
          Sarkari Saathi
        </Link>
        <span>Possible schemes are a starting point. Always confirm details with official sources.</span>
      </div>
    </footer>
  );
}
