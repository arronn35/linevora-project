import type { ReactNode } from "react";
import { statusLabel, statusTone } from "../tokens";

const PILL: Record<string, string> = {
  "draft": "pill-gray", "open": "pill-amber", "pending": "pill-amber", "in_review": "pill-blue",
  "approved": "pill-green", "exported": "pill-teal", "active": "pill-green",
  "archived": "pill-gray", "mandatory": "pill-red", "info": "pill-gray",
  "queued": "pill-amber", "running": "pill-blue", "done": "pill-green", "failed": "pill-red",
  "rejected": "pill-red", "answered": "pill-green", "waived": "pill-gray",
  "published": "pill-blue", "awarded": "pill-green", "closed": "pill-gray",
  "submitted": "pill-blue", "revision_requested": "pill-amber", "selected": "pill-green",
  "withdrawn": "pill-gray",
  "added": "pill-blue", "removed": "pill-red", "changed": "pill-amber", "corrected": "pill-blue",
};

const TONE_PILL: Record<string, string> = {
  neutral: "pill-gray", info: "pill-blue", success: "pill-green", warn: "pill-amber", danger: "pill-red", signal: "pill-amber",
};

export function Pill({ t }: { t: string }) {
  const cls = PILL[t] ?? TONE_PILL[statusTone(t)] ?? "pill-gray";
  return <span className={`p-pill ${cls}`}>{statusLabel(t)}</span>;
}

/** Meaningful status badge: draft=neutral, published=info, revision requested=warning, selected=success, closed=neutral. */
export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const tone = statusTone(status);
  return (
    <span className={`p-badge tone-${tone}`} data-status={status} aria-label={`Status: ${label ?? statusLabel(status)}`}>
      {label ?? statusLabel(status)}
    </span>
  );
}

export function PageHeader({ title, desc, actions }: { title: string; desc?: string; actions?: ReactNode }) {
  return (
    <div className="p-pagehead">
      <div>
        <h1>{title}</h1>
        {desc ? <p className="p-pagedesc">{desc}</p> : null}
      </div>
      {actions ? <div className="p-pagehead-actions">{actions}</div> : null}
    </div>
  );
}

export function EmptyState({ title, desc, action }: { title: string; desc?: string; action?: ReactNode }) {
  return (
    <div className="p-empty">
      <h3>{title}</h3>
      {desc ? <p>{desc}</p> : null}
      {action}
    </div>
  );
}

export function Skeleton({ lines = 3, label = "Loading" }: { lines?: number; label?: string }) {
  return (
    <div className="p-skeleton" role="status" aria-label={label} aria-busy="true">
      <span className="p-skeleton-line short" />
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className={`p-skeleton-line${i % 2 ? " med" : ""}`} />
      ))}
    </div>
  );
}

export function Hint({ children }: { children: ReactNode }) {
  return <div className="p-hint">{children}</div>;
}
export function Banner({ msg, kind }: { msg: string | null; kind?: "ok" | "err" }) {
  if (!msg) return null;
  return <div className={`p-banner${kind === "ok" ? " ok" : ""}`} role="alert">{msg}</div>;
}
export function Steps({ done }: { done: boolean[] }) {
  const labels = ["Inquiry", "File", "Processing", "Quote", "Approval & sending"];
  const firstOpen = done.findIndex((d) => !d);
  return (
    <div className="p-steps">
      {labels.map((l, i) => (
        <span key={l} className={`p-step${done[i] ? " done" : i === firstOpen ? " active" : ""}`}>{i + 1}. {l}</span>
      )).reduce<ReactNode[]>((acc, el, i) => (i === 0 ? [el] : [...acc, <span key={`a${i}`} className="p-muted">→</span>, el]), [])}
    </div>
  );
}
