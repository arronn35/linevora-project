import { useEffect, useState } from "react";
import { mpApi, type MpAgreement, type MpComparison, type MpDashboard, type MpListing, type MpMessage, type MpNotification, type MpOffer, type MpParse, type MpTrust, type User } from "../panel/api";
import { EmptyState, Skeleton, StatusBadge } from "../panel/ui";
import "./marketplace.css";

const DRAFT_KEY = "linevora_marketplace_draft";
const UNKNOWN = "Bilmiyorum, tedarikçi önerisi istiyorum";
type Notify = (m: string, k?: "ok" | "err") => void;
type View = "kesfet" | "olustur" | "ilanlarim" | "tekliflerim" | "mesajlar" | "detay";
const kindLabel = (k: string) => (k === "supply" ? "Satış ilanı" : "Tedarik talebi");
const errText = (e: unknown) => (e as Error)?.message || "Beklenmedik bir hata oluştu. Lütfen tekrar deneyin.";
function listingTitle(l: MpListing) { return l.title || l.product || "Başlıksız ilan"; }
function fmtDate(ts?: number) { return ts ? new Date(ts * 1000).toLocaleString("tr-TR") : ""; }
const TRUST_TONE: Record<string, string> = { "yeni": "neutral", "aktif": "info", "doğrulanmış": "success" };
export function TrustBadge({ trust, name }: { trust?: MpTrust | null; name?: string }) {
  if (!trust) return null;
  const tone = TRUST_TONE[trust.level] ?? "neutral";
  const label = `Güven: ${trust.level}`;
  return <span className={`p-badge tone-${tone}`} aria-label={`${name ? `${name} — ` : ""}${label}, ${trust.agreements_completed} tamamlanmış anlaşma`}>{trust.level} · {trust.agreements_completed} anlaşma</span>;
}
export function listingTrust(l: MpListing): MpTrust | null {
  if (l.trust) return l.trust;
  const c = l.company ?? l.owner_company;
  return c ? { level: c.level, has_published: c.has_published, has_agreement: c.has_agreement, agreements_completed: c.agreements_completed } : null;
}

