import { useEffect, useState } from "react";
import { mpApi, type MpAgreement, type MpComparison, type MpDashboard, type MpListing, type MpMessage, type MpNotification, type MpOffer, type MpParse, type MpTrust, type User } from "../panel/api";
import { EmptyState, Skeleton, StatusBadge } from "../panel/ui";
import "./marketplace.css";

const DRAFT_KEY = "linevora_marketplace_draft";
const UNKNOWN = "I don't know, I want a supplier suggestion";
type Notify = (m: string, k?: "ok" | "err") => void;
type View = "explore" | "create" | "my-listings" | "my-offers" | "messages" | "detail";
const kindLabel = (k: string) => (k === "supply" ? "Sales listing" : "Procurement request");
const errText = (e: unknown) => (e as Error)?.message || "Something unexpected happened. Please try again.";
function listingTitle(l: MpListing) { return l.title || l.product || "Untitled listing"; }
function fmtDate(ts?: number) { return ts ? new Date(ts * 1000).toLocaleString("en-US") : ""; }
const TRUST_TONE: Record<string, string> = { "new": "neutral", "active": "info", "verified": "success" };
const TRUST_LABEL: Record<string, string> = { "new": "New", "active": "Active", "verified": "Verified" };
export function TrustBadge({ trust, name }: { trust?: MpTrust | null; name?: string }) {
  if (!trust) return null;
  const tone = TRUST_TONE[trust.level] ?? "neutral";
  const display = TRUST_LABEL[trust.level] ?? trust.level;
  const label = `Trust: ${display}`;
  return <span className={`p-badge tone-${tone}`} aria-label={`${name ? `${name} — ` : ""}${label}, ${trust.agreements_completed} completed agreements`}>{display} · {trust.agreements_completed} agreements</span>;
}
export function listingTrust(l: MpListing): MpTrust | null {
  if (l.trust) return l.trust;
  const c = l.company ?? l.owner_company;
  return c ? { level: c.level, has_published: c.has_published, has_agreement: c.has_agreement, agreements_completed: c.agreements_completed } : null;
}

const ACT_TARGET: Record<string, string> = { listing: "my-listings", offer_sent: "my-offers", offer_received: "my-listings", revision_requested: "my-offers", message: "messages", agreement: "my-offers" };
export function Overview({ notify, go }: { user: User; notify: Notify; go: (tab: string) => void }) {
  const [d, setD] = useState<MpDashboard | null>(null);
  const [rev, setRev] = useState<MpOffer[]>([]);
  const [notes, setNotes] = useState<MpNotification[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    (async () => {
      try {
        const [dash, offers, ns] = await Promise.all([mpApi.dashboard(), mpApi.myOffers(), mpApi.notifications()]);
        setD(dash);
        setRev(offers.offers.filter((o) => o.status === "revision_requested"));
        setNotes(ns.notifications.filter((n) => !n.read));
      } catch (e) { setError(errText(e)); notify(errText(e)); }
    })();
  }, []); // eslint-disable-line
  if (!d) return <section aria-label="Overview"><div className="p-card">{error ? <p role="alert" className="mp-error">{error}</p> : <Skeleton lines={4} label="Loading overview" />}</div></section>;
  const unreadMsgs = notes.filter((n) => n.kind === "message");
  const kpis: { label: string; value: number; tab: string; hint: string }[] = [
    { label: "My published listings", value: d.my_listings.published, tab: "my-listings", hint: "Go to My listings" },
    { label: "Pending offers", value: d.offers_received_open, tab: "my-listings", hint: "See incoming offers" },
    { label: "Awaiting revision", value: d.revision_requested, tab: "my-offers", hint: "Offers needing revision" },
    { label: "Unread notifications", value: d.unread_notifications, tab: "messages", hint: "Open notifications" },
  ];
  return <section aria-label="Overview">
    {error && <p role="alert" className="mp-error">{error}</p>}
    <div className="p-stat-grid" role="list" aria-label="Summary indicators">
      {kpis.map((k) => <button key={k.label} type="button" role="listitem" className="p-kpi mp-kpi-btn" onClick={() => go(k.tab)} aria-label={`${k.label}: ${k.value}. ${k.hint}`}><span className="n">{k.value}</span><span className="l">{k.label}</span><span className="d">{k.hint} →</span></button>)}
    </div>
    <div className="p-card"><h3>Pending work</h3>
      {rev.length === 0 && unreadMsgs.length === 0 ? <EmptyState title="No pending work" desc="No revision requests or unread message notifications." /> : <>
        {rev.length > 0 && <><h4>Offers needing revision</h4><ul className="mp-todo">{rev.map((o) => <li key={o.id}><span>Total <b>{o.total ?? "—"} {o.currency ?? ""}</b> · revision {o.revision_no} · <StatusBadge status={o.status} /></span><span className="p-row"><button className="p-btn sm" onClick={() => go("my-offers")}>Revise in My offers</button></span></li>)}</ul></>}
        {unreadMsgs.length > 0 && <><h4>Messages awaiting a reply</h4><ul className="mp-todo">{unreadMsgs.map((n) => <li key={n.id}><span>{n.text} <small>{fmtDate(n.created_at)}</small></span><button className="p-btn sm" onClick={() => go("messages")}>Open in Messages</button></li>)}</ul></>}
      </>}
    </div>
    <div className="p-card"><h3>Recent activity</h3>
      {d.recent_activity.length === 0 ? <EmptyState title="No activity yet" desc="Listing, offer and message activity is listed here." /> :
        <ul className="mp-activity">{d.recent_activity.map((a, i) => <li key={`${a.timestamp}-${i}`}><span><time dateTime={new Date(a.timestamp * 1000).toISOString()}>{fmtDate(a.timestamp)}</time> — {a.text}</span>{a.listing_id && <button className="p-btn sm" onClick={() => go(ACT_TARGET[a.type] ?? "explore")} aria-label={`Go to the section for: ${a.text}`}>Go to section</button>}</li>)}</ul>}
    </div>
  </section>;
}

