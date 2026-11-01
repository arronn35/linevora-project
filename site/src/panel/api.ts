/* Linevora API istemcisi — /v1 yüzeyi, belirteç localStorage'da tutulur. */

export type Role = "admin" | "specialist" | "viewer";

export interface User { username: string; roles: string[] }
export interface Inquiry { id: string; customer: string; title: string; status: string; created_by: string }
export interface Page { number: number; text: string }
export interface Version { id: string; inquiry_id: string; version_no: number; file_id: string; filename: string; pages: Page[] }
export interface Source { page: number; quote: string }
export interface Requirement { id: string; product_type: string; features: Record<string, unknown>; quantity: number | null; unit: string | null; source: Source }
export interface ProductRef { code: string; names: string[]; unit: string }
export interface Suggestion { id: string; requirement_id: string; product: ProductRef; score: number; reasons: string[]; status: string; source: Source }
export interface Gap { id: string; requirement_id: string; field: string; question: string; severity: string; status: string; answer: string }
export interface AltRow { criterion: string; wanted: string; offered: string; match: boolean }
export interface Alternative { id: string; requirement_id: string; product: ProductRef; score: number; comparison: AltRow[]; reasons: string[]; status: string }
export interface DiffChange { type: string; product_type: string; field: string; old: string; new: string }
export interface Product { id: string; code: string; names: string[]; synonyms: string[]; features: Record<string, unknown>; unit: string }
export interface Price { id: string; product_id: string; price: number; currency: string; status: string }
export interface Terms { id: string; name: string; text: string; status: string }
export interface QuoteLine { id: string; requirement_id: string; product: ProductRef; quantity: number; unit: string; unit_price: number; currency: string; amount: number; price_version_id: string }
export interface Quote { id: string; inquiry_id: string; customer: string; version_no: number | null; status: string; terms_version_id: string; lines: QuoteLine[]; totals: { currency: string; amount: number }[]; created_by: string; approved_by: string | null }
export interface QuoteSummary { id: string; version_no: number | null; status: string; created_by: string; approved_by: string | null }
export interface AuditEntry { seq: number; timestamp: number; actor: string; action: string; target: string; detail: string }
export interface Job { job_id: string; kind: string; status: string; attempts: number; result: unknown; error: string | null }
export interface Metrics {
  http: { total: number; by_class: Record<string, number>; uptime_seconds: number };
  jobs: { by_status: Record<string, number> };
  model: { calls: number; ok: number; failed: number };
  quotes: { by_status: Record<string, number>; exported: number; avg_approval_seconds: number | null };
}
export interface ModelUsage { calls: number; ok: number; failed: number; prompt_chars: number; response_chars: number; estimated_tokens: number; avg_latency_ms: number | null; by_model: string[] }
export interface Health { status: string; version?: string }

const TOKEN_KEY = "linevora_token";

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(t: string | null) {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* yoksay */ }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

async function req<T>(path: string, opts: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string> | undefined) };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let body: BodyInit | undefined = opts.body as BodyInit | undefined;
  if (opts.json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.json); }
  const res = await fetch(`/v1${path}`, { ...opts, headers, body });
  let data: unknown = null;
  try { data = await res.json(); } catch { data = null; }
  if (!res.ok) {
    const d = (data as { detail?: unknown } | null)?.detail;
    throw new ApiError(res.status, typeof d === "string" ? d : d !== undefined ? JSON.stringify(d) : `HTTP ${res.status}`);
  }
  return data as T;
}