const ACT_TARGET: Record<string, string> = { listing: "ilanlarim", offer_sent: "tekliflerim", offer_received: "ilanlarim", revision_requested: "tekliflerim", message: "mesajlar", agreement: "tekliflerim" };
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
  if (!d) return <section aria-label="Genel Bakış"><div className="p-card">{error ? <p role="alert" className="mp-error">{error}</p> : <Skeleton lines={4} label="Genel bakış yükleniyor" />}</div></section>;
  const unreadMsgs = notes.filter((n) => n.kind === "message");
  const kpis: { label: string; value: number; tab: string; hint: string }[] = [
    { label: "Yayındaki ilanım", value: d.my_listings.published, tab: "ilanlarim", hint: "İlanlarım'a git" },
    { label: "Bekleyen teklif", value: d.offers_received_open, tab: "ilanlarim", hint: "Gelen teklifleri gör" },
    { label: "Revize bekleyen", value: d.revision_requested, tab: "tekliflerim", hint: "Revize istenen teklifler" },
    { label: "Okunmamış bildirim", value: d.unread_notifications, tab: "mesajlar", hint: "Bildirimleri aç" },
  ];
  return <section aria-label="Genel Bakış">
    {error && <p role="alert" className="mp-error">{error}</p>}
    <div className="p-stat-grid" role="list" aria-label="Özet göstergeler">
      {kpis.map((k) => <button key={k.label} type="button" role="listitem" className="p-kpi mp-kpi-btn" onClick={() => go(k.tab)} aria-label={`${k.label}: ${k.value}. ${k.hint}`}><span className="n">{k.value}</span><span className="l">{k.label}</span><span className="d">{k.hint} →</span></button>)}
    </div>
    <div className="p-card"><h3>Bekleyen işler</h3>
      {rev.length === 0 && unreadMsgs.length === 0 ? <EmptyState title="Bekleyen iş yok" desc="Revize istenen teklif veya okunmamış mesaj bildirimi bulunmuyor." /> : <>
        {rev.length > 0 && <><h4>Revize istenen teklifler</h4><ul className="mp-todo">{rev.map((o) => <li key={o.id}><span>Toplam <b>{o.total ?? "—"} {o.currency ?? ""}</b> · revizyon {o.revision_no} · <StatusBadge status={o.status} /></span><span className="p-row"><button className="p-btn sm" onClick={() => go("tekliflerim")}>Tekliflerimde revize et</button></span></li>)}</ul></>}
        {unreadMsgs.length > 0 && <><h4>Cevap bekleyen mesajlar</h4><ul className="mp-todo">{unreadMsgs.map((n) => <li key={n.id}><span>{n.text} <small>{fmtDate(n.created_at)}</small></span><button className="p-btn sm" onClick={() => go("mesajlar")}>Mesajlarda aç</button></li>)}</ul></>}
      </>}
    </div>
    <div className="p-card"><h3>Son aktivite</h3>
      {d.recent_activity.length === 0 ? <EmptyState title="Henüz aktivite yok" desc="İlan, teklif ve mesaj hareketleri burada listelenir." /> :
        <ul className="mp-activity">{d.recent_activity.map((a, i) => <li key={`${a.timestamp}-${i}`}><span><time dateTime={new Date(a.timestamp * 1000).toISOString()}>{fmtDate(a.timestamp)}</time> — {a.text}</span>{a.listing_id && <button className="p-btn sm" onClick={() => go(ACT_TARGET[a.type] ?? "kesfet")} aria-label={`${a.text} ile ilgili bölüme git`}>İlgili bölüme git</button>}</li>)}</ul>}
    </div>
  </section>;
}

export function Marketplace({ user, initial, notify, go }: { user: User; initial?: string; notify: Notify; go: (tab: string) => void }) {
  const [view, setView] = useState<View>((initial as View) || "kesfet");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => { if (initial && initial !== view) setView(initial as View); }, [initial]); // eslint-disable-line
  const open = (id: string) => { setSelectedId(id); setView("detay"); };
  if (view === "detay" && selectedId) return <Detail id={selectedId} user={user} notify={notify} back={() => setView("kesfet")} />;
  if (view === "olustur") return <CreateListing user={user} notify={notify} done={(id) => { setSelectedId(id); setView("detay"); }} />;
  if (view === "ilanlarim") return <MyListings user={user} notify={notify} open={open} />;
  if (view === "tekliflerim") return <MyOffers user={user} notify={notify} open={open} />;
  if (view === "mesajlar") return <Messages user={user} notify={notify} open={open} />;
  return <Explore notify={notify} open={open} />;
}

