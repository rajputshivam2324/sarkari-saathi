import { useId, type InputHTMLAttributes, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, AudioLines, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

type AuthLayoutProps = {
  eyebrow: string;
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
};

/** Two-panel auth shell: form on the left, plum "voice scene" panel on the right (hidden on small screens). */
export function AuthLayout({ eyebrow, title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="grid min-h-screen bg-background text-foreground lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <main className="flex flex-col px-5 py-6 sm:px-10 lg:px-16">
        <div className="flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3" aria-label="Sarkari Saathi home">
            <span className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <AudioLines aria-hidden="true" className="size-5" />
            </span>
            <span className="font-display text-lg font-semibold leading-tight">Sarkari Saathi</span>
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-muted-foreground transition-colors hover:text-primary"
          >
            <ArrowLeft aria-hidden="true" className="size-4" /> Back to home
          </Link>
        </div>

        <div className="flex flex-1 items-center py-12">
          <div className="mx-auto w-full max-w-[420px]">
            <p className="text-sm font-bold uppercase tracking-[0.12em] text-plum-soft">{eyebrow}</p>
            <h1 className="mt-3 font-display text-4xl font-semibold leading-tight text-primary md:text-[2.6rem]">
              {title}
            </h1>
            <p className="mt-3 text-base leading-7 text-muted-foreground">{subtitle}</p>

            <div className="mt-8">{children}</div>

            <div className="mt-8 border-t border-border pt-6 text-sm text-muted-foreground">{footer}</div>
          </div>
        </div>
      </main>

      <aside
        aria-hidden="true"
        className="relative isolate hidden overflow-hidden bg-primary text-primary-foreground lg:block"
      >
        <img
          src="/sarkari-saathi-community.jpg"
          alt=""
          width={1600}
          height={1200}
          className="absolute inset-0 -z-20 size-full object-cover object-[62%_45%]"
        />
        <div
          className="absolute inset-0 -z-10"
          style={{
            background:
              "linear-gradient(180deg, color-mix(in srgb, #462d43 30%, transparent), color-mix(in srgb, #462d43 88%, transparent) 78%)",
          }}
        />
        <div className="flex h-full flex-col justify-end p-14">
          <p className="text-sm font-bold text-lime">आपकी बात, आपकी भाषा</p>
          <p className="mt-3 max-w-md font-display text-4xl font-semibold leading-[1.1]">
            Start speaking.
            <br />
            We’re listening.
          </p>
          <p className="mt-4 max-w-sm text-base leading-7 text-white/85">
            Tell us about your family, work, or what you need help with. There’s no form to figure out.
          </p>
          <p className="mt-8 inline-flex w-fit items-center gap-2 rounded-full border border-white/30 bg-primary/60 px-4 py-2 text-xs font-medium">
            <ShieldCheck className="size-4 text-lime" /> Every match links to an official source
          </p>
        </div>
      </aside>
    </div>
  );
}

type FieldProps = InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string };

export function Field({ label, hint, className, id, ...props }: FieldProps) {
  const auto = useId();
  const inputId = id ?? auto;
  return (
    <div className="grid gap-1.5">
      <label htmlFor={inputId} className="text-sm font-semibold text-primary">
        {label}
      </label>
      <input
        id={inputId}
        aria-describedby={hint ? `${inputId}-hint` : undefined}
        className={cn(
          "h-12 w-full rounded-lg border border-border bg-card px-4 text-base text-foreground outline-none transition-shadow placeholder:text-muted-foreground focus:border-plum-soft focus:ring-4 focus:ring-plum-soft/15",
          className,
        )}
        {...props}
      />
      {hint && (
        <p id={`${inputId}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
    </div>
  );
}