export const api = {
  health: () => req<Health>("/health"),
  ready: () => req<{ status: string; checks: Record<string, boolean> }>("/health/ready"),
  login: (username: string, password: string) => req<{ access_token: string }>("/auth/token", { method: "POST", json: { username, password } }),
  revoke: () => req<{ revoked: boolean }>("/auth/revoke", { method: "POST" }),
  me: () => req<User>("/me"),
  audit: (limit = 200, offset = 0) => req<{ total: number; entries: AuditEntry[] }>(`/audit?limit=${limit}&offset=${offset}`),
  metrics: () => req<Metrics>("/metrics"),
  modelUsage: () => req<ModelUsage>("/metrics/model-usage"),
  deadLetter: () => req<{ jobs: { job_id: string; kind: string; status: string; attempts: number; error: string | null }[] }>("/jobs/dead-letter"),
  job: (id: string) => req<Job>(`/jobs/${id}`),
  inquiries: () => req<{ total: number; inquiries: Inquiry[] }>("/inquiries"),
  createInquiry: (customer: string, title: string) => req<Inquiry>("/inquiries", { method: "POST", json: { customer, title } }),
  versions: (inquiryId: string) => req<{ versions: Version[] }>(`/inquiries/${inquiryId}/versions`),
  uploadVersion: async (inquiryId: string, file: File): Promise<Version> => {
    const fd = new FormData(); fd.append("file", file);
    const token = getToken();
    const res = await fetch(`/v1/inquiries/${inquiryId}/versions`, { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: fd });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new ApiError(res.status, (data as { detail?: string })?.detail ?? `HTTP ${res.status}`);
    return data as Version;
  },
  process: (inquiryId: string, versionNo: number) => req<{ job_id: string; status: string }>(`/inquiries/${inquiryId}/versions/${versionNo}/process`, { method: "POST" }),
  suggestions: (inquiryId: string, versionNo: number) => req<{ requirements: Requirement[]; suggestions: Suggestion[] }>(`/inquiries/${inquiryId}/versions/${versionNo}/suggestions`),
  gaps: (inquiryId: string, versionNo: number) => req<{ gaps: Gap[] }>(`/inquiries/${inquiryId}/versions/${versionNo}/gaps`),
  alternatives: (inquiryId: string, versionNo: number) => req<{ alternatives: Alternative[] }>(`/inquiries/${inquiryId}/versions/${versionNo}/alternatives`),
  diff: (inquiryId: string, a: number, b: number) => req<{ from_version: number; to_version: number; changes: DiffChange[] }>(`/inquiries/${inquiryId}/versions/${a}/diff/${b}`),
  decideSuggestion: (id: string, status: string) => req<unknown>(`/suggestions/${id}`, { method: "PATCH", json: { status } }),
  answerGap: (id: string, answer: string) => req<unknown>(`/gaps/${id}/answer`, { method: "POST", json: { status: "yanıtlandı", answer } }),
  products: () => req<{ products: Product[] }>("/products"),
  createProduct: (code: string, names: string[], unit: string) => req<unknown>("/products", { method: "POST", json: { code, names, unit } }),
  prices: (productId: string) => req<{ prices: Price[] }>(`/prices?product_id=${productId}`),
  createPrice: (product_id: string, price: number, currency: string) => req<unknown>("/prices", { method: "POST", json: { product_id, price, currency } }),
  activatePrice: (id: string) => req<unknown>(`/prices/${id}/activate`, { method: "POST" }),
  terms: () => req<{ terms: Terms[] }>("/terms"),
  createTerms: (name: string, text: string) => req<unknown>("/terms", { method: "POST", json: { name, text } }),
  activateTerms: (id: string) => req<unknown>(`/terms/${id}/activate`, { method: "POST" }),
  quotes: (inquiryId: string) => req<{ quotes: QuoteSummary[] }>(`/inquiries/${inquiryId}/quotes`),
  createQuote: (inquiryId: string, versionNo: number, lines: { requirement_id: string; product_id: string; quantity: number | null }[]) =>
    req<Quote>(`/inquiries/${inquiryId}/versions/${versionNo}/quotes`, { method: "POST", json: { lines } }),
  updateQuoteLines: (quoteId: string, lines: { requirement_id: string; product_id: string; quantity: number | null }[]) =>
    req<Quote>(`/quotes/${quoteId}/lines`, { method: "PUT", json: { lines } }),
  quote: (id: string) => req<Quote>(`/quotes/${id}`),
  quoteAction: (id: string, action: "submit" | "return" | "approve") => req<Quote>(`/quotes/${id}/${action}`, { method: "POST" }),
  exportQuote: (id: string) => req<Record<string, unknown>>(`/quotes/${id}/export`),
  previewQuote: (id: string) => req<Record<string, unknown>>(`/quotes/${id}/preview`),
  snapshot: () => req<{ saved: boolean; path: string }>("/admin/snapshot", { method: "POST" }),
};