export function Marketplace({ user, initial, notify, go }: { user: User; initial?: string; notify: Notify; go: (tab: string) => void }) {
  const [view, setView] = useState<View>((initial as View) || "explore");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => { if (initial && initial !== view) setView(initial as View); }, [initial]); // eslint-disable-line
  const open = (id: string) => { setSelectedId(id); setView("detail"); };
  if (view === "detail" && selectedId) return <Detail id={selectedId} user={user} notify={notify} back={() => setView("explore")} />;
  if (view === "create") return <CreateListing user={user} notify={notify} done={(id) => { setSelectedId(id); setView("detail"); }} />;
  if (view === "my-listings") return <MyListings user={user} notify={notify} open={open} />;
  if (view === "my-offers") return <MyOffers user={user} notify={notify} open={open} />;
  if (view === "messages") return <Messages user={user} notify={notify} open={open} />;
  return <Explore notify={notify} open={open} />;
}

function CreateListing({ notify, done }: { user: User; notify: Notify; done: (id: string) => void }) {
  const [kind, setKind] = useState("demand"); const [text, setText] = useState(""); const [step, setStep] = useState<1 | 2>(1);
  const [parsed, setParsed] = useState<MpParse | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [f, setF] = useState({ title: "", product: "", quantity: "", unit: "", delivery_place: "", delivery_days: "", category: "" });
  const [unknown, setUnknown] = useState<Record<string, boolean>>({});
  useEffect(() => { try { const d = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null"); if (d) { setKind(d.kind || "demand"); setText(d.text || ""); if (d.f) setF(d.f); if (d.parsed) { setParsed(d.parsed); setStep(2); } } } catch { /* ignore */ } }, []);
  useEffect(() => { try { localStorage.setItem(DRAFT_KEY, JSON.stringify({ kind, text, f, parsed })); } catch { /* ignore */ } }, [kind, text, f, parsed]);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF((s) => ({ ...s, [k]: e.target.value }));
  function applyParsed(p: MpParse) {
    setParsed(p); setStep(2);
    setF({ title: p.title || "", product: p.product || "", quantity: p.quantity || "", unit: p.unit || "", delivery_place: p.delivery_place || "", delivery_days: p.delivery_days != null ? String(p.delivery_days) : "", category: p.category || "" });
  }
  async function parse() {
    if (!text.trim()) { setError("Please first write a text describing what you need."); return; }
    setBusy(true); setError("");
    try { applyParsed(await mpApi.parseListing(kind, text)); }
    catch (e) { setError(`Automatic parsing failed (${errText(e)}). You can continue by filling in the form below manually.`); applyParsed({ kind, title: "", product: null, quantity: null, unit: null, delivery_place: null, delivery_days: null, category: null, features: {}, missing_fields: [], missing_questions: [], needs_clarification: true, document: text, raw_text: text }); }
    finally { setBusy(false); }
  }
  async function publish() {
    setBusy(true); setError("");
    try {
      const missing = [...(parsed?.missing_fields || []), ...Object.keys(unknown).filter((k) => unknown[k])];
      const created = await mpApi.createListing({ kind, raw_text: text, title: f.title || undefined, product: f.product || undefined, quantity: f.quantity || undefined, unit: f.unit || undefined, delivery_place: f.delivery_place || undefined, delivery_days: f.delivery_days ? Number(f.delivery_days) : undefined, category: f.category || undefined, missing_fields: [...new Set(missing)], needs_clarification: Object.values(unknown).some(Boolean) || (parsed?.needs_clarification ?? false) });
      const pub = await mpApi.publishListing(created.id);
      try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
      notify("Your listing has been published.", "ok"); done(pub.id);
    } catch (e) { setError(errText(e)); notify(errText(e)); } finally { setBusy(false); }
  }
  if (step === 1) return <section aria-label="Create listing">
    <div className="p-card"><h3>1 · What would you like to do?</h3>
      <div className="mp-kind-cards">
        <button className={`mp-kind-card${kind === "demand" ? " on" : ""}`} onClick={() => setKind("demand")} aria-pressed={kind === "demand"}><b>Procurement request</b><span>I am looking for a product; suppliers quote a price.</span><small>Example: “Looking for 300 galvanized pipes, delivery to Istanbul.”</small></button>
        <button className={`mp-kind-card${kind === "supply" ? " on" : ""}`} onClick={() => setKind("supply")} aria-pressed={kind === "supply"}><b>Sales listing</b><span>I am selling a product I have; buyers make offers.</span><small>Example: “I have 500 galvanized pipes, ready for sale.”</small></button>
      </div>
      <label htmlFor="mp-describe">Describe it — what do you need?</label>
      <textarea id="mp-describe" className="mp-big" rows={7} value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. Looking for 300 galvanized pipes" aria-describedby="mp-describe-hint" />
      <p id="mp-describe-hint" className="p-muted">Only what you write is used; a price, technical detail or payment term you did not state is never invented. Your draft is saved automatically.</p>
      {error && <p role="alert" className="mp-error">{error}</p>}
      <button className="p-btn primary" disabled={busy} onClick={() => void parse()}>{busy ? "Parsing…" : "Continue: go to the review step"}</button>
    </div></section>;
  return <section aria-label="Review your listing">
    <div className="p-card"><h3>2 · Review and publish</h3>
      <p className="p-muted">You can correct the fields. Publishing happens only with your approval, via the “Publish” button below.</p>
      <div className="mp-form">
        <label htmlFor="cl-title">Title<input id="cl-title" value={f.title} onChange={set("title")} /></label>
        <label htmlFor="cl-product">Product<input id="cl-product" value={f.product} onChange={set("product")} /></label>
        <label htmlFor="cl-qty">Quantity<input id="cl-qty" inputMode="decimal" value={f.quantity} onChange={set("quantity")} /></label>
        <label htmlFor="cl-unit">Unit<input id="cl-unit" value={f.unit} onChange={set("unit")} placeholder="pcs, kg…" /></label>
        <label htmlFor="cl-place">Delivery place<input id="cl-place" value={f.delivery_place} onChange={set("delivery_place")} /></label>
        <label htmlFor="cl-days">Delivery time (days)<input id="cl-days" type="number" min="0" value={f.delivery_days} onChange={set("delivery_days")} /></label>
        <label htmlFor="cl-cat">Category<input id="cl-cat" value={f.category} onChange={set("category")} /></label>
      </div>
      {parsed && parsed.missing_questions.length > 0 && <fieldset className="mp-missing"><legend>Missing information</legend>
        {parsed.missing_questions.map((q0) => <div key={q0.field} className="mp-missing-row"><span>{q0.question}</span>
          <label><input type="checkbox" checked={!!unknown[q0.field]} onChange={(e) => setUnknown((s) => ({ ...s, [q0.field]: e.target.checked }))} /> {UNKNOWN}</label></div>)}
      </fieldset>}
      {parsed?.document && <><h4>Document preview</h4><pre className="p-text" aria-label="Listing document preview">{parsed.document}</pre></>}
      {error && <p role="alert" className="mp-error">{error}</p>}
      <div className="p-row"><button className="p-btn" onClick={() => setStep(1)}>Go back</button>
      <button className="p-btn primary" disabled={busy} onClick={() => void publish()}>{busy ? "Publishing…" : "Publish"}</button></div>
    </div></section>;
}

function Detail({ id, user, notify, back }: { id: string; user: User; notify: Notify; back: () => void }) {
  const [listing, setListing] = useState<MpListing | null>(null); const [offers, setOffers] = useState<MpOffer[]>([]);
  const [cmp, setCmp] = useState<MpComparison | null>(null); const [error, setError] = useState(""); const [offerText, setOfferText] = useState("");
  const [offerStep, setOfferStep] = useState<1 | 2>(1); const [offerParsed, setOfferParsed] = useState<Record<string, unknown> | null>(null); const [busy, setBusy] = useState(false);
  const [agreement, setAgreement] = useState<MpAgreement | null>(null);
  const isOwner = listing?.owner_user === user.username;
  async function load() {
    try {
      const l = await mpApi.listing(id); setListing(l);
      setOffers((await mpApi.listingOffers(id)).offers);
      if (l.owner_user === user.username) { try { setCmp(await mpApi.comparison(id)); } catch { setCmp(null); } }
    } catch (e) { setError(errText(e)); }
  }
  useEffect(() => { void load(); }, [id]); // eslint-disable-line
  async function parseOffer() {
    if (!offerText.trim()) { setError("Write your offer as free text: price, delivery time and payment terms."); return; }
    setBusy(true); setError("");
    try { setOfferParsed(await mpApi.parseOffer(id, offerText)); setOfferStep(2); }
    catch (e) { setError(errText(e)); } finally { setBusy(false); }
  }
  async function submitOffer() {
    setBusy(true); setError("");
    try { await mpApi.createOffer(id, { text: offerText, quantity: (offerParsed as { quantity?: string })?.quantity, unit_price: (offerParsed as { unit_price?: string })?.unit_price, currency: (offerParsed as { currency?: string })?.currency, tax_included: (offerParsed as { tax_included?: boolean })?.tax_included, shipping_included: (offerParsed as { shipping_included?: boolean })?.shipping_included, delivery_days: (offerParsed as { delivery_days?: number })?.delivery_days, payment_terms: (offerParsed as { payment_terms?: string })?.payment_terms }); notify("Your offer has been sent.", "ok"); setOfferText(""); setOfferStep(1); await load(); }
    catch (e) { setError(errText(e)); notify(errText(e)); } finally { setBusy(false); }
  }
  async function actOffer(offerId: string, act: "msg" | "rev" | "sel") {
    if (act === "sel") { if (!window.confirm("Are you sure you want to select this offer? The other offers will be closed.")) return; try { const r = await mpApi.selectOffer(offerId); setAgreement(r.agreement); notify("Offer selected, agreement created.", "ok"); await load(); } catch (e) { notify(errText(e)); } return; }
    const note = window.prompt(act === "rev" ? "Your revision note (e.g. price or delivery time):" : "Your question / message:"); if (!note) return;
    try { if (act === "rev") { await mpApi.requestRevision(offerId, note); notify("Revision request sent.", "ok"); } else { await mpApi.postMessage(offerId, note); notify("Message sent.", "ok"); } await load(); } catch (e) { notify(errText(e)); }
  }
  if (!listing) return <div className="p-card"><button className="p-btn" onClick={back}>← Back to Explore</button>{error ? <p role="alert" className="mp-error">{error}</p> : <p className="p-muted">Loading…</p>}</div>;
  return <section aria-label="Listing detail">
    <button className="p-btn" onClick={back}>← Back to Explore</button>
    <div className="p-card"><span className="p-pill">{kindLabel(listing.kind)}</span> <StatusBadge status={listing.status} /> <TrustBadge trust={listingTrust(listing)} name={(listing.company ?? listing.owner_company)?.display_name ?? listing.owner_user} />
      <h3>{listingTitle(listing)}</h3>
      {(listing.company ?? listing.owner_company) && <p className="p-muted">Company: {(listing.company ?? listing.owner_company)!.display_name} · {listingTrust(listing)?.agreements_completed ?? 0} completed agreements</p>}
      <p>{listing.quantity ? `${listing.quantity} ${listing.unit ?? ""}` : "Quantity not specified"} · {listing.delivery_place || "Delivery place not specified"}{listing.delivery_days != null ? ` · ${listing.delivery_days} days` : ""}</p>
      {listing.document && <pre className="p-text" aria-label="Listing document">{listing.document}</pre>}
      <p className="p-muted">Section: document view · Payment and logistics are not handled on this platform; the parties agree between themselves.</p>
      {error && <p role="alert" className="mp-error">{error}</p>}
    </div>
    {!isOwner && listing.status === "published" && <div className="p-card"><h3>Make an offer</h3>
      <p className="p-muted">Competing offers are not shown to you; you only see your own offer.</p>
      {offerStep === 1 ? <><label htmlFor="of-text">Describe your offer</label>
        <textarea id="of-text" className="mp-big" rows={5} value={offerText} onChange={(e) => setOfferText(e.target.value)} placeholder="e.g. Unit price 125.50 USD, VAT excluded, delivery in 10 days" />
        <button className="p-btn primary" disabled={busy} onClick={() => void parseOffer()}>Parse and review the offer</button></>
      : <><h4>Review it</h4><pre className="p-text">{JSON.stringify(offerParsed, null, 2)}</pre>
        <p className="p-muted">Sending happens only with your “Send offer” approval. An amount you did not state is never completed for you.</p>
        <div className="p-row"><button className="p-btn" onClick={() => setOfferStep(1)}>Edit the text</button>
        <button className="p-btn primary" disabled={busy} onClick={() => void submitOffer()}>Send offer</button></div></>}
    </div>}
    {isOwner && cmp && <div className="p-card"><h3>Compare offers</h3>
      <div className="mp-tablewrap"><table aria-label="Offer comparison table"><thead><tr><th>Company</th><th>Quantity</th><th>Unit price</th><th>Tax / shipping</th><th>Delivery</th><th>Payment</th><th>Total</th><th>Action</th></tr></thead>
      <tbody>{cmp.offers.map((c) => { const line = c.offer.lines[0]; return <tr key={c.offer_id}>
        <td>{c.company?.display_name ?? c.offerer_user} <TrustBadge trust={c.trust ?? (c.company ? { level: c.company.level, has_published: c.company.has_published, has_agreement: c.company.has_agreement, agreements_completed: c.company.agreements_completed } : null)} name={c.company?.display_name ?? c.offerer_user} />{c.comparable ? "" : <span className="mp-warn" role="note"> Not comparable: {c.comparable_reasons.join("; ")}</span>}{c.missing_costs.length > 0 && <span className="mp-warn"> Missing costs: {c.missing_costs.join(", ")}</span>}</td>
        <td>{line?.quantity ?? "—"} {line?.unit ?? ""}</td><td>{line?.unit_price ?? "—"} {line?.currency ?? ""}</td>
        <td>{c.tax_included == null ? "VAT not specified" : c.tax_included ? "VAT included" : "VAT excluded"} · {c.shipping_included == null ? "shipping not specified" : c.shipping_included ? "shipping included" : `shipping separate${c.shipping_cost ? `: ${c.shipping_cost}` : ""}`}</td>
        <td>{c.delivery_days != null ? `${c.delivery_days} days` : "—"}</td><td>{c.payment_terms || "—"}</td>
        <td><b>{c.total ?? "—"} {c.currency ?? ""}</b></td>
        <td><div className="p-row"><button className="p-btn sm" onClick={() => void actOffer(c.offer_id, "msg")}>Ask a question</button>
        <button className="p-btn sm" onClick={() => void actOffer(c.offer_id, "rev")}>Request revision</button>
        <button className="p-btn sm primary" onClick={() => void actOffer(c.offer_id, "sel")}>Select offer</button></div></td></tr>; })}</tbody></table></div>
      {cmp.offers.length === 0 && <p className="p-muted">No offers yet.</p>}
    </div>}
    {agreement && <div className="p-card" role="status" aria-label="Agreement summary"><h3>Agreement created</h3>
      <p>Buyer: <b>{agreement.buyer_user}</b> · Seller: <b>{agreement.seller_user}</b></p>
      <p>Total: <b>{agreement.total ?? "—"} {agreement.currency ?? ""}</b> · Date: {fmtDate(agreement.created_at)} · Status: <StatusBadge status={agreement.status} /></p>
      <ol className="mp-timeline" aria-label="Agreement status timeline"><li className="done">Offer selected</li><li className="done">Agreement record created ({fmtDate(agreement.created_at)})</li><li>Delivery and payment are handled between the parties</li></ol>
    </div>}
    {!isOwner && offers.length > 0 && <div className="p-card"><h3>My offer</h3>{offers.map((o) => <p key={o.id}>Revision {o.revision_no} · Total <b>{o.total ?? "—"} {o.currency ?? ""}</b> · <StatusBadge status={o.status} /></p>)}</div>}
  </section>;
}

function MyListings({ notify, open }: { user: User; notify: Notify; open: (id: string) => void }) {
  const [items, setItems] = useState<MpListing[]>([]); const [error, setError] = useState("");
  useEffect(() => { (async () => { try { setItems((await mpApi.myListings()).listings); } catch (e) { setError(errText(e)); notify(errText(e)); } })(); }, []); // eslint-disable-line
  return <section aria-label="My listings"><div className="p-card"><h3>My listings</h3>{error && <p role="alert" className="mp-error">{error}</p>}
    {items.length === 0 ? <EmptyState title="You have no listings yet" desc="When you create your first listing it will be listed here." /> : <div className="mp-cards">{items.map((l) => <article key={l.id} className="mp-card"><span className="p-row"><span className="p-pill">{kindLabel(l.kind)}</span><StatusBadge status={l.status} /><TrustBadge trust={listingTrust(l)} /></span><h4 className="mp-card-title">{listingTitle(l)}</h4><p>{l.quantity ? `${l.quantity} ${l.unit ?? ""}` : ""} {fmtDate(l.created_at)}</p><span className="p-row"><button className="p-btn sm" onClick={() => open(l.id)} aria-label={`Open details for ${listingTitle(l)}`}>Open details</button></span></article>)}</div>}
  </div></section>;
}

function MyOffers({ notify, open }: { user: User; notify: Notify; open: (id: string) => void }) {
  const [items, setItems] = useState<MpOffer[]>([]); const [error, setError] = useState(""); const [revText, setRevText] = useState<Record<string, string>>({});
  async function load() { try { setItems((await mpApi.myOffers()).offers); } catch (e) { setError(errText(e)); notify(errText(e)); } }
  useEffect(() => { void load(); }, []); // eslint-disable-line
  async function revise(o: MpOffer) {
    const t = revText[o.id]; if (!t?.trim()) { notify("Write the new offer text for the revision."); return; }
    try { const p = await mpApi.parseOffer(o.listing_id, t); await mpApi.reviseOffer(o.id, { text: t, unit_price: (p as { unit_price?: string }).unit_price, quantity: (p as { quantity?: string }).quantity }); notify("Revised offer sent.", "ok"); await load(); } catch (e) { notify(errText(e)); }
  }
  return <section aria-label="My offers"><div className="p-card"><h3>My offers</h3>{error && <p role="alert" className="mp-error">{error}</p>}
    {items.length === 0 ? <EmptyState title="You have not made any offers yet" desc="When you make an offer on a listing in Explore, it appears here." /> : items.map((o) => <article key={o.id} className="mp-offer-row">
      <p><b>{o.total ?? "—"} {o.currency ?? ""}</b> · revision {o.revision_no} · <StatusBadge status={o.status} /></p>
      <div className="p-row"><button className="p-btn sm" onClick={() => open(o.listing_id)}>Open listing</button></div>
      <label htmlFor={`rev-${o.id}`}>Revision text</label>
      <textarea id={`rev-${o.id}`} rows={3} value={revText[o.id] || ""} onChange={(e) => setRevText((s) => ({ ...s, [o.id]: e.target.value }))} placeholder="e.g. Unit price 120 USD, delivery in 7 days" />
      <button className="p-btn sm" onClick={() => void revise(o)}>Send revision</button>
    </article>)}
  </div></section>;
}

function Messages({ notify, open }: { user: User; notify: Notify; open: (id: string) => void }) {
  const [notes, setNotes] = useState<MpNotification[]>([]); const [error, setError] = useState("");
  const [offerId, setOfferId] = useState(""); const [msgs, setMsgs] = useState<MpMessage[]>([]); const [draft, setDraft] = useState("");
  async function loadNotes() { try { setNotes((await mpApi.notifications()).notifications); } catch (e) { setError(errText(e)); } }
  useEffect(() => { void loadNotes(); }, []); // eslint-disable-line
  async function loadThread(id: string) { setOfferId(id); try { setMsgs((await mpApi.messages(id)).messages); } catch (e) { notify(errText(e)); } }
  async function send() { if (!draft.trim() || !offerId) return; try { await mpApi.postMessage(offerId, draft); setDraft(""); await loadThread(offerId); } catch (e) { notify(errText(e)); } }
  return <section aria-label="Messages"><div className="p-card"><h3>Messages and notifications</h3>
    <p className="p-muted">Messages are visible only between the listing owner and the offerer. Competing offers never see each other.</p>
    {error && <p role="alert" className="mp-error">{error}</p>}
    {notes.length === 0 ? <p className="p-muted">No notifications yet.</p> : <ul className="mp-notes">{notes.map((n) => <li key={n.id} className={n.read ? "" : "unread"}>
      <span>{n.text} <small>{fmtDate(n.created_at)}</small></span>
      <span className="p-row">{n.listing_id && <button className="p-btn sm" onClick={() => open(n.listing_id!)}>Listing</button>}
      {n.offer_id && <button className="p-btn sm" onClick={() => void loadThread(n.offer_id!)}>Conversation</button>}
      {!n.read && <button className="p-btn sm" onClick={() => void mpApi.readNotification(n.id).then(loadNotes)}>Mark as read</button>}</span></li>)}</ul>}
    {offerId && <div className="mp-thread"><h4>Conversation</h4>
      {msgs.length === 0 ? <p className="p-muted">No messages in this conversation yet.</p> : msgs.map((m) => <p key={m.id} className="mp-msg"><b>{m.sender_user}</b>: {m.body} <small>{fmtDate(m.created_at)}</small></p>)}
      <label htmlFor="mp-msg-input">New message</label>
      <textarea id="mp-msg-input" rows={3} value={draft} onChange={(e) => setDraft(e.target.value)} />
      <button className="p-btn primary" onClick={() => void send()}>Send</button></div>}
  </div></section>;
}

function Explore({ notify, open }: { notify: Notify; open: (id: string) => void }) {
  const [kind, setKind] = useState(""); const [q, setQ] = useState(""); const [category, setCategory] = useState("");
  const [location, setLocation] = useState(""); const [maxDays, setMaxDays] = useState(""); const [sort, setSort] = useState("newest");
  const [items, setItems] = useState<MpListing[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  const hasFilters = !!(kind || q || category || location || maxDays || sort !== "newest");
  async function load(next?: { kind: string; q: string; category: string; location: string; maxDays: string; sort: string }) {
    const f = next ?? { kind, q, category, location, maxDays, sort };
    setLoading(true); setError("");
    try { setItems((await mpApi.listings({ kind: f.kind || undefined, q: f.q || undefined, category: f.category || undefined, location: f.location || undefined, max_delivery_days: f.maxDays ? Number(f.maxDays) : undefined, sort: f.sort })).listings); }
    catch (e) { setError(errText(e)); notify(errText(e)); } finally { setLoading(false); }
  }
  function clearAll() { const f = { kind: "", q: "", category: "", location: "", maxDays: "", sort: "newest" }; setKind(""); setQ(""); setCategory(""); setLocation(""); setMaxDays(""); setSort("newest"); void load(f); }
  useEffect(() => { void load(); }, []); // eslint-disable-line
  return <section aria-label="Explore listings">
    <div className="p-card">
      <h3>Explore listings</h3>
      <div className="mp-filters" role="search">
        <label htmlFor="mp-kind">Kind<select id="mp-kind" value={kind} onChange={(e) => setKind(e.target.value)}><option value="">All</option><option value="demand">Procurement request</option><option value="supply">Sales listing</option></select></label>
        <label htmlFor="mp-q">Search text<input id="mp-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. galvanized pipe" /></label>
        <label htmlFor="mp-cat">Category<input id="mp-cat" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="category" /></label>
        <label htmlFor="mp-loc">Location<input id="mp-loc" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. Istanbul" /></label>
        <label htmlFor="mp-days">Delivery time (days, max)<input id="mp-days" type="number" min="0" inputMode="numeric" value={maxDays} onChange={(e) => setMaxDays(e.target.value)} /></label>
        <label htmlFor="mp-sort">Sort<select id="mp-sort" value={sort} onChange={(e) => { setSort(e.target.value); void load({ kind, q, category, location, maxDays, sort: e.target.value }); }}><option value="newest">Newest</option><option value="delivery">Delivery time (shortest first)</option></select></label>
        <span className="p-row"><button className="p-btn primary" onClick={() => void load()}>Filter</button><button className="p-btn" disabled={!hasFilters} onClick={clearAll} aria-label="Clear filters">Clear</button></span>
      </div>
      <p className="p-muted" role="status" aria-live="polite">{loading ? "Loading listings" : `${items.length} listings`}{hasFilters ? " · filter active" : ""}</p>
      {error && <p role="alert" className="mp-error">{error}</p>}
      {loading ? <Skeleton lines={3} label="Loading listings" /> : items.length === 0 ? <EmptyState title="No listings found" desc="No published listing matches your search. Broaden the filters and try again." /> :
        <div className="mp-cards">{items.map((l) => <article key={l.id} className="mp-card">
          <span className="p-row"><span className="p-pill">{kindLabel(l.kind)}</span><TrustBadge trust={listingTrust(l)} name={(l.company ?? l.owner_company)?.display_name ?? l.owner_user} /></span>
          <h4 className="mp-card-title">{listingTitle(l)}</h4>
          <p>{l.quantity ? `${l.quantity} ${l.unit ?? ""}` : "Quantity not specified"} · {l.delivery_place || "Delivery place not specified"}{l.delivery_days != null ? ` · ${l.delivery_days} days` : ""}</p>
          {(l.company ?? l.owner_company) && <p className="p-muted">{(l.company ?? l.owner_company)!.display_name} · {listingTrust(l)?.agreements_completed ?? 0} completed agreements</p>}
          {l.needs_clarification && <p className="mp-warn">Some information needs clarification — the system never invents it, it shows the gaps.</p>}
          <span className="p-row"><button className="p-btn sm" onClick={() => open(l.id)} aria-label={`Open details for ${listingTitle(l)}`}>Open details</button></span>
        </article>)}</div>}
    </div>
  </section>;
}
