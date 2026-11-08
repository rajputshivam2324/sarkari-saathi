import { Link } from "react-router-dom";
import {
  ArrowDown,
  ArrowRight,
  AudioLines,
  Check,
  Globe2,
  Headphones,
  Mic2,
  ShieldCheck,
  Volume2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "../auth";
import { AccountMenu } from "../components/AccountMenu";
import { usePageTitle } from "../lib/usePageTitle";

export function LandingPage() {
  usePageTitle();
  const { token } = useAuth();
  const deskHref = token ? "/desk" : "/register";

  const languages = [
    "हिन्दी",
    "English",
    "Hinglish",
    "தமிழ்",
    "తెలుగు",
    "ಕನ್ನಡ",
    "मराठी",
    "বাংলা",
    "ગુજરાતી",
    "ਪੰਜਾਬੀ",
  ];

  return (
    <main className="min-h-screen overflow-hidden bg-background text-foreground">
      {/* ── Header ── */}
      <header className="relative z-10 border-b border-border/70">
        <div className="mx-auto flex h-[76px] max-w-[1680px] items-center justify-between px-5 md:px-10 2xl:px-16">
          <a
            href="#top"
            className="flex items-center gap-3"
            aria-label="Sarkari Saathi home"
          >
            <span className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <AudioLines aria-hidden="true" className="size-5" />
            </span>
            <span className="font-display text-lg font-semibold leading-tight">
              Sarkari Saathi
            </span>
          </a>
          <nav
            aria-label="Main navigation"
            className="hidden items-center gap-8 md:flex"
          >
            <a
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
              href="#how-it-works"
            >
              How it works
            </a>
            <a
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
              href="#languages"
            >
              Languages
            </a>
            <a
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
              href="#trust"
            >
              Our approach
            </a>
            <Link
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
              to="/schemes"
            >
              Schemes
            </Link>
          </nav>
          <div className="flex items-center gap-2 sm:gap-4">
            {token ? (
              <>
                <Button asChild className="hidden h-10 rounded-full px-5 md:inline-flex">
                  <Link to="/desk">
                    Start conversation <ArrowRight aria-hidden="true" />
                  </Link>
                </Button>
                <AccountMenu />
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  className="px-2 text-sm font-semibold text-primary transition-colors hover:text-plum-soft"
                >
                  Log in
                </Link>
                <Button asChild className="h-10 rounded-full px-5">
                  <Link to="/register">
                    Meet your guide <ArrowRight aria-hidden="true" />
                  </Link>
                </Button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* ── Hero ── */}
      <section
        id="top"
        className="relative isolate min-h-[690px] overflow-hidden md:min-h-[730px]"
      >
        <img
          src="/sarkari-saathi-community.jpg"
          alt="A community worker helping an older woman explore information on a phone"
          width={1600}
          height={1200}
          fetchPriority="high"
          className="absolute inset-0 -z-20 size-full object-cover object-[62%_center] md:object-center"
        />
        <div className="absolute inset-0 -z-10 bg-hero-wash" />
        <div className="mx-auto flex min-h-[690px] max-w-[1680px] items-center px-5 py-16 md:min-h-[730px] md:px-10 2xl:px-16">
          <div className="max-w-[610px]">
            <p className="mb-7 inline-flex items-center gap-2 rounded-full border border-primary/15 bg-background/90 px-4 py-2 text-xs font-semibold text-primary shadow-sm">
              <span className="size-2 rounded-full bg-lime" />A simpler way to
              find public support
            </p>
            <h1 className="font-display text-5xl font-semibold leading-[1.04] tracking-normal text-primary sm:text-6xl md:text-7xl">
              Your voice can open the right doors.
            </h1>
            <p className="mt-6 max-w-[510px] text-lg leading-8 text-foreground/80 md:text-xl">
              Talk naturally in your language. Discover government schemes you
              may qualify for—with clear next steps, not complicated forms.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Button asChild size="lg" className="h-12 rounded-full px-6 text-base">
                <Link to={deskHref}>
                  Start conversation <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
              <a
                href="#trust"
                className="inline-flex h-12 items-center gap-2 px-4 text-sm font-semibold text-primary transition-colors hover:text-plum-soft"
              >
                Built for real conversations{" "}
                <ArrowDown aria-hidden="true" className="size-4" />
              </a>
            </div>
            <div className="mt-12 flex flex-wrap items-center gap-x-7 gap-y-3 text-sm font-medium text-primary">
              <span className="inline-flex items-center gap-2">
                <Mic2 aria-hidden="true" className="size-4" /> Voice-first
              </span>
              <span className="inline-flex items-center gap-2">
                <Globe2 aria-hidden="true" className="size-4" /> 10 language
                options
              </span>
              <span className="inline-flex items-center gap-2">
                <ShieldCheck aria-hidden="true" className="size-4" /> Official
                sources
              </span>
            </div>
          </div>
        </div>
        <div className="absolute bottom-5 right-6 hidden items-center gap-2 rounded-full border border-border/70 bg-background/90 px-4 py-2 text-xs font-medium text-foreground shadow-sm lg:flex">
          <Volume2 aria-hidden="true" className="size-4 text-primary" /> Listen.
          Understand. Take the next step.
        </div>
      </section>

      {/* ── Language bar ── */}
      <section className="border-y border-border bg-secondary/60">
        <div className="mx-auto grid max-w-[1680px] gap-8 px-5 py-8 md:grid-cols-[1fr_auto_1fr] md:items-center md:px-10 2xl:px-16 md:py-9">
          <div>
            <p className="font-display text-2xl font-semibold text-primary">
              Support should sound familiar.
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              A first guide to benefits that can be hard to find.
            </p>
          </div>
          <span className="hidden h-12 w-px bg-border md:block" />
          <div
            className="flex flex-wrap gap-2"
            aria-label="Available language options"
          >
            {languages.slice(0, 6).map((language) => (
              <span
                key={language}
                className="rounded-full border border-border bg-background px-3 py-1.5 text-sm font-medium text-primary"
              >
                {language}
              </span>
            ))}
            <a
              href="#languages"
              className="inline-flex items-center gap-1 px-2 text-sm font-semibold text-primary hover:text-plum-soft"
            >
              + 4 more <ArrowRight aria-hidden="true" className="size-3.5" />
            </a>
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section
        id="how-it-works"
        className="scroll-mt-10 px-5 py-24 md:px-10 2xl:px-16 md:py-32"
      >
        <div className="mx-auto max-w-[1680px]">
          <div className="max-w-2xl">
            <p className="text-sm font-bold uppercase tracking-[0.12em] text-plum-soft">
              A conversation, not a form
            </p>
            <h2 className="mt-4 font-display text-4xl font-semibold leading-tight text-primary md:text-5xl">
              A few simple questions. A clearer next step.
            </h2>
            <p className="mt-5 text-lg leading-8 text-muted-foreground">
              Start with what you want to share. Sarkari Saathi guides you one
              question at a time, then points you toward the official details.
            </p>
          </div>
          <div className="mt-14 grid gap-0 border-t border-border md:grid-cols-3">
            <article className="border-b border-border py-8 md:border-b-0 md:pr-10 md:py-10">
              <span className="font-display text-sm font-semibold text-plum-soft">
                01 / SAY HELLO
              </span>
              <h3 className="mt-5 font-display text-2xl font-semibold text-primary">
                Choose your language
              </h3>
              <p className="mt-3 leading-7 text-muted-foreground">
                Tap the microphone and speak about yourself—your age, work, or
                family, in your own words.
              </p>
              <div className="mt-7 flex size-12 items-center justify-center rounded-full bg-secondary text-primary">
                <Mic2 aria-hidden="true" />
              </div>
            </article>
            <article className="border-b border-border py-8 md:border-b-0 md:border-l md:px-10 2xl:px-16 md:py-10">
              <span className="font-display text-sm font-semibold text-plum-soft">
                02 / TALK IT THROUGH
              </span>
              <h3 className="mt-5 font-display text-2xl font-semibold text-primary">
                Answer one thing at a time
              </h3>
              <p className="mt-3 leading-7 text-muted-foreground">
                Hear simple follow-up questions. Most ask for a yes, no, or a
                single number.
              </p>
              <div className="mt-7 flex size-12 items-center justify-center rounded-full bg-secondary text-primary">
                <Headphones aria-hidden="true" />
              </div>
            </article>
            <article className="py-8 md:border-l md:pl-10 md:py-10">
              <span className="font-display text-sm font-semibold text-plum-soft">
                03 / FIND YOUR WAY
              </span>
              <h3 className="mt-5 font-display text-2xl font-semibold text-primary">
                See possible schemes
              </h3>
              <p className="mt-3 leading-7 text-muted-foreground">
                Review a first guide on screen, then follow links to official
                websites or ask a nearby Common Service Centre.
              </p>
              <div className="mt-7 flex size-12 items-center justify-center rounded-full bg-secondary text-primary">
                <ArrowRight aria-hidden="true" />
              </div>
            </article>
          </div>
          <div className="mt-8 flex flex-wrap items-center gap-2 border-l-2 border-lime pl-5 text-sm text-muted-foreground">
            <span className="font-semibold text-primary">
              Voice technology by Gnani:
            </span>
            <span>
              Prisma understands speech; Timbre speaks the conversation back.
            </span>
          </div>
        </div>
      </section>

      {/* ── Languages section ── */}
      <section
        id="languages"
        className="scroll-mt-10 bg-primary py-20 text-primary-foreground md:py-24"
      >
        <div className="mx-auto grid max-w-[1680px] gap-12 px-5 md:grid-cols-[0.85fr_1.15fr] md:items-start md:px-10 2xl:px-16">
          <div>
            <p className="text-sm font-bold uppercase tracking-[0.12em] text-lime">
              Made to meet you where you are
            </p>
            <h2 className="mt-4 font-display text-4xl font-semibold leading-tight md:text-5xl">
              Start in the language that feels like yours.
            </h2>
            <p className="mt-5 max-w-md text-base leading-7 text-primary-foreground/75">
              Choose from 10 language options. In every language, the guide keeps
              questions simple and shows scheme details on screen.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-x-5 gap-y-0 sm:grid-cols-3">
            {languages.map((language, index) => (
              <div
                key={language}
                className="flex items-center gap-3 border-b border-primary-foreground/20 py-4"
              >
                <span className="text-xs font-medium text-lime">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="text-lg font-medium">{language}</span>
              </div>
            ))}
            <p className="col-span-full mt-5 text-sm leading-6 text-primary-foreground/65">
              Free-form speech works best in Hindi, English, and Hinglish. For
              other languages, the guide relies on short, spoken questions.
            </p>
          </div>
        </div>
      </section>

      {/* ── Trust / Our approach ── */}
      <section
        id="trust"
        className="scroll-mt-10 px-5 py-24 md:px-10 2xl:px-16 md:py-32"
      >
        <div className="mx-auto max-w-[1680px]">
          <div className="grid gap-12 md:grid-cols-[0.8fr_1.2fr] md:items-start">
            <div>
              <p className="text-sm font-bold uppercase tracking-[0.12em] text-plum-soft">
                A guide, not a gatekeeper
              </p>
              <h2 className="mt-4 font-display text-4xl font-semibold leading-tight text-primary md:text-5xl">
                Helpful guidance. Honest limits.
              </h2>
            </div>
            <div className="grid gap-7 sm:grid-cols-2">
              <article className="border-t-2 border-lime pt-5">
                <Check aria-hidden="true" className="size-5 text-plum-soft" />
                <h3 className="mt-4 font-display text-xl font-semibold text-primary">
                  A first guide, not a decision
                </h3>
                <p className="mt-2 leading-7 text-muted-foreground">
                  The app never decides whether you are eligible. Confirm
                  requirements with the official scheme or a local service
                  centre.
                </p>
              </article>
              <article className="border-t-2 border-lime pt-5">
                <Check aria-hidden="true" className="size-5 text-plum-soft" />
                <h3 className="mt-4 font-display text-xl font-semibold text-primary">
                  Designed for everyday conditions
                </h3>
                <p className="mt-2 leading-7 text-muted-foreground">
                  Short answers and a phone-line mode are designed for noisy
                  places and phone-quality audio.
                </p>
              </article>
              <article className="border-t-2 border-lime pt-5">
                <Check aria-hidden="true" className="size-5 text-plum-soft" />
                <h3 className="mt-4 font-display text-xl font-semibold text-primary">
                  Official details are one step away
                </h3>
                <p className="mt-2 leading-7 text-muted-foreground">
                  Every possible match points back to an official website and
                  help from a nearby Common Service Centre.
                </p>
              </article>
              <article className="border-t-2 border-lime pt-5">
                <Check aria-hidden="true" className="size-5 text-plum-soft" />
                <h3 className="mt-4 font-display text-xl font-semibold text-primary">
                  Made for the people beside you
                </h3>
                <p className="mt-2 leading-7 text-muted-foreground">
                  A practical guide for first-time smartphone users, older
                  adults, and the workers who support them.
                </p>
              </article>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA Banner ── */}
      <section className="px-5 pb-20 md:px-10 2xl:px-16 md:pb-24">
        <div className="mx-auto flex max-w-[1680px] flex-col gap-7 rounded-2xl bg-lime p-7 sm:p-10 md:flex-row md:items-center md:justify-between md:p-14">
          <div className="max-w-2xl">
            <p className="text-sm font-bold uppercase tracking-[0.12em] text-primary/70">
              The right conversation can make a difference
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold leading-tight text-primary md:text-4xl">
              Make the next step easier to find.
            </h2>
          </div>
          <Button
            asChild
            variant="secondary"
            size="lg"
            className="h-12 shrink-0 rounded-full px-6"
          >
            <Link to={deskHref}>
              Start conversation <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-border px-5 py-7 md:px-10 2xl:px-16">
        <div className="mx-auto flex max-w-[1680px] flex-col gap-3 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <span className="font-display font-semibold text-primary">
            Sarkari Saathi
          </span>
          <span>
            Possible schemes are a starting point. Always confirm details with
            official sources.
          </span>
        </div>
      </footer>
    </main>
  );
}