/* ---- Pazar yeri ---- */
export interface MpTrust { level: string; has_published: boolean; has_agreement: boolean; agreements_completed: number }
export interface MpCompany { company_id: string; display_name: string; level: string; trust_level?: string; has_published: boolean; has_agreement: boolean; agreements_completed: number; completed_agreements?: number; published_listings: number }
export interface MpListing { id: string; kind: string; owner_user: string; company_id?: string; title: string; raw_text: string; product: string | null; quantity: string | null; unit: string | null; delivery_place: string | null; delivery_days: number | null; category: string | null; features: Record<string, unknown>; missing_fields: string[]; needs_clarification: boolean; status: string; document?: string; created_at?: number; updated_at?: number; company?: MpCompany; owner_company?: MpCompany; trust?: MpTrust }
export interface MpAgreement { id: string; listing_id: string; offer_id: string; buyer_user: string; buyer_company_id: string; seller_user: string; seller_company_id: string; total: string | null; currency: string | null; status: string; created_at: number }
export interface MpActivity { type: string; timestamp: number; created_at?: number; text: string; description?: string; listing_id: string | null; offer_id: string | null }
export interface MpDashboard { my_listings: { draft: number; published: number; awarded: number; closed: number; total: number }; offers_received_open: number; offers_sent_open: number; revision_requested: number; unread_notifications: number; recent_activity: MpActivity[] }
export interface MpCompanyMe { company_id: string; display_name: string; member_since: number | null; stats: { published_listings: number; agreements_completed: number; offers_sent: number }; trust: { has_published: boolean; has_agreement: boolean; level: string } }
export interface MpParse { kind: string; title: string; product: string | null; quantity: string | null; unit: string | null; delivery_place: string | null; delivery_days: number | null; category: string | null; features: Record<string, unknown>; missing_fields: string[]; missing_questions: { field: string; question: string }[]; needs_clarification: boolean; document: string; raw_text: string }
export interface MpOfferLine { quantity: string | null; unit: string | null; unit_price: string | null; currency: string | null; line_total: string | null; product?: string | null; features?: Record<string, unknown> }
export interface MpOffer { id: string; listing_id: string; offerer_user: string; revision_no: number; parent_offer_id: string | null; lines: MpOfferLine[]; total: string | null; currency: string | null; tax_included: boolean | null; shipping_included: boolean | null; shipping_cost: string | null; delivery_days: number | null; payment_terms: string | null; note: string | null; status: string; document?: string }
export interface MpComparison { listing_id: string; offers: { offer_id: string; offerer_user: string; revision_no: number; status: string; total: string | null; currency: string | null; tax_included: boolean | null; shipping_included: boolean | null; shipping_cost: string | null; delivery_days: number | null; payment_terms: string | null; missing_costs: string[]; comparable: boolean; comparable_reasons: string[]; offer: MpOffer; company?: MpCompany; trust?: MpTrust }[] }
export interface MpMessage { id: string; listing_id: string; offer_id: string | null; sender_user: string; recipient_user: string; body: string; created_at: number }
export interface MpNotification { id: string; text: string; kind: string; read: boolean; listing_id: string | null; offer_id: string | null; created_at: number }

export const mpApi = {
  parseListing: (kind: string, text: string) => req<MpParse>("/marketplace/parse-listing", { method: "POST", json: { kind, text } }),
  createListing: (b: Record<string, unknown>) => req<MpListing>("/marketplace/listings", { method: "POST", json: b }),
  publishListing: (id: string) => req<MpListing>(`/marketplace/listings/${id}/publish`, { method: "POST", json: { confirmed: true } }),
  listings: (p: Record<string, string | number | undefined>) => { const q = new URLSearchParams(); Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== "") q.set(k, String(v)); }); return req<{ listings: MpListing[] }>(`/marketplace/listings?${q}`); },
  listing: (id: string) => req<MpListing>(`/marketplace/listings/${id}`),
  myListings: () => req<{ listings: MpListing[] }>("/marketplace/my/listings"),
  parseOffer: (id: string, text: string) => req<Record<string, unknown>>(`/marketplace/listings/${id}/offers/parse`, { method: "POST", json: { text } }),
  createOffer: (id: string, b: Record<string, unknown>) => req<MpOffer>(`/marketplace/listings/${id}/offers`, { method: "POST", json: { ...b, confirmed: true } }),
  listingOffers: (id: string) => req<{ offers: MpOffer[] }>(`/marketplace/listings/${id}/offers`),
  myOffers: () => req<{ offers: MpOffer[] }>("/marketplace/my/offers"),
  reviseOffer: (id: string, b: Record<string, unknown>) => req<MpOffer>(`/marketplace/offers/${id}/revise`, { method: "POST", json: { ...b, confirmed: true } }),
  requestRevision: (id: string, note: string) => req<MpOffer>(`/marketplace/offers/${id}/request-revision`, { method: "POST", json: { note } }),
  selectOffer: (id: string) => req<{ offer: MpOffer; agreement: MpAgreement; listing: MpListing }>(`/marketplace/offers/${id}/select`, { method: "POST", json: { confirmed: true } }),
  dashboard: () => req<MpDashboard>("/marketplace/dashboard"),
  companyMe: () => req<MpCompanyMe>("/marketplace/company/me"),
  comparison: (id: string) => req<MpComparison>(`/marketplace/listings/${id}/comparison`),
  messages: (offerId: string) => req<{ messages: MpMessage[] }>(`/marketplace/offers/${offerId}/messages`),
  postMessage: (offerId: string, body: string) => req<MpMessage>(`/marketplace/offers/${offerId}/messages`, { method: "POST", json: { body } }),
  notifications: () => req<{ notifications: MpNotification[] }>("/marketplace/notifications"),
  readNotification: (id: string) => req<unknown>(`/marketplace/notifications/${id}/read`, { method: "POST" }),
};

export const isAdmin = (u: User | null) => !!u?.roles.includes("admin");
export const isEditor = (u: User | null) => !!u && (u.roles.includes("admin") || u.roles.includes("specialist"));
export const money = (n: number, cur?: string) => `${Number(n).toLocaleString("tr-TR")} ${cur ?? ""}`.trim();
export const dt = (ts: number) => new Date(ts * 1000).toLocaleString("tr-TR");
