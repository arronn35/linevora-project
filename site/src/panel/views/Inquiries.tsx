import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api, dt, isEditor, money,
  type Alternative, type DiffChange, type Gap, type Inquiry, type Job, type Quote, type QuoteSummary,
  type Requirement, type Suggestion, type User, type Version,
} from "../api";
import { Banner, Hint, Pill, Steps } from "../ui";

type Sub = "oneriler" | "eksikler" | "alternatifler" | "fark" | "teklifler";

export function InquiriesView({ user, notify }: { user: User; notify: (m: string, k?: "ok" | "err") => void }) {
  const editor = isEditor(user);
  const [inquiries, setInquiries] = useState<Inquiry[]>([]);
  const [filter, setFilter] = useState("");
  const [inquiryId, setInquiryId] = useState<string | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [versionNo, setVersionNo] = useState<number | null>(null);
  const [sub, setSub] = useState<Sub>("oneriler");
  const [suggestions, setSuggestions] = useState<{ requirements: Requirement[]; suggestions: Suggestion[] } | null>(null);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [alternatives, setAlternatives] = useState<Alternative[]>([]);
  const [diff, setDiff] = useState<{ from: number; to: number; changes: DiffChange[] } | null>(null);
  const [diffFrom, setDiffFrom] = useState<number>(1);
  const [diffTo, setDiffTo] = useState<number>(1);
  const [quotes, setQuotes] = useState<QuoteSummary[]>([]);
  const [quoteId, setQuoteId] = useState<string | null>(null);
  const [quoteDetail, setQuoteDetail] = useState<Quote | null>(null);
  const [quoteDoc, setQuoteDoc] = useState<Record<string, unknown> | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [sourceView, setSourceView] = useState<string | null>(null);
  const [products, setProducts] = useState<{ id: string; code: string; names: string[] }[]>([]);
  const [nc, setNc] = useState({ customer: "", title: "" });

  const loadInquiries = useCallback(async () => {
    const r = await api.inquiries(); setInquiries(r.inquiries);
  }, []);
  const loadSub = useCallback(async (id: string, vno: number, s: Sub) => {
    if (s === "oneriler" || s === "teklifler") setSuggestions(await api.suggestions(id, vno));
    if (s === "eksikler") setGaps((await api.gaps(id, vno)).gaps);
    if (s === "alternatifler") setAlternatives((await api.alternatives(id, vno)).alternatives);
  }, []);
  const loadDetail = useCallback(async (id: string) => {
    const vs = (await api.versions(id)).versions;
    setVersions(vs);
    const last = vs.length ? vs[vs.length - 1].version_no : null;
    setVersionNo((cur) => (cur && vs.find((v) => v.version_no === cur) ? cur : last));
    setDiffFrom(vs.length ? vs[0].version_no : 1);
    setDiffTo(last ?? 1);
    setQuotes((await api.quotes(id)).quotes);
    if (last) await loadSub(id, last, "oneriler");
  }, [loadSub]);

  useEffect(() => { void loadInquiries().catch((e) => notify(String(e.message ?? e))); }, [loadInquiries, notify]);
  useEffect(() => { if (inquiryId && versionNo) void loadSub(inquiryId, versionNo, sub).catch((e) => notify(String(e.message ?? e))); }, [sub, inquiryId, versionNo, loadSub, notify]);

  const filtered = useMemo(() => {
    const q = filter.toLocaleLowerCase("tr");
    return inquiries.filter((x) => !q || `${x.title} ${x.customer}`.toLocaleLowerCase("tr").includes(q));
  }, [inquiries, filter]);
  const current = inquiries.find((i) => i.id === inquiryId);
  const done = [!!inquiryId, versions.length > 0, job?.status === "done" || !!suggestions?.requirements.length, quotes.length > 0, quotes.some((q) => q.status === "dışa aktarıldı")];

  async function selectInquiry(id: string) {
    setInquiryId(id); setVersionNo(null); setSub("oneriler"); setJob(null); setQuoteId(null); setDiff(null); setQuoteDetail(null);
    try { await loadDetail(id); } catch (e) { notify((e as Error).message); }
  }
  async function onNew(e: React.FormEvent) {
    e.preventDefault();
    try {
      const q = await api.createInquiry(nc.customer.trim(), nc.title.trim());
      setNc({ customer: "", title: "" }); setInquiryId(q.id);
      await loadInquiries(); await loadDetail(q.id);
      notify("Talep açıldı.", "ok");
    } catch (err) { notify((err as Error).message); }
  }
  async function onUpload(e: React.FormEvent) {
    e.preventDefault();
    const input = (e.target as HTMLFormElement).querySelector<HTMLInputElement>('input[type="file"]');
    const f = input?.files?.[0]; if (!f || !inquiryId) return;
    try { const v = await api.uploadVersion(inquiryId, f); setVersionNo(v.version_no); await loadDetail(inquiryId); notify(`Sürüm ${v.version_no} yüklendi.`, "ok"); }
    catch (err) { notify(`Yükleme hatası: ${(err as Error).message}`); }
  }
  async function onProcess() {
    if (!inquiryId || !versionNo) return;
    try {
      const p = await api.process(inquiryId, versionNo);
      setJob({ job_id: p.job_id, kind: "process_version", status: p.status, attempts: 0, result: null, error: null });
      for (let i = 0; i < 60; i++) {
        const j = await api.job(p.job_id); setJob(j);
        if (j.status === "done" || j.status === "failed") {
          if (j.status === "done") { await loadDetail(inquiryId); notify("İşleme tamamlandı.", "ok"); }
          else notify(`İş başarısız: ${j.error ?? ""}`);
          break;
        }
        await new Promise((r) => setTimeout(r, 500));
      }
    } catch (err) { notify(`İşleme hatası: ${(err as Error).message}`); }
  }

  function highlighted(pageNo: number, quote: string) {
    const v = versions.find((x) => x.version_no === versionNo);
    const pg = v?.pages.find((x) => x.number === pageNo);
    if (!pg) return "Sayfa metni bulunamadı.";
    const i = pg.text.toLocaleLowerCase("tr").indexOf(quote.toLocaleLowerCase("tr"));
    if (i < 0) return pg.text;
    return <>{pg.text.slice(0, i)}<mark>{pg.text.slice(i, i + quote.length)}</mark>{pg.text.slice(i + quote.length)}</>;
  }

  return (
    <div className="p-grid2">
      <div className="p-card">
        <h3>Talepler</h3>
        <label className="p-muted">Ara <input aria-label="Talep ara" placeholder="müşteri / başlık" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ width: "100%", marginTop: 4 }} /></label>
        <div className="p-list" style={{ marginTop: 10 }}>
          {filtered.length === 0 && <p className="p-muted">Kayıt yok.</p>}
          {filtered.map((q) => (
            <button key={q.id} className={`p-listitem${q.id === inquiryId ? " on" : ""}`} onClick={() => void selectInquiry(q.id)}>
              <b>{q.title}</b><span className="p-muted">{q.customer} · {q.status}</span>
            </button>
          ))}
        </div>
        {editor && (
          <>
            <h4>Yeni Talep</h4>
            <form className="p-stack" onSubmit={onNew}>
              <input placeholder="Müşteri" required value={nc.customer} onChange={(e) => setNc({ ...nc, customer: e.target.value })} />
              <input placeholder="Başlık" required value={nc.title} onChange={(e) => setNc({ ...nc, title: e.target.value })} />
              <button className="p-btn primary" type="submit">Aç</button>
            </form>
          </>
        )}
      </div>

      <div>
        {!inquiryId && <div className="p-card"><p className="p-muted">Soldan bir talep seçin.</p></div>}
        {inquiryId && current && (
          <>
            <div className="p-card">
              <h3>{current.title}</h3>
              <p className="p-muted">{current.customer} · <Pill t={current.status} /></p>
              <Steps done={done} />
              <h4>Sürümler</h4>
              <Hint>Her yükleme yeni sürümdür; eskiler silinmez. Müşteri düzeltme gönderirse yeni dosya olarak yükleyin — Fark sekmesi değişenleri gösterir.</Hint>
              {versions.length === 0 && <p className="p-muted">Henüz sürüm yok; aşağıdan dosya yükleyin.</p>}
              {versions.length > 0 && (
                <table><thead><tr><th>No</th><th>Dosya</th><th>Sayfa</th><th /></tr></thead><tbody>
                  {versions.map((v) => (
                    <tr key={v.id}>
                      <td>{v.version_no}</td><td>{v.filename}</td><td>{v.pages.length}</td>
                      <td>{v.version_no === versionNo ? <b>seçili</b> : <button className="p-btn sm" onClick={() => { setVersionNo(v.version_no); setJob(null); setDiff(null); }}>Seç</button>}</td>
                    </tr>
                  ))}
                </tbody></table>
              )}
              {versions.filter((v) => v.version_no === versionNo).map((v) => (
                <details key={v.id} style={{ marginTop: 8 }}><summary style={{ cursor: "pointer", fontSize: 13 }}>Metin önizleme — Sürüm {v.version_no}</summary>
                  <pre className="p-text">{v.pages.map((p) => `--- Sayfa ${p.number} ---\n${p.text}`).join("\n\n")}</pre>
                </details>
              ))}
              {editor && (
                <>
                  <h4>Sürüm Yükle</h4>
                  <form className="p-inline" onSubmit={onUpload}>
                    <input type="file" accept=".pdf,.txt,.md" required aria-label="Sürüm dosyası" />
                    <button className="p-btn primary" type="submit">Yükle</button>
                  </form>
                </>
              )}
            </div>

            {versionNo && (
              <>
                <div className="p-card">
                  <h3>Sürüm {versionNo} İşleme</h3>
                  <Hint>Sistem metinden gereksinimleri çıkarır ve katalogla eşleştirir. Sonuç Öneriler sekmesine düşer; her öneriyi kaynak alıntısıyla doğrulayın.</Hint>
                  <div className="p-row">
                    {editor && <button className="p-btn primary" onClick={() => void onProcess()}>Gereksinim çıkar + eşleştir</button>}
                    {job ? <span>İş: <Pill t={job.status} /> (deneme {job.attempts})</span> : <span className="p-muted">Henüz işletilmedi.</span>}
                    {job && <button className="p-btn sm" onClick={async () => { try { const j = await api.job(job.job_id); setJob(j); if (j.status === "done" && inquiryId) await loadDetail(inquiryId); } catch (e) { notify((e as Error).message); } }}>Durumu yenile</button>}
                  </div>
                </div>
                <div className="p-card">
                  <div className="p-subtabs" role="tablist" aria-label="Sürüm görünümleri">
                    {([["oneriler", "Öneriler"], ["eksikler", "Eksikler"], ["alternatifler", "Alternatifler"], ["fark", "Fark"], ["teklifler", "Teklifler"]] as [Sub, string][]).map(([k, l]) => (
                      <button key={k} role="tab" aria-selected={sub === k} className={`p-subtab${sub === k ? " on" : ""}`} onClick={() => { setSub(k); if (k === "teklifler") void api.products().then((r) => setProducts(r.products)).catch(() => {}); }}>{l}</button>
                    ))}
                  </div>
                  {sub === "oneriler" && <SubOneriler data={suggestions} editor={editor} sourceView={sourceView} setSourceView={setSourceView} highlighted={highlighted} notify={notify} reload={async () => { if (inquiryId && versionNo) setSuggestions(await api.suggestions(inquiryId, versionNo)); }} />}
                  {sub === "eksikler" && <SubEksikler gaps={gaps} editor={editor} notify={notify} reload={async () => { if (inquiryId && versionNo) setGaps((await api.gaps(inquiryId, versionNo)).gaps); }} />}
                  {sub === "alternatifler" && <SubAlternatifler items={alternatives} />}
                  {sub === "fark" && <SubFark versions={versions} diff={diff} diffFrom={diffFrom} diffTo={diffTo} setDiffFrom={setDiffFrom} setDiffTo={setDiffTo} onCompare={async () => { if (!inquiryId) return; try { const d = await api.diff(inquiryId, diffFrom, diffTo); setDiff({ from: d.from_version, to: d.to_version, changes: d.changes }); } catch (e) { notify((e as Error).message); } }} />}
                  {sub === "teklifler" && <SubTeklifler suggestions={suggestions} products={products} quotes={quotes} quoteId={quoteId} quoteDetail={quoteDetail} editor={editor} notify={notify}
                    setQuoteDoc={setQuoteDoc}
                    reloadQuotes={async () => { if (inquiryId) setQuotes((await api.quotes(inquiryId)).quotes); }}
                    selectQuote={async (id: string) => { setQuoteId(id); try { setQuoteDetail(await api.quote(id)); } catch (e) { notify((e as Error).message); } }}
                    setQuoteDetail={setQuoteDetail} setQuoteId={setQuoteId} inquiryId={inquiryId} versionNo={versionNo} />}
                </div>
              </>
            )}
          </>
        )}
      </div>
      {quoteDoc && <QuoteModal doc={quoteDoc} close={() => setQuoteDoc(null)} notify={notify} />}
    </div>
  );
}

