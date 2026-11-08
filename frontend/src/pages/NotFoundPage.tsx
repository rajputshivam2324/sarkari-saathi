import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SiteFooter, SiteHeader } from "../components/SiteChrome";
import { usePageTitle } from "../lib/usePageTitle";

export function NotFoundPage() {
  usePageTitle("Page not found");

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <SiteHeader />
      <main className="flex flex-1 items-center justify-center px-5 py-20">
        <div className="max-w-md text-center">
          <p className="text-sm font-bold uppercase tracking-[0.12em] text-plum-soft">Error 404</p>
          <h1 className="mt-4 font-display text-5xl font-semibold leading-tight text-primary md:text-6xl">
            This page isn’t here.
          </h1>
          <p className="mt-5 text-lg leading-8 text-muted-foreground">
            The link may be old or mistyped. You can go back home or browse the scheme list.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button asChild size="lg" className="h-12 rounded-full px-6 text-base">
              <Link to="/">Go home</Link>
            </Button>
            <Button asChild variant="secondary" size="lg" className="h-12 rounded-full px-6 text-base">
              <Link to="/schemes">
                Browse schemes <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
          </div>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