function CreateListing({ notify, done }: { user: User; notify: Notify; done: (id: string) => void }) {
  const [kind, setKind] = useState("demand"); const [text, setText] = useState(""); const [step, setStep] = useState<1 | 2>(1);
  const [parsed, setParsed] = useState<MpParse | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [f, setF] = useState({ title: "", product: "", quantity: "", unit: "", delivery_place: "", delivery_days: "", category: "" });
  const [unknown, setUnknown] = useState<Record<string, boolean>>({});
  useEffect(() => { try { const d = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null"); if (d) { setKind(d.kind || "demand"); setText(d.text || ""); if (d.f) setF(d.f); if (d.parsed) { setParsed(d.parsed); setStep(2); } } } catch { /* yoksay */ } }, []);
  useEffect(() => { try { localStorage.setItem(DRAFT_KEY, JSON.stringify({ kind, text, f, parsed })); } catch { /* yoksay */ } }, [kind, text, f, parsed]);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF((s) => ({ ...s, [k]: e.target.value }));
  function applyParsed(p: MpParse) {
    setParsed(p); setStep(2);
    setF({ title: p.title || "", product: p.product || "", quantity: p.quantity || "", unit: p.unit || "", delivery_place: p.delivery_place || "", delivery_days: p.delivery_days != null ? String(p.delivery_days) : "", category: p.category || "" });
  }
  async function parse() {
    if (!text.trim()) { setError("Lütfen önce ihtiyacınızı anlatan bir metin yazın."); return; }
    setBusy(true); setError("");
    try { applyParsed(await mpApi.parseListing(kind, text)); }
    catch (e) { setError(`Otomatik çözümleme başarısız oldu (${errText(e)}). Aşağıdaki formu elle doldurarak devam edebilirsiniz.`); applyParsed({ kind, title: "", product: null, quantity: null, unit: null, delivery_place: null, delivery_days: null, category: null, features: {}, missing_fields: [], missing_questions: [], needs_clarification: true, document: text, raw_text: text }); }
    finally { setBusy(false); }
  }
  async function publish() {
    setBusy(true); setError("");
    try {
      const missing = [...(parsed?.missing_fields || []), ...Object.keys(unknown).filter((k) => unknown[k])];
      const created = await mpApi.createListing({ kind, raw_text: text, title: f.title || undefined, product: f.product || undefined, quantity: f.quantity || undefined, unit: f.unit || undefined, delivery_place: f.delivery_place || undefined, delivery_days: f.delivery_days ? Number(f.delivery_days) : undefined, category: f.category || undefined, missing_fields: [...new Set(missing)], needs_clarification: Object.values(unknown).some(Boolean) || (parsed?.needs_clarification ?? false) });
      const pub = await mpApi.publishListing(created.id);
      try { localStorage.removeItem(DRAFT_KEY); } catch { /* yoksay */ }
      notify("İlanınız yayımlandı.", "ok"); done(pub.id);
    } catch (e) { setError(errText(e)); notify(errText(e)); } finally { setBusy(false); }
  }
  if (step === 1) return <section aria-label="İlan oluştur">
    <div className="p-card"><h3>1 · Ne yapmak istiyorsunuz?</h3>
      <div className="mp-kind-cards">
        <button className={`mp-kind-card${kind === "demand" ? " on" : ""}`} onClick={() => setKind("demand")} aria-pressed={kind === "demand"}><b>Tedarik talebi</b><span>Bir ürün arıyorum, tedarikçiler fiyat versin.</span><small>Örnek: “300 adet galvaniz boru arıyorum, İstanbul teslim.”</small></button>
        <button className={`mp-kind-card${kind === "supply" ? " on" : ""}`} onClick={() => setKind("supply")} aria-pressed={kind === "supply"}><b>Satış ilanı</b><span>Elimdeki ürünü satıyorum, alıcılar teklif versin.</span><small>Örnek: “Elimde 500 adet galvaniz boru var, satışa hazır.”</small></button>
      </div>
      <label htmlFor="mp-anlat">Anlatın — neye ihtiyacınız var?</label>
      <textarea id="mp-anlat" className="mp-big" rows={7} value={text} onChange={(e) => setText(e.target.value)} placeholder="örn. 300 adet galvaniz boru arıyorum" aria-describedby="mp-anlat-hint" />
      <p id="mp-anlat-hint" className="p-muted">Yalnızca yazdıklarınız kullanılır; belirtmediğiniz fiyat, teknik detay veya ödeme şartı uydurulmaz. Taslağınız otomatik kaydedilir.</p>
      {error && <p role="alert" className="mp-error">{error}</p>}
      <button className="p-btn primary" disabled={busy} onClick={() => void parse()}>{busy ? "Çözümleniyor…" : "Devam et: kontrol adımına geç"}</button>
    </div></section>;
  return <section aria-label="İlanı kontrol et">
    <div className="p-card"><h3>2 · Kontrol edin ve yayımlayın</h3>
      <p className="p-muted">Alanları düzeltebilirsiniz. Yayımlama yalnızca sizin onayınızla, aşağıdaki “Yayımla” düğmesiyle olur.</p>
      <div className="mp-form">
        <label htmlFor="cl-title">Başlık<input id="cl-title" value={f.title} onChange={set("title")} /></label>
        <label htmlFor="cl-product">Ürün<input id="cl-product" value={f.product} onChange={set("product")} /></label>
        <label htmlFor="cl-qty">Miktar<input id="cl-qty" inputMode="decimal" value={f.quantity} onChange={set("quantity")} /></label>
        <label htmlFor="cl-unit">Birim<input id="cl-unit" value={f.unit} onChange={set("unit")} placeholder="adet, kg…" /></label>
        <label htmlFor="cl-place">Teslim yeri<input id="cl-place" value={f.delivery_place} onChange={set("delivery_place")} /></label>
        <label htmlFor="cl-days">Teslim süresi (gün)<input id="cl-days" type="number" min="0" value={f.delivery_days} onChange={set("delivery_days")} /></label>
        <label htmlFor="cl-cat">Kategori<input id="cl-cat" value={f.category} onChange={set("category")} /></label>
      </div>
      {parsed && parsed.missing_questions.length > 0 && <fieldset className="mp-missing"><legend>Eksik bilgiler</legend>
        {parsed.missing_questions.map((q0) => <div key={q0.field} className="mp-missing-row"><span>{q0.question}</span>
          <label><input type="checkbox" checked={!!unknown[q0.field]} onChange={(e) => setUnknown((s) => ({ ...s, [q0.field]: e.target.checked }))} /> {UNKNOWN}</label></div>)}
      </fieldset>}
      {parsed?.document && <><h4>Belge önizlemesi</h4><pre className="p-text" aria-label="İlan belge önizlemesi">{parsed.document}</pre></>}
      {error && <p role="alert" className="mp-error">{error}</p>}
      <div className="p-row"><button className="p-btn" onClick={() => setStep(1)}>Geri dön</button>
      <button className="p-btn primary" disabled={busy} onClick={() => void publish()}>{busy ? "Yayımlanıyor…" : "Yayımla"}</button></div>
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
    if (!offerText.trim()) { setError("Teklifinizi serbest metinle yazın: fiyat, teslim süresi ve ödeme şartları."); return; }
    setBusy(true); setError("");
    try { setOfferParsed(await mpApi.parseOffer(id, offerText)); setOfferStep(2); }
    catch (e) { setError(errText(e)); } finally { setBusy(false); }
  }
  async function submitOffer() {
    setBusy(true); setError("");
    try { await mpApi.createOffer(id, { text: offerText, quantity: (offerParsed as { quantity?: string })?.quantity, unit_price: (offerParsed as { unit_price?: string })?.unit_price, currency: (offerParsed as { currency?: string })?.currency, tax_included: (offerParsed as { tax_included?: boolean })?.tax_included, shipping_included: (offerParsed as { shipping_included?: boolean })?.shipping_included, delivery_days: (offerParsed as { delivery_days?: number })?.delivery_days, payment_terms: (offerParsed as { payment_terms?: string })?.payment_terms }); notify("Teklifiniz gönderildi.", "ok"); setOfferText(""); setOfferStep(1); await load(); }
    catch (e) { setError(errText(e)); notify(errText(e)); } finally { setBusy(false); }
  }
  async function actOffer(offerId: string, act: "msg" | "rev" | "sel") {
    if (act === "sel") { if (!window.confirm("Bu teklifi seçmek istediğinize emin misiniz? Diğer teklifler kapanır.")) return; try { const r = await mpApi.selectOffer(offerId); setAgreement(r.agreement); notify("Teklif seçildi, anlaşma oluştu.", "ok"); await load(); } catch (e) { notify(errText(e)); } return; }
    const note = window.prompt(act === "rev" ? "Revize notunuz (örn. fiyat veya teslim süresi):" : "Sorunuz / mesajınız:"); if (!note) return;
    try { if (act === "rev") { await mpApi.requestRevision(offerId, note); notify("Revize isteği gönderildi.", "ok"); } else { await mpApi.postMessage(offerId, note); notify("Mesaj gönderildi.", "ok"); } await load(); } catch (e) { notify(errText(e)); }
  }
  if (!listing) return <div className="p-card"><button className="p-btn" onClick={back}>← Keşfete dön</button>{error ? <p role="alert" className="mp-error">{error}</p> : <p className="p-muted">Yükleniyor…</p>}</div>;
  return <section aria-label="İlan detayı">
    <button className="p-btn" onClick={back}>← Keşfete dön</button>
    <div className="p-card"><span className="p-pill">{kindLabel(listing.kind)}</span> <StatusBadge status={listing.status} /> <TrustBadge trust={listingTrust(listing)} name={(listing.company ?? listing.owner_company)?.display_name ?? listing.owner_user} />
      <h3>{listingTitle(listing)}</h3>
      {(listing.company ?? listing.owner_company) && <p className="p-muted">Firma: {(listing.company ?? listing.owner_company)!.display_name} · {listingTrust(listing)?.agreements_completed ?? 0} tamamlanmış anlaşma</p>}
      <p>{listing.quantity ? `${listing.quantity} ${listing.unit ?? ""}` : "Miktar belirtilmemiş"} · {listing.delivery_place || "Teslim yeri belirtilmemiş"}{listing.delivery_days != null ? ` · ${listing.delivery_days} gün` : ""}</p>
      {listing.document && <pre className="p-text" aria-label="İlan belgesi">{listing.document}</pre>}
      <p className="p-muted">Bölüm: belge görünümü · Ödeme ve lojistik bu platformda yürütülmez; taraflar kendi arasında anlaşır.</p>
      {error && <p role="alert" className="mp-error">{error}</p>}
    </div>
    {!isOwner && listing.status === "published" && <div className="p-card"><h3>Teklif verin</h3>
      <p className="p-muted">Rakip teklifler size gösterilmez; yalnızca kendi teklifinizi görürsünüz.</p>
      {offerStep === 1 ? <><label htmlFor="of-text">Teklifinizi anlatın</label>
        <textarea id="of-text" className="mp-big" rows={5} value={offerText} onChange={(e) => setOfferText(e.target.value)} placeholder="örn. Birim fiyat 125,50 TL, KDV hariç, 10 günde teslim" />
        <button className="p-btn primary" disabled={busy} onClick={() => void parseOffer()}>Teklifi çözümle ve kontrol et</button></>
      : <><h4>Kontrol edin</h4><pre className="p-text">{JSON.stringify(offerParsed, null, 2)}</pre>
        <p className="p-muted">Gönderim yalnızca “Teklifi gönder” onayınızla yapılır. Belirtmediğiniz tutar tamamlanmaz.</p>
        <div className="p-row"><button className="p-btn" onClick={() => setOfferStep(1)}>Metni düzelt</button>
        <button className="p-btn primary" disabled={busy} onClick={() => void submitOffer()}>Teklifi gönder</button></div></>}
    </div>}
    {isOwner && cmp && <div className="p-card"><h3>Teklifleri karşılaştırın</h3>
      <div className="mp-tablewrap"><table aria-label="Teklif karşılaştırma tablosu"><thead><tr><th>Firma</th><th>Miktar</th><th>Birim fiyat</th><th>Vergi / nakliye</th><th>Teslimat</th><th>Ödeme</th><th>Toplam</th><th>İşlem</th></tr></thead>
      <tbody>{cmp.offers.map((c) => { const line = c.offer.lines[0]; return <tr key={c.offer_id}>
        <td>{c.company?.display_name ?? c.offerer_user} <TrustBadge trust={c.trust ?? (c.company ? { level: c.company.level, has_published: c.company.has_published, has_agreement: c.company.has_agreement, agreements_completed: c.company.agreements_completed } : null)} name={c.company?.display_name ?? c.offerer_user} />{c.comparable ? "" : <span className="mp-warn" role="note"> Karşılaştırılamaz: {c.comparable_reasons.join("; ")}</span>}{c.missing_costs.length > 0 && <span className="mp-warn"> Eksik maliyet: {c.missing_costs.join(", ")}</span>}</td>
        <td>{line?.quantity ?? "—"} {line?.unit ?? ""}</td><td>{line?.unit_price ?? "—"} {line?.currency ?? ""}</td>
        <td>{c.tax_included == null ? "KDV belirtilmemiş" : c.tax_included ? "KDV dahil" : "KDV hariç"} · {c.shipping_included == null ? "nakliye belirtilmemiş" : c.shipping_included ? "nakliye dahil" : `nakliye ayrı${c.shipping_cost ? `: ${c.shipping_cost}` : ""}`}</td>
        <td>{c.delivery_days != null ? `${c.delivery_days} gün` : "—"}</td><td>{c.payment_terms || "—"}</td>
        <td><b>{c.total ?? "—"} {c.currency ?? ""}</b></td>
        <td><div className="p-row"><button className="p-btn sm" onClick={() => void actOffer(c.offer_id, "msg")}>Soru sor</button>
        <button className="p-btn sm" onClick={() => void actOffer(c.offer_id, "rev")}>Revize iste</button>
        <button className="p-btn sm primary" onClick={() => void actOffer(c.offer_id, "sel")}>Teklifi seç</button></div></td></tr>; })}</tbody></table></div>
      {cmp.offers.length === 0 && <p className="p-muted">Henüz teklif gelmedi.</p>}
    </div>}
    {agreement && <div className="p-card" role="status" aria-label="Anlaşma özeti"><h3>Anlaşma oluştu</h3>
      <p>Alıcı: <b>{agreement.buyer_user}</b> · Satıcı: <b>{agreement.seller_user}</b></p>
      <p>Toplam: <b>{agreement.total ?? "—"} {agreement.currency ?? ""}</b> · Tarih: {fmtDate(agreement.created_at)} · Durum: <StatusBadge status={agreement.status} /></p>
      <ol className="mp-timeline" aria-label="Anlaşma durum zaman çizelgesi"><li className="done">Teklif seçildi</li><li className="done">Anlaşma kaydı oluştu ({fmtDate(agreement.created_at)})</li><li>Teslim ve ödeme taraflar arasında yürütülür</li></ol>
    </div>}
    {!isOwner && offers.length > 0 && <div className="p-card"><h3>Teklifim</h3>{offers.map((o) => <p key={o.id}>Revizyon {o.revision_no} · Toplam <b>{o.total ?? "—"} {o.currency ?? ""}</b> · <StatusBadge status={o.status} /></p>)}</div>}
  </section>;
}

function MyListings({ notify, open }: { user: User; notify: Notify; open: (id: string) => void }) {
  const [items, setItems] = useState<MpListing[]>([]); const [error, setError] = useState("");
  useEffect(() => { (async () => { try { setItems((await mpApi.myListings()).listings); } catch (e) { setError(errText(e)); notify(errText(e)); } })(); }, []); // eslint-disable-line
  return <section aria-label="İlanlarım"><div className="p-card"><h3>İlanlarım</h3>{error && <p role="alert" className="mp-error">{error}</p>}
    {items.length === 0 ? <EmptyState title="Henüz ilanınız yok" desc="İlk ilanınızı oluşturduğunuzda burada listelenir." /> : <div className="mp-cards">{items.map((l) => <article key={l.id} className="mp-card"><span className="p-row"><span className="p-pill">{kindLabel(l.kind)}</span><StatusBadge status={l.status} /><TrustBadge trust={listingTrust(l)} /></span><h4 className="mp-card-title">{listingTitle(l)}</h4><p>{l.quantity ? `${l.quantity} ${l.unit ?? ""}` : ""} {fmtDate(l.created_at)}</p><span className="p-row"><button className="p-btn sm" onClick={() => open(l.id)} aria-label={`${listingTitle(l)} detayını aç`}>Detayı aç</button></span></article>)}</div>}
  </div></section>;
}

function MyOffers({ notify, open }: { user: User; notify: Notify; open: (id: string) => void }) {
  const [items, setItems] = useState<MpOffer[]>([]); const [error, setError] = useState(""); const [revText, setRevText] = useState<Record<string, string>>({});
  async function load() { try { setItems((await mpApi.myOffers()).offers); } catch (e) { setError(errText(e)); notify(errText(e)); } }
  useEffect(() => { void load(); }, []); // eslint-disable-line
  async function revise(o: MpOffer) {
    const t = revText[o.id]; if (!t?.trim()) { notify("Revize için yeni teklif metnini yazın."); return; }
    try { const p = await mpApi.parseOffer(o.listing_id, t); await mpApi.reviseOffer(o.id, { text: t, unit_price: (p as { unit_price?: string }).unit_price, quantity: (p as { quantity?: string }).quantity }); notify("Revize teklif gönderildi.", "ok"); await load(); } catch (e) { notify(errText(e)); }
  }
  return <section aria-label="Tekliflerim"><div className="p-card"><h3>Tekliflerim</h3>{error && <p role="alert" className="mp-error">{error}</p>}
    {items.length === 0 ? <EmptyState title="Henüz teklif vermediniz" desc="Keşfet bölümünden bir ilana teklif verdiğinizde burada görünür." /> : items.map((o) => <article key={o.id} className="mp-offer-row">
      <p><b>{o.total ?? "—"} {o.currency ?? ""}</b> · revizyon {o.revision_no} · <StatusBadge status={o.status} /></p>
      <div className="p-row"><button className="p-btn sm" onClick={() => open(o.listing_id)}>İlanı aç</button></div>
      <label htmlFor={`rev-${o.id}`}>Revize metni</label>
      <textarea id={`rev-${o.id}`} rows={3} value={revText[o.id] || ""} onChange={(e) => setRevText((s) => ({ ...s, [o.id]: e.target.value }))} placeholder="örn. Birim fiyat 120 TL, 7 günde teslim" />
      <button className="p-btn sm" onClick={() => void revise(o)}>Revize gönder</button>
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
  return <section aria-label="Mesajlar"><div className="p-card"><h3>Mesajlar ve bildirimler</h3>
    <p className="p-muted">Mesajlar yalnızca ilan sahibi ile teklif veren arasında görünür. Rakip teklifler birbirini görmez.</p>
    {error && <p role="alert" className="mp-error">{error}</p>}
    {notes.length === 0 ? <p className="p-muted">Henüz bildirim yok.</p> : <ul className="mp-notes">{notes.map((n) => <li key={n.id} className={n.read ? "" : "unread"}>
      <span>{n.text} <small>{fmtDate(n.created_at)}</small></span>
      <span className="p-row">{n.listing_id && <button className="p-btn sm" onClick={() => open(n.listing_id!)}>İlan</button>}
      {n.offer_id && <button className="p-btn sm" onClick={() => void loadThread(n.offer_id!)}>Konuşma</button>}
      {!n.read && <button className="p-btn sm" onClick={() => void mpApi.readNotification(n.id).then(loadNotes)}>Okundu işaretle</button>}</span></li>)}</ul>}
    {offerId && <div className="mp-thread"><h4>Konuşma</h4>
      {msgs.length === 0 ? <p className="p-muted">Bu konuşmada henüz mesaj yok.</p> : msgs.map((m) => <p key={m.id} className="mp-msg"><b>{m.sender_user}</b>: {m.body} <small>{fmtDate(m.created_at)}</small></p>)}
      <label htmlFor="mp-msg-input">Yeni mesaj</label>
      <textarea id="mp-msg-input" rows={3} value={draft} onChange={(e) => setDraft(e.target.value)} />
      <button className="p-btn primary" onClick={() => void send()}>Gönder</button></div>}
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
  return <section aria-label="İlanları keşfet">
    <div className="p-card">
      <h3>İlanları keşfet</h3>
      <div className="mp-filters" role="search">
        <label htmlFor="mp-kind">Tür<select id="mp-kind" value={kind} onChange={(e) => setKind(e.target.value)}><option value="">Tümü</option><option value="demand">Tedarik talebi</option><option value="supply">Satış ilanı</option></select></label>
        <label htmlFor="mp-q">Arama metni<input id="mp-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="örn. galvaniz boru" /></label>
        <label htmlFor="mp-cat">Kategori<input id="mp-cat" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="kategori" /></label>
        <label htmlFor="mp-loc">Konum<input id="mp-loc" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="örn. İstanbul" /></label>
        <label htmlFor="mp-days">Teslim süresi (gün, en fazla)<input id="mp-days" type="number" min="0" inputMode="numeric" value={maxDays} onChange={(e) => setMaxDays(e.target.value)} /></label>
        <label htmlFor="mp-sort">Sıralama<select id="mp-sort" value={sort} onChange={(e) => { setSort(e.target.value); void load({ kind, q, category, location, maxDays, sort: e.target.value }); }}><option value="newest">En yeni</option><option value="delivery">Teslim süresi (kısa önce)</option></select></label>
        <span className="p-row"><button className="p-btn primary" onClick={() => void load()}>Filtrele</button><button className="p-btn" disabled={!hasFilters} onClick={clearAll} aria-label="Filtreleri temizle">Temizle</button></span>
      </div>
      <p className="p-muted" role="status" aria-live="polite">{loading ? "İlanlar yükleniyor" : `${items.length} ilan listeleniyor`}{hasFilters ? " · filtre aktif" : ""}</p>
      {error && <p role="alert" className="mp-error">{error}</p>}
      {loading ? <Skeleton lines={3} label="İlanlar yükleniyor" /> : items.length === 0 ? <EmptyState title="İlan bulunamadı" desc="Aramanıza uygun yayımlanmış ilan bulunamadı. Filtreleri genişletip tekrar deneyin." /> :
        <div className="mp-cards">{items.map((l) => <article key={l.id} className="mp-card">
          <span className="p-row"><span className="p-pill">{kindLabel(l.kind)}</span><TrustBadge trust={listingTrust(l)} name={(l.company ?? l.owner_company)?.display_name ?? l.owner_user} /></span>
          <h4 className="mp-card-title">{listingTitle(l)}</h4>
          <p>{l.quantity ? `${l.quantity} ${l.unit ?? ""}` : "Miktar belirtilmemiş"} · {l.delivery_place || "Teslim yeri belirtilmemiş"}{l.delivery_days != null ? ` · ${l.delivery_days} gün` : ""}</p>
          {(l.company ?? l.owner_company) && <p className="p-muted">{(l.company ?? l.owner_company)!.display_name} · {listingTrust(l)?.agreements_completed ?? 0} tamamlanmış anlaşma</p>}
          {l.needs_clarification && <p className="mp-warn">Bazı bilgiler netleştirilecek — sistem uydurmaz, eksikleri gösterir.</p>}
          <span className="p-row"><button className="p-btn sm" onClick={() => open(l.id)} aria-label={`${listingTitle(l)} detayını aç`}>Detayı aç</button></span>
        </article>)}</div>}
    </div>
  </section>;
}