function SubOneriler({ data, editor, sourceView, setSourceView, highlighted, notify, reload }: {
  data: { requirements: Requirement[]; suggestions: Suggestion[] } | null;
  editor: boolean; sourceView: string | null; setSourceView: (v: string | null) => void;
  highlighted: (p: number, q: string) => React.ReactNode; notify: (m: string, k?: "ok" | "err") => void; reload: () => Promise<void>;
}) {
  const desc = <Hint>Skor 0–1 arasındadır: 0.85 ve üzeri genelde birebir eşleşme, altı dikkatli inceleme ister. “bekliyor” rozeti, ekibin henüz karar vermediği anlamına gelir.</Hint>;
  if (!data || !data.requirements.length) return <>{desc}<p className="p-muted">Gereksinim yok. Önce sürümü işletin.</p></>;
  return (
    <>
      {desc}
      <div className="p-stack">
        {data.requirements.map((r) => {
          const sugs = data.suggestions.filter((s) => s.requirement_id === r.id);
          const feat = Object.entries(r.features || {}).map(([k, v]) => `${k}=${String(v)}`).join(", ");
          return (
            <div key={r.id} className="p-card" style={{ marginBottom: 0 }}>
              <b>{r.product_type}</b> <span className="p-muted">{r.quantity ?? "?"} {r.unit ?? ""}{feat ? ` · ${feat}` : ""}</span>
              <br /><span className="p-muted">Kaynak: sayfa {r.source.page} — “{r.source.quote}”</span>{" "}
              <button className="p-btn sm" onClick={() => setSourceView(sourceView === r.id ? null : r.id)}>Kaynağı göster</button>
              {sourceView === r.id && <pre className="p-srcview">{highlighted(r.source.page, r.source.quote)}</pre>}
              {sugs.length === 0 ? <p className="p-muted">Öneri yok.</p> : (
                <table><thead><tr><th>Ürün</th><th>Skor</th><th /><th>Gerekçe</th></tr></thead><tbody>
                  {sugs.map((s) => (
                    <tr key={s.id}>
                      <td><b>{s.product.code}</b><br /><span className="p-muted">{s.product.names.join(", ")}</span></td>
                      <td>{s.score.toFixed(2)}</td>
                      <td><div className="p-scorebar"><div style={{ width: `${Math.round(s.score * 100)}%` }} /></div></td>
                      <td>{s.reasons.map((x, i) => <span key={i}>{x}<br /></span>)}<Pill t={s.status} />
                        {editor && s.id && <> <button className="p-btn sm" onClick={async () => { try { await api.decideSuggestion(s.id, "onaylandı"); await reload(); } catch (e) { notify((e as Error).message); } }}>Kabul</button> <button className="p-btn sm" onClick={async () => { try { await api.decideSuggestion(s.id, "reddedildi"); await reload(); } catch (e) { notify((e as Error).message); } }}>Reddet</button></>}
                      </td>
                    </tr>
                  ))}
                </tbody></table>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

function SubEksikler({ gaps, editor, notify, reload }: { gaps: Gap[]; editor: boolean; notify: (m: string, k?: "ok" | "err") => void; reload: () => Promise<void> }) {
  const [answerFor, setAnswerFor] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const desc = <Hint>Bunlar müşteriye sorulacak sorulardır. “zorunlu” olanlar teklife girmeden tamamlanmalı; “bilgi” olanlar kaliteyi artırır.</Hint>;
  if (!gaps.length) return <>{desc}<p className="p-muted">Eksik yok — teklif kurulabilir.</p></>;
  return (
    <>
      {desc}
      <div className="p-row" style={{ marginBottom: 10 }}>
        <button className="p-btn sm" onClick={async () => {
          const lines = ["Merhaba, teklif hazırlamak için şu bilgileri rica ediyoruz:", ...gaps.map((g) => `- ${g.question}`)];
          try { await navigator.clipboard.writeText(lines.join("\n")); notify("Soru listesi panoya kopyalandı.", "ok"); } catch (e) { notify(`Kopyalama başarısız: ${(e as Error).message}`); }
        }}>Soru listesini kopyala</button>
      </div>
      <table><thead><tr><th>Alan</th><th>Soru</th><th>Önem</th><th>Durum</th><th /></tr></thead><tbody>
        {gaps.map((g) => (
          <tr key={g.id}>
            <td>{g.field}</td><td>{g.question}</td><td><Pill t={g.severity} /></td>
            <td><Pill t={g.status} />{g.answer ? <><br />{g.answer}</> : null}</td>
            <td>{editor && g.status === "açık" && (answerFor === g.id
              ? <span className="p-row"><input value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Yanıt / not" aria-label="Eksik yanıtı" /><button className="p-btn sm primary" onClick={async () => { try { await api.answerGap(g.id, answer); setAnswerFor(null); setAnswer(""); await reload(); } catch (e) { notify((e as Error).message); } }}>Kaydet</button></span>
              : <button className="p-btn sm" onClick={() => { setAnswerFor(g.id); setAnswer(""); }}>Yanıtla</button>)}</td>
          </tr>
        ))}
      </tbody></table>
    </>
  );
}

function SubAlternatifler({ items }: { items: Alternative[] }) {
  const desc = <Hint>Birebir ürün yoksa en yakın adaylar ölçüte göre karşılaştırılır. “Uyum” sütunu hangi şartın tuttuğunu gösterir; önerebilir misiniz kararı sizde.</Hint>;
  if (!items.length) return <>{desc}<p className="p-muted">Alternatif yok (birebir eşleşme var ya da sürüm işletilmedi).</p></>;
  return (
    <>
      {desc}
      <div className="p-stack">
        {items.map((a) => (
          <div key={a.id} className="p-card" style={{ marginBottom: 0 }}>
            <b>{a.product.code}</b> <span className="p-muted">{a.product.names.join(", ")} · skor {a.score.toFixed(2)}</span> <Pill t={a.status} />
            <table><thead><tr><th>Ölçüt</th><th>İstenen</th><th>Sunulan</th><th>Uyum</th></tr></thead><tbody>
              {a.comparison.map((r, i) => <tr key={i}><td>{r.criterion}</td><td>{r.wanted}</td><td>{r.offered}</td><td>{r.match ? "Evet" : "—"}</td></tr>)}
            </tbody></table>
            <span className="p-muted">{a.reasons.map((x, i) => <span key={i}>{x}<br /></span>)}</span>
          </div>
        ))}
      </div>
    </>
  );
}

function SubFark({ versions, diff, diffFrom, diffTo, setDiffFrom, setDiffTo, onCompare }: {
  versions: Version[]; diff: { from: number; to: number; changes: DiffChange[] } | null;
  diffFrom: number; diffTo: number; setDiffFrom: (n: number) => void; setDiffTo: (n: number) => void; onCompare: () => Promise<void>;
}) {
  return (
    <>
      <Hint>İki sürüm arasında miktarı, birimi veya özellikleri değişen; eklenen ve çıkarılan kalemler.</Hint>
      <form className="p-inline" onSubmit={(e) => { e.preventDefault(); void onCompare(); }}>
        <select aria-label="Fark başlangıç sürümü" value={diffFrom} onChange={(e) => setDiffFrom(Number(e.target.value))}>{versions.map((v) => <option key={v.id} value={v.version_no}>Sürüm {v.version_no}</option>)}</select>
        <select aria-label="Fark bitiş sürümü" value={diffTo} onChange={(e) => setDiffTo(Number(e.target.value))}>{versions.map((v) => <option key={v.id} value={v.version_no}>Sürüm {v.version_no}</option>)}</select>
        <button className="p-btn primary" type="submit">Karşılaştır</button>
      </form>
      {!diff && <p className="p-muted" style={{ marginTop: 10 }}>İki sürüm seçip karşılaştırın.</p>}
      {diff && diff.changes.length === 0 && <p className="p-muted" style={{ marginTop: 10 }}>Fark yok.</p>}
      {diff && diff.changes.length > 0 && (
        <table style={{ marginTop: 10 }}><thead><tr><th>Tür</th><th>Ürün</th><th>Alan</th><th>Eski</th><th>Yeni</th></tr></thead><tbody>
          {diff.changes.map((c, i) => <tr key={i}><td><Pill t={c.type} /></td><td>{c.product_type}</td><td>{c.field}</td><td>{c.old}</td><td>{c.new}</td></tr>)}
        </tbody></table>
      )}
    </>
  );
}

function SubTeklifler({ suggestions, products, quotes, quoteId, quoteDetail, editor, notify, setQuoteDoc, reloadQuotes, selectQuote, setQuoteDetail, setQuoteId, inquiryId, versionNo }: {
  suggestions: { requirements: Requirement[]; suggestions: Suggestion[] } | null;
  products: { id: string; code: string; names: string[] }[];
  quotes: QuoteSummary[]; quoteId: string | null; quoteDetail: Quote | null; editor: boolean;
  notify: (m: string, k?: "ok" | "err") => void; setQuoteDoc: (d: Record<string, unknown> | null) => void;
  reloadQuotes: () => Promise<void>; selectQuote: (id: string) => Promise<void>;
  setQuoteDetail: (q: Quote | null) => void; setQuoteId: (id: string | null) => void;
  inquiryId: string | null; versionNo: number | null;
}) {
  const reqs = suggestions?.requirements ?? [];
  const sugs = suggestions?.suggestions ?? [];
  async function build(edit: boolean) {
    const rows = Array.from(document.querySelectorAll<HTMLElement>("[data-req]"));
    const lines: { requirement_id: string; product_id: string; quantity: number | null }[] = [];
    for (const row of rows) {
      const prod = row.querySelector<HTMLSelectElement>(".q-prod")?.value;
      const qtyRaw = row.querySelector<HTMLInputElement>(".q-qty")?.value;
      if (prod) lines.push({ requirement_id: row.dataset.req!, product_id: prod, quantity: qtyRaw === "" || qtyRaw == null ? null : Number(qtyRaw) });
    }
    if (!lines.length) { notify("En az bir kalem için ürün seçin."); return; }
    try {
      if (edit && quoteId) { setQuoteDetail(await api.updateQuoteLines(quoteId, lines)); }
      else if (inquiryId && versionNo) { const q = await api.createQuote(inquiryId, versionNo, lines); setQuoteId(q.id); setQuoteDetail(q); }
      await reloadQuotes(); notify("Teklif kaydedildi.", "ok");
    } catch (e) { notify(`Teklif hatası: ${(e as Error).message}`); }
  }
  return (
    <>
      <Hint>Ürünler en iyi öneriye göre önceden seçilidir; miktar boş bırakılırsa gereksinimdeki miktar kullanılır. Fiyat, teklif kurulduğu anda yürürlükteki sürümden kilitlenir.</Hint>
      <h4>Teklifler</h4>
      {quotes.length === 0 ? <p className="p-muted">Bu talepte teklif yok.</p> : (
        <div className="p-list">
          {quotes.map((q) => (
            <button key={q.id} className={`p-listitem${q.id === quoteId ? " on" : ""}`} onClick={() => void selectQuote(q.id)}>
              <span><b>Sürüm {q.version_no} teklifi</b> <Pill t={q.status} /></span>
              <span className="p-muted">{q.created_by}{q.approved_by ? ` · onay: ${q.approved_by}` : ""}</span>
            </button>
          ))}
        </div>
      )}
      {editor && reqs.length > 0 && (
        <>
          <h4>Kalemler</h4>
          <table><thead><tr><th>Gereksinim</th><th>Ürün</th><th>Miktar</th></tr></thead><tbody>
            {reqs.map((r) => {
              const top = sugs.find((s) => s.requirement_id === r.id);
              return (
                <tr key={r.id} data-req={r.id}>
                  <td><b>{r.product_type}</b><br /><span className="p-muted">{r.quantity ?? "?"} {r.unit ?? ""}</span></td>
                  <td><select className="q-prod" aria-label={`Ürün — ${r.product_type}`} defaultValue={products.find((p) => top && p.code === top.product.code)?.id ?? ""}>
                    <option value="">— seçin —</option>
                    {products.map((p) => <option key={p.id} value={p.id}>{p.code} — {p.names.join(", ")}</option>)}
                  </select></td>
                  <td><input className="q-qty" type="number" min="0" step="any" placeholder={r.quantity != null ? String(r.quantity) : ""} style={{ width: 110 }} aria-label={`Miktar — ${r.product_type}`} /></td>
                </tr>
              );
            })}
          </tbody></table>
          <div className="p-row" style={{ marginTop: 10 }}>
            <button className="p-btn primary" onClick={() => void build(false)}>Yeni teklif oluştur</button>
            {quoteDetail?.status === "taslak" && <button className="p-btn" onClick={() => void build(true)}>Seçili taslağı güncelle</button>}
          </div>
        </>
      )}
      {quoteDetail && <QuoteDetail q={quoteDetail} editor={editor} notify={notify} setQuoteDetail={setQuoteDetail} reloadQuotes={reloadQuotes} setQuoteDoc={setQuoteDoc} />}
    </>
  );
}

function QuoteDetail({ q, editor, notify, setQuoteDetail, reloadQuotes, setQuoteDoc }: {
  q: Quote; editor: boolean; notify: (m: string, k?: "ok" | "err") => void;
  setQuoteDetail: (q: Quote | null) => void; reloadQuotes: () => Promise<void>; setQuoteDoc: (d: Record<string, unknown> | null) => void;
}) {
  const admin = editor; // submit editör, approve/return panel üstünden rol kontrolü API'de
  async function act(action: "submit" | "return" | "approve") {
    if (action === "approve" && !window.confirm("Teklif onaylanacak ve dışa aktarmaya hazır olacak. Emin misiniz?")) return;
    try { setQuoteDetail(await api.quoteAction(q.id, action)); await reloadQuotes(); notify("Teklif güncellendi.", "ok"); }
    catch (e) { notify((e as Error).message); }
  }
  async function onExport() {
    if (!window.confirm("Onaylanmış teklif dışa aktarılacak ve belge üretilecek. Emin misiniz?")) return;
    try { const doc = await api.exportQuote(q.id); setQuoteDoc(doc); setQuoteDetail(await api.quote(q.id)); await reloadQuotes(); }
    catch (e) { notify((e as Error).message); }
  }
  async function onPreview() {
    try {
      const terms = (await api.terms()).terms;
      const t = terms.find((x) => x.id === q.terms_version_id);
      setQuoteDoc({ preview: true, quote_id: q.id, status: q.status, customer: q.customer, version_no: q.version_no,
        lines: q.lines.map((l) => ({ product_code: l.product.code, product_names: l.product.names, quantity: l.quantity, unit: l.unit, unit_price: l.unit_price, currency: l.currency, amount: l.amount })),
        totals: q.totals, terms: t ? { name: t.name, text: t.text } : null, prepared_by: q.created_by, approved_by: q.approved_by });
    } catch (e) { notify((e as Error).message); }
  }
  return (
    <div style={{ marginTop: 14 }}>
      <h4>Teklif Detayı <Pill t={q.status} /></h4>
      <table><thead><tr><th>Ürün</th><th>Miktar</th><th>Birim fiyat</th><th>Tutar</th></tr></thead><tbody>
        {q.lines.map((l) => <tr key={l.id}><td><b>{l.product.code}</b><br /><span className="p-muted">{l.product.names.join(", ")}</span></td><td>{l.quantity} {l.unit}</td><td>{money(l.unit_price, l.currency)}</td><td>{money(l.amount, l.currency)}</td></tr>)}
        {q.totals.map((t) => <tr key={t.currency} className="p-total-row"><td colSpan={3}>Toplam</td><td>{money(t.amount, t.currency)}</td></tr>)}
      </tbody></table>
      <p className="p-muted">Hazırlayan: {q.created_by}{q.approved_by ? ` · Onaylayan: ${q.approved_by}` : ""}<br />Kalem fiyatları, kurulduğu anda yürürlükteki fiyat sürümünden kilitlenmiştir.</p>
      <div className="p-row">
        {editor && q.status === "taslak" && <button className="p-btn primary" onClick={() => void act("submit")}>İncelemeye sun</button>}
        {q.status === "incelemede" && <><button className="p-btn primary" onClick={() => void act("approve")}>Onayla</button><button className="p-btn" onClick={() => void act("return")}>İade et</button></>}
        <button className="p-btn" onClick={() => void onPreview()}>Önizleme</button>
        {(q.status === "onaylandı" || q.status === "dışa aktarıldı") && <button className="p-btn primary" onClick={() => void onExport()}>Dışa aktar</button>}
        {void admin}
      </div>
    </div>
  );
}

function QuoteModal({ doc, close, notify }: { doc: Record<string, unknown>; close: () => void; notify: (m: string, k?: "ok" | "err") => void }) {
  const lines = (doc.lines as { product_code: string; product_names?: string[]; quantity: number; unit: string; unit_price: number; currency: string; amount: number }[]) ?? [];
  const totals = (doc.totals as { currency: string; amount: number }[]) ?? [];
  const terms = doc.terms as { name: string; text: string } | null;
  async function downloadPdf() {
    const token = localStorage.getItem("linevora_token");
    try {
      const res = await fetch(`/v1/quotes/${String(doc.quote_id)}/export.pdf`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      if (!res.ok) throw new Error(`PDF alınamadı (${res.status})`);
      const blob = await res.blob();
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "teklif.pdf"; a.click(); URL.revokeObjectURL(a.href);
    } catch (e) { notify((e as Error).message); }
  }
  return (
    <div className="p-modal-veil" onClick={(e) => { if (e.target === e.currentTarget) close(); }}>
      <div className="p-modal" role="dialog" aria-modal="true" aria-label="Teklif belgesi">
        <div className="p-quote-head"><h2>Teklif {doc.preview ? "(Önizleme)" : ""}</h2><button className="p-btn sm" onClick={close}>Kapat</button></div>
        <p><b>Müşteri:</b> {String(doc.customer ?? "")} &nbsp; <b>Sürüm:</b> {String(doc.version_no ?? "")} &nbsp; <Pill t={String(doc.status ?? "")} /></p>
        <table><thead><tr><th>Ürün</th><th>Miktar</th><th>Birim fiyat</th><th>Tutar</th></tr></thead><tbody>
          {lines.map((l, i) => <tr key={i}><td><b>{l.product_code}</b><br /><span className="p-muted">{(l.product_names ?? []).join(", ")}</span></td><td>{l.quantity} {l.unit}</td><td>{money(l.unit_price, l.currency)}</td><td>{money(l.amount, l.currency)}</td></tr>)}
          {totals.map((t) => <tr key={t.currency} className="p-total-row"><td colSpan={3}>Toplam</td><td>{money(t.amount, t.currency)}</td></tr>)}
        </tbody></table>
        {terms && <><h4>{terms.name}</h4><div className="p-termsbox">{terms.text}</div></>}
        <p className="p-muted">Hazırlayan: {String(doc.prepared_by ?? "")}{doc.approved_by ? ` · Onaylayan: ${String(doc.approved_by)}` : ""}</p>
        {!doc.preview && <div className="p-row"><button className="p-btn primary" onClick={() => void downloadPdf()}>PDF indir</button></div>}
        <span className="p-muted">{dt(Date.now() / 1000)}</span>
      </div>
    </div>
  );
}
