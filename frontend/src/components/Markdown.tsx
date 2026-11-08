import { Fragment, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { safeUrl } from "../lib/safeUrl";

/**
 * Renders the small markdown subset that myScheme uses (bold, links, bullet and numbered lists,
 * quotes, one step per line). It builds React elements directly and never injects HTML, so
 * third-party text cannot run script or inject markup.
 */

const TOKEN = /(\*\*[^*]+\*\*|\[[^\]]+\]\([^)\s]+(?:\s+"[^"]*")?\))/g;
const LINK = /^\[([^\]]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)$/;

function inline(text: string): ReactNode[] {
  return text.split(TOKEN).map((part, i) => {
    if (!part) return null;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return (
        <strong key={i} className="font-semibold text-primary">
          {part.slice(2, -2)}
        </strong>
      );
    }
    const m = LINK.exec(part);
    if (m) {
      const href = safeUrl(m[2]);
      return href ? (
        <a
          key={i}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-plum-soft underline underline-offset-2 hover:text-primary"
        >
          {m[1]}
        </a>
      ) : (
        <Fragment key={i}>{m[1]}</Fragment>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

type Block =
  | { kind: "p"; text: string }
  | { kind: "quote"; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] };

function parse(md: string): Block[] {
  const blocks: Block[] = [];
  for (const raw of md.replace(/\r/g, "").split("\n")) {
    const line = raw.trimEnd();
    if (!line.trim()) continue;
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d{1,2}[.)]\s+(.*)$/.exec(line);
    const quote = /^\s*>\s?(.*)$/.exec(line);
    const last = blocks[blocks.length - 1];
    if (bullet) {
      if (last?.kind === "ul") last.items.push(bullet[1]);
      else blocks.push({ kind: "ul", items: [bullet[1]] });
    } else if (numbered) {
      if (last?.kind === "ol") last.items.push(numbered[1]);
      else blocks.push({ kind: "ol", items: [numbered[1]] });
    } else if (quote) {
      blocks.push({ kind: "quote", text: quote[1] });
    } else {
      blocks.push({ kind: "p", text: line.trim() });
    }
  }
  return blocks;
}

export function Markdown({ text, className }: { text: string; className?: string }) {
  const blocks = parse(text || "");
  if (blocks.length === 0) return null;
  return (
    <div className={cn("space-y-2.5 text-[15px] leading-7 text-foreground/90", className)}>
      {blocks.map((b, i) => {
        if (b.kind === "ul" || b.kind === "ol") {
          const List = b.kind === "ul" ? "ul" : "ol";
          return (
            <List key={i} className={cn("space-y-1.5 pl-5", b.kind === "ul" ? "list-disc" : "list-decimal")}>
              {b.items.map((it, j) => (
                <li key={j} className="pl-1 marker:text-plum-soft">
                  {inline(it)}
                </li>
              ))}
            </List>
          );
        }
        if (b.kind === "quote") {
          return (
            <p key={i} className="rounded-lg border-l-4 border-lime bg-secondary/70 px-3 py-2 text-sm">
              {inline(b.text)}
            </p>
          );
        }
        return <p key={i}>{inline(b.text)}</p>;
      })}
    </div>
  );
}
