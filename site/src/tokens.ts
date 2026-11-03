/**
 * Linevora design tokens — the bone / ink / signal identity is preserved.
 * Corporate discipline: thin borders instead of shadows, a 4/8 spacing grid, sans hierarchy.
 * Serif (Instrument Serif) is used only for the brand signature.
 */

export const T = {
  /* Surface tiers */
  bone: "#ecebe4",
  paper: "#f6f5ef",
  white: "#ffffff",
  surfaceApp: "#ecebe4",
  surfaceCard: "#f6f5ef",
  surfaceRaised: "#ffffff",
  surfaceSunken: "#e3e1d8",
  surfaceInverse: "#0e0f10",
  surfaceInverseSoft: "#232422",

  /* Text tiers */
  ink: "#0e0f10",
  inkSoft: "#2d2e2c",
  inkSecondary: "#3a3b38",
  mute: "#6d6e68",
  faint: "#8a8b84",
  textInverse: "#ecebe4",
  textInverseMuted: "#9a9b93",
  textOnSignal: "#0e0f10",

  /* Rules / border discipline */
  rule: "#cfcdc3",
  ruleStrong: "#0e0f10",
  ruleSoft: "#e0ded4",
  ruleInverse: "#3a3b37",

  /* Brand */
  signal: "#ff5a1f",
  signalHover: "#e64a12",
  signalSoft: "rgba(255,90,31,.14)",
  signalInk: "#7a2400",

  /* Status colors */
  ok: "#1f7a4d",
  success: "#1f7a4d",
  successBg: "#d7f0dd",
  successInk: "#14532d",
  warn: "#8a5a00",
  warnBg: "#fbeecb",
  warnInk: "#5c3d00",
  danger: "#8f1d16",
  dangerBg: "#f9dcd9",
  dangerInk: "#7f1d1d",
  bad: "#8f1d16",
  info: "#1d4e6b",
  infoBg: "#d8e5f3",
  infoInk: "#163a52",
  neutralBg: "#e5e8ec",
  neutralInk: "#3a3b38",

  /* Focus */
  focus: "#ff5a1f",
  focusWidth: "2px",
  focusOffset: "2px",

  /* Typography — serif only for the brand signature */
  serif: "'Instrument Serif', 'Times New Roman', serif",
  sans: "'Inter Tight', system-ui, sans-serif",
  mono: "'JetBrains Mono', ui-monospace, monospace",
} as const;

/** 4/8 spacing grid (px) */
export const SPACE = {
  0: 0, 1: 4, 2: 8, 3: 12, 4: 16, 5: 20, 6: 24, 8: 32, 10: 40, 12: 48, 16: 64,
} as const;

/** Type scale — corporate sans hierarchy */
export const TYPE = {
  display: { fontFamily: T.sans, fontSize: 28, lineHeight: 1.15, fontWeight: 600, letterSpacing: "-0.02em" },
  h1: { fontFamily: T.sans, fontSize: 22, lineHeight: 1.2, fontWeight: 600, letterSpacing: "-0.015em" },
  h2: { fontFamily: T.sans, fontSize: 17, lineHeight: 1.3, fontWeight: 600, letterSpacing: "-0.01em" },
  h3: { fontFamily: T.sans, fontSize: 15, lineHeight: 1.4, fontWeight: 600, letterSpacing: "-0.005em" },
  body: { fontFamily: T.sans, fontSize: 15, lineHeight: 1.5, fontWeight: 400 },
  bodySm: { fontFamily: T.sans, fontSize: 13.5, lineHeight: 1.5, fontWeight: 400 },
  label: { fontFamily: T.mono, fontSize: 11, lineHeight: 1.4, fontWeight: 500, letterSpacing: ".08em", textTransform: "uppercase" as const },
  caption: { fontFamily: T.sans, fontSize: 12.5, lineHeight: 1.45, fontWeight: 400 },
  mono: { fontFamily: T.mono, fontSize: 12.5, lineHeight: 1.5, fontWeight: 400 },
} as const;

export type StatusTone = "neutral" | "info" | "success" | "warn" | "danger" | "signal";

/**
 * Meaningful status mapping — listing / offer / quote / job statuses.
 * Keys are the raw values produced by the backend.
 */
export const STATUS_TONE: Record<string, StatusTone> = {
  draft: "neutral",
  published: "info",
  submitted: "info", in_review: "info",
  awarded: "success", selected: "success",
  approved: "success", exported: "success", active: "success",
  done: "success", answered: "success", running: "info",
  revision_requested: "warn", pending: "warn", open: "warn", queued: "warn",
  mandatory: "danger",
  closed: "neutral", archived: "neutral",
  rejected: "danger", failed: "danger",
  withdrawn: "neutral", waived: "neutral", info: "neutral",
  added: "info", removed: "danger", changed: "warn", corrected: "info",
};

/** Label shown in the badge (the raw value is preserved; only presentation is formatted). */
export const STATUS_LABEL: Record<string, string> = {
  draft: "Draft", published: "Published", awarded: "Awarded", closed: "Closed",
  submitted: "Submitted", revision_requested: "Revision requested", selected: "Selected",
  rejected: "Rejected", withdrawn: "Withdrawn",
  queued: "Queued", running: "Running", done: "Done", failed: "Failed",
  open: "Open", pending: "Pending", in_review: "In review", approved: "Approved",
  exported: "Exported", active: "Active", archived: "Archived",
  answered: "Answered", waived: "Waived", mandatory: "Mandatory", info: "Info",
  added: "Added", removed: "Removed", changed: "Changed", corrected: "Corrected",
};

export function statusTone(status: string): StatusTone {
  return STATUS_TONE[status] ?? STATUS_TONE[status.toLocaleLowerCase("en")] ?? "neutral";
}
export function statusLabel(status: string): string {
  return STATUS_LABEL[status] ?? status;
}

export const PANEL_URL: string =
  (import.meta.env.VITE_PANEL_URL as string | undefined) ?? "/panel";
