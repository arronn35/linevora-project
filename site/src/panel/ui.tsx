import type { ReactNode } from "react";
import { statusLabel, statusTone } from "../tokens";

const PILL: Record<string, string> = {
  "taslak": "pill-gray", "açık": "pill-amber", "bekliyor": "pill-amber", "incelemede": "pill-blue",
  "onaylandı": "pill-green", "dışa aktarıldı": "pill-teal", "yürürlükte": "pill-green",
  "arşiv": "pill-gray", "zorunlu": "pill-red", "bilgi": "pill-gray",
  "queued": "pill-amber", "running": "pill-blue", "done": "pill-green", "failed": "pill-red",
  "reddedildi": "pill-red", "yanıtlandı": "pill-green", "vazgeçildi": "pill-gray",
  /* Pazar yeri (EN ham değerler) */
  "draft": "pill-gray", "published": "pill-blue", "awarded": "pill-green", "closed": "pill-gray",
  "submitted": "pill-blue", "revision_requested": "pill-amber", "selected": "pill-green",
  "rejected": "pill-red", "withdrawn": "pill-gray",
  "yayında": "pill-blue", "revize istendi": "pill-amber", "seçildi": "pill-green", "kapandı": "pill-gray",
};

const TONE_PILL: Record<string, string> = {
  neutral: "pill-gray", info: "pill-blue", success: "pill-green", warn: "pill-amber", danger: "pill-red", signal: "pill-amber",
};

export function Pill({ t }: { t: string }) {
  const cls = PILL[t] ?? TONE_PILL[statusTone(t)] ?? "pill-gray";
  return <span className={`p-pill ${cls}`}>{t}</span>;
}

/** Anlamlı durum rozeti: taslak=nötr, yayında=info, revize istendi=uyarı, seçildi=başarı, kapandı=nötr. */
export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const tone = statusTone(status);
  return (
    <span className={`p-badge tone-${tone}`} data-status={status} aria-label={`Durum: ${label ?? statusLabel(status)}`}>
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

export function Skeleton({ lines = 3, label = "Yükleniyor" }: { lines?: number; label?: string }) {
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
  const labels = ["Talep", "Dosya", "İşleme", "Teklif", "Onay ve gönderi"];
  const firstOpen = done.findIndex((d) => !d);
  return (
    <div className="p-steps">
      {labels.map((l, i) => (
        <span key={l} className={`p-step${done[i] ? " done" : i === firstOpen ? " active" : ""}`}>{i + 1}. {l}</span>
      )).reduce<ReactNode[]>((acc, el, i) => (i === 0 ? [el] : [...acc, <span key={`a${i}`} className="p-muted">→</span>, el]), [])}
    </div>
  );
}
