import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api, dt, isEditor, money,
  type Alternative, type DiffChange, type Gap, type Inquiry, type Job, type Quote, type QuoteSummary,
  type Requirement, type Suggestion, type User, type Version,
} from "../api";
import { Banner, Hint, Pill, Steps } from "../ui";

type Sub = "suggestions" | "gaps" | "alternatives" | "diff" | "quotes";

export function InquiriesView({ user, notify }: { user: User; notify: (m: string, k?: "ok" | "err") => void }) {
  const editor = isEditor(user);
  const [inquiries, setInquiries] = useState<Inquiry[]>([]);
  const [filter, setFilter] = useState("");
  const [inquiryId, setInquiryId] = useState<string | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [versionNo, setVersionNo] = useState<number | null>(null);
  const [sub, setSub] = useState<Sub>("suggestions");
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
    if (s === "suggestions" || s === "quotes") setSuggestions(await api.suggestions(id, vno));
    if (s === "gaps") setGaps((await api.gaps(id, vno)).gaps);
    if (s === "alternatives") setAlternatives((await api.alternatives(id, vno)).alternatives);
  }, []);
  const loadDetail = useCallback(async (id: string) => {
    const vs = (await api.versions(id)).versions;
    setVersions(vs);
    const last = vs.length ? vs[vs.length - 1].version_no : null;
    setVersionNo((cur) => (cur && vs.find((v) => v.version_no === cur) ? cur : last));
    setDiffFrom(vs.length ? vs[0].version_no : 1);
    setDiffTo(last ?? 1);
    setQuotes((await api.quotes(id)).quotes);
    if (last) await loadSub(id, last, "suggestions");
  }, [loadSub]);

  useEffect(() => { void loadInquiries().catch((e) => notify(String(e.message ?? e))); }, [loadInquiries, notify]);
  useEffect(() => { if (inquiryId && versionNo) void loadSub(inquiryId, versionNo, sub).catch((e) => notify(String(e.message ?? e))); }, [sub, inquiryId, versionNo, loadSub, notify]);

  const filtered = useMemo(() => {
    const q = filter.toLocaleLowerCase("en");
    return inquiries.filter((x) => !q || `${x.title} ${x.customer}`.toLocaleLowerCase("en").includes(q));
  }, [inquiries, filter]);
  const current = inquiries.find((i) => i.id === inquiryId);
  const done = [!!inquiryId, versions.length > 0, job?.status === "done" || !!suggestions?.requirements.length, quotes.length > 0, quotes.some((q) => q.status === "exported")];

  async function selectInquiry(id: string) {
    setInquiryId(id); setVersionNo(null); setSub("suggestions"); setJob(null); setQuoteId(null); setDiff(null); setQuoteDetail(null);
    try { await loadDetail(id); } catch (e) { notify((e as Error).message); }
  }
  async function onNew(e: React.FormEvent) {
    e.preventDefault();
    try {
      const q = await api.createInquiry(nc.customer.trim(), nc.title.trim());
      setNc({ customer: "", title: "" }); setInquiryId(q.id);
      await loadInquiries(); await loadDetail(q.id);
      notify("Inquiry opened.", "ok");
    } catch (err) { notify((err as Error).message); }
  }
  async function onUpload(e: React.FormEvent) {
    e.preventDefault();
    const input = (e.target as HTMLFormElement).querySelector<HTMLInputElement>('input[type="file"]');
    const f = input?.files?.[0]; if (!f || !inquiryId) return;
    try { const v = await api.uploadVersion(inquiryId, f); setVersionNo(v.version_no); await loadDetail(inquiryId); notify(`Version ${v.version_no} uploaded.`, "ok"); }
    catch (err) { notify(`Upload error: ${(err as Error).message}`); }
  }
  async function onProcess() {
    if (!inquiryId || !versionNo) return;
    try {
      const p = await api.process(inquiryId, versionNo);
      setJob({ job_id: p.job_id, kind: "process_version", status: p.status, attempts: 0, result: null, error: null });
      for (let i = 0; i < 60; i++) {
        const j = await api.job(p.job_id); setJob(j);
        if (j.status === "done" || j.status === "failed") {
          if (j.status === "done") { await loadDetail(inquiryId); notify("Processing complete.", "ok"); }
          else notify(`Job failed: ${j.error ?? ""}`);
          break;
        }
        await new Promise((r) => setTimeout(r, 500));
      }
    } catch (err) { notify(`Processing error: ${(err as Error).message}`); }
  }

  function highlighted(pageNo: number, quote: string) {
    const v = versions.find((x) => x.version_no === versionNo);
    const pg = v?.pages.find((x) => x.number === pageNo);
    if (!pg) return "Page text not found.";
    const i = pg.text.toLocaleLowerCase("en").indexOf(quote.toLocaleLowerCase("en"));
    if (i < 0) return pg.text;
    return <>{pg.text.slice(0, i)}<mark>{pg.text.slice(i, i + quote.length)}</mark>{pg.text.slice(i + quote.length)}</>;
  }

  return (
    <div className="p-grid2">
      <div className="p-card">
        <h3>Inquiries</h3>
        <label className="p-muted">Search <input aria-label="Search inquiries" placeholder="customer / title" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ width: "100%", marginTop: 4 }} /></label>
        <div className="p-list" style={{ marginTop: 10 }}>
          {filtered.length === 0 && <p className="p-muted">No records.</p>}
          {filtered.map((q) => (
            <button key={q.id} className={`p-listitem${q.id === inquiryId ? " on" : ""}`} onClick={() => void selectInquiry(q.id)}>
              <b>{q.title}</b><span className="p-muted">{q.customer} · {q.status}</span>
            </button>
          ))}
        </div>
        {editor && (
          <>
            <h4>New Inquiry</h4>
            <form className="p-stack" onSubmit={onNew}>
              <input placeholder="Customer" required value={nc.customer} onChange={(e) => setNc({ ...nc, customer: e.target.value })} />
              <input placeholder="Title" required value={nc.title} onChange={(e) => setNc({ ...nc, title: e.target.value })} />
              <button className="p-btn primary" type="submit">Open</button>
            </form>
          </>
        )}
      </div>

      <div>
        {!inquiryId && <div className="p-card"><p className="p-muted">Select an inquiry on the left.</p></div>}
        {inquiryId && current && (
          <>
            <div className="p-card">
              <h3>{current.title}</h3>
              <p className="p-muted">{current.customer} · <Pill t={current.status} /></p>
              <Steps done={done} />
              <h4>Versions</h4>
              <Hint>Every upload is a new version; older ones are never deleted. If the customer sends a correction, upload it as a new file — the Diff tab shows what changed.</Hint>
              {versions.length === 0 && <p className="p-muted">No versions yet; upload a file below.</p>}
              {versions.length > 0 && (
                <table><thead><tr><th>No</th><th>File</th><th>Pages</th><th /></tr></thead><tbody>
                  {versions.map((v) => (
                    <tr key={v.id}>
                      <td>{v.version_no}</td><td>{v.filename}</td><td>{v.pages.length}</td>
                      <td>{v.version_no === versionNo ? <b>selected</b> : <button className="p-btn sm" onClick={() => { setVersionNo(v.version_no); setJob(null); setDiff(null); }}>Select</button>}</td>
                    </tr>
                  ))}
                </tbody></table>
              )}
              {versions.filter((v) => v.version_no === versionNo).map((v) => (
                <details key={v.id} style={{ marginTop: 8 }}><summary style={{ cursor: "pointer", fontSize: 13 }}>Text preview — Version {v.version_no}</summary>
                  <pre className="p-text">{v.pages.map((p) => `--- Page ${p.number} ---\n${p.text}`).join("\n\n")}</pre>
                </details>
              ))}
              {editor && (
                <>
                  <h4>Upload Version</h4>
                  <form className="p-inline" onSubmit={onUpload}>
                    <input type="file" accept=".pdf,.txt,.md" required aria-label="Version file" />
                    <button className="p-btn primary" type="submit">Upload</button>
                  </form>
                </>
              )}
            </div>

            {versionNo && (
              <>
                <div className="p-card">
                  <h3>Process Version {versionNo}</h3>
                  <Hint>The system extracts requirements from the text and matches them against the catalog. Results land in the Suggestions tab; verify each suggestion against its source quote.</Hint>
                  <div className="p-row">
                    {editor && <button className="p-btn primary" onClick={() => void onProcess()}>Extract requirements + match</button>}
                    {job ? <span>Job: <Pill t={job.status} /> (attempt {job.attempts})</span> : <span className="p-muted">Not processed yet.</span>}
                    {job && <button className="p-btn sm" onClick={async () => { try { const j = await api.job(job.job_id); setJob(j); if (j.status === "done" && inquiryId) await loadDetail(inquiryId); } catch (e) { notify((e as Error).message); } }}>Refresh status</button>}
                  </div>
                </div>
                <div className="p-card">
                  <div className="p-subtabs" role="tablist" aria-label="Version views">
                    {([["suggestions", "Suggestions"], ["gaps", "Gaps"], ["alternatives", "Alternatives"], ["diff", "Diff"], ["quotes", "Quotes"]] as [Sub, string][]).map(([k, l]) => (
                      <button key={k} role="tab" aria-selected={sub === k} className={`p-subtab${sub === k ? " on" : ""}`} onClick={() => { setSub(k); if (k === "quotes") void api.products().then((r) => setProducts(r.products)).catch(() => {}); }}>{l}</button>
                    ))}
                  </div>
                  {sub === "suggestions" && <SubSuggestions data={suggestions} editor={editor} sourceView={sourceView} setSourceView={setSourceView} highlighted={highlighted} notify={notify} reload={async () => { if (inquiryId && versionNo) setSuggestions(await api.suggestions(inquiryId, versionNo)); }} />}
                  {sub === "gaps" && <SubGaps gaps={gaps} editor={editor} notify={notify} reload={async () => { if (inquiryId && versionNo) setGaps((await api.gaps(inquiryId, versionNo)).gaps); }} />}
                  {sub === "alternatives" && <SubAlternatives items={alternatives} />}
                  {sub === "diff" && <SubDiff versions={versions} diff={diff} diffFrom={diffFrom} diffTo={diffTo} setDiffFrom={setDiffFrom} setDiffTo={setDiffTo} onCompare={async () => { if (!inquiryId) return; try { const d = await api.diff(inquiryId, diffFrom, diffTo); setDiff({ from: d.from_version, to: d.to_version, changes: d.changes }); } catch (e) { notify((e as Error).message); } }} />}
                  {sub === "quotes" && <SubQuotes suggestions={suggestions} products={products} quotes={quotes} quoteId={quoteId} quoteDetail={quoteDetail} editor={editor} notify={notify}
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

function SubSuggestions({ data, editor, sourceView, setSourceView, highlighted, notify, reload }: {
  data: { requirements: Requirement[]; suggestions: Suggestion[] } | null;
  editor: boolean; sourceView: string | null; setSourceView: (v: string | null) => void;
  highlighted: (p: number, q: string) => React.ReactNode; notify: (m: string, k?: "ok" | "err") => void; reload: () => Promise<void>;
}) {
  const desc = <Hint>The score is between 0 and 1: 0.85 and above is usually an exact match, below that needs careful review. A “pending” badge means the team has not decided yet.</Hint>;
  if (!data || !data.requirements.length) return <>{desc}<p className="p-muted">No requirements. Process the version first.</p></>;
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
              <br /><span className="p-muted">Source: page {r.source.page} — “{r.source.quote}”</span>{" "}
              <button className="p-btn sm" onClick={() => setSourceView(sourceView === r.id ? null : r.id)}>Show source</button>
              {sourceView === r.id && <pre className="p-srcview">{highlighted(r.source.page, r.source.quote)}</pre>}
              {sugs.length === 0 ? <p className="p-muted">No suggestions.</p> : (
                <table><thead><tr><th>Product</th><th>Score</th><th /><th>Rationale</th></tr></thead><tbody>
                  {sugs.map((s) => (
                    <tr key={s.id}>
                      <td><b>{s.product.code}</b><br /><span className="p-muted">{s.product.names.join(", ")}</span></td>
                      <td>{s.score.toFixed(2)}</td>
                      <td><div className="p-scorebar"><div style={{ width: `${Math.round(s.score * 100)}%` }} /></div></td>
                      <td>{s.reasons.map((x, i) => <span key={i}>{x}<br /></span>)}<Pill t={s.status} />
                        {editor && s.id && <> <button className="p-btn sm" onClick={async () => { try { await api.decideSuggestion(s.id, "approved"); await reload(); } catch (e) { notify((e as Error).message); } }}>Accept</button> <button className="p-btn sm" onClick={async () => { try { await api.decideSuggestion(s.id, "rejected"); await reload(); } catch (e) { notify((e as Error).message); } }}>Reject</button></>}
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

function SubGaps({ gaps, editor, notify, reload }: { gaps: Gap[]; editor: boolean; notify: (m: string, k?: "ok" | "err") => void; reload: () => Promise<void> }) {
  const [answerFor, setAnswerFor] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const desc = <Hint>These are questions to ask the customer. “Mandatory” ones must be completed before the quote; “info” ones improve quality.</Hint>;
  if (!gaps.length) return <>{desc}<p className="p-muted">No gaps — a quote can be built.</p></>;
  return (
    <>
      {desc}
      <div className="p-row" style={{ marginBottom: 10 }}>
        <button className="p-btn sm" onClick={async () => {
          const lines = ["Hello, to prepare your quote we would like the following information:", ...gaps.map((g) => `- ${g.question}`)];
          try { await navigator.clipboard.writeText(lines.join("\n")); notify("Question list copied to clipboard.", "ok"); } catch (e) { notify(`Copy failed: ${(e as Error).message}`); }
        }}>Copy question list</button>
      </div>
      <table><thead><tr><th>Field</th><th>Question</th><th>Severity</th><th>Status</th><th /></tr></thead><tbody>
        {gaps.map((g) => (
          <tr key={g.id}>
            <td>{g.field}</td><td>{g.question}</td><td><Pill t={g.severity} /></td>
            <td><Pill t={g.status} />{g.answer ? <><br />{g.answer}</> : null}</td>
            <td>{editor && g.status === "open" && (answerFor === g.id
              ? <span className="p-row"><input value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Answer / note" aria-label="Gap answer" /><button className="p-btn sm primary" onClick={async () => { try { await api.answerGap(g.id, answer); setAnswerFor(null); setAnswer(""); await reload(); } catch (e) { notify((e as Error).message); } }}>Save</button></span>
              : <button className="p-btn sm" onClick={() => { setAnswerFor(g.id); setAnswer(""); }}>Answer</button>)}</td>
          </tr>
        ))}
      </tbody></table>
    </>
  );
}

function SubAlternatives({ items }: { items: Alternative[] }) {
  const desc = <Hint>When there is no exact product, the closest candidates are compared by criterion. The “Match” column shows which condition holds; whether to suggest it is your decision.</Hint>;
  if (!items.length) return <>{desc}<p className="p-muted">No alternatives (there is an exact match, or the version was not processed).</p></>;
  return (
    <>
      {desc}
      <div className="p-stack">
        {items.map((a) => (
          <div key={a.id} className="p-card" style={{ marginBottom: 0 }}>
            <b>{a.product.code}</b> <span className="p-muted">{a.product.names.join(", ")} · score {a.score.toFixed(2)}</span> <Pill t={a.status} />
            <table><thead><tr><th>Criterion</th><th>Wanted</th><th>Offered</th><th>Match</th></tr></thead><tbody>
              {a.comparison.map((r, i) => <tr key={i}><td>{r.criterion}</td><td>{r.wanted}</td><td>{r.offered}</td><td>{r.match ? "Yes" : "—"}</td></tr>)}
            </tbody></table>
            <span className="p-muted">{a.reasons.map((x, i) => <span key={i}>{x}<br /></span>)}</span>
          </div>
        ))}
      </div>
    </>
  );
}

function SubDiff({ versions, diff, diffFrom, diffTo, setDiffFrom, setDiffTo, onCompare }: {
  versions: Version[]; diff: { from: number; to: number; changes: DiffChange[] } | null;
  diffFrom: number; diffTo: number; setDiffFrom: (n: number) => void; setDiffTo: (n: number) => void; onCompare: () => Promise<void>;
}) {
  return (
    <>
      <Hint>Items whose quantity, unit or features changed between two versions; items added and removed.</Hint>
      <form className="p-inline" onSubmit={(e) => { e.preventDefault(); void onCompare(); }}>
        <select aria-label="Diff start version" value={diffFrom} onChange={(e) => setDiffFrom(Number(e.target.value))}>{versions.map((v) => <option key={v.id} value={v.version_no}>Version {v.version_no}</option>)}</select>
        <select aria-label="Diff end version" value={diffTo} onChange={(e) => setDiffTo(Number(e.target.value))}>{versions.map((v) => <option key={v.id} value={v.version_no}>Version {v.version_no}</option>)}</select>
        <button className="p-btn primary" type="submit">Compare</button>
      </form>
      {!diff && <p className="p-muted" style={{ marginTop: 10 }}>Select two versions and compare.</p>}
      {diff && diff.changes.length === 0 && <p className="p-muted" style={{ marginTop: 10 }}>No differences.</p>}
      {diff && diff.changes.length > 0 && (
        <table style={{ marginTop: 10 }}><thead><tr><th>Type</th><th>Product</th><th>Field</th><th>Old</th><th>New</th></tr></thead><tbody>
          {diff.changes.map((c, i) => <tr key={i}><td><Pill t={c.type} /></td><td>{c.product_type}</td><td>{c.field}</td><td>{c.old}</td><td>{c.new}</td></tr>)}
        </tbody></table>
      )}
    </>
  );
}

function SubQuotes({ suggestions, products, quotes, quoteId, quoteDetail, editor, notify, setQuoteDoc, reloadQuotes, selectQuote, setQuoteDetail, setQuoteId, inquiryId, versionNo }: {
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
    if (!lines.length) { notify("Select a product for at least one line."); return; }
    try {
      if (edit && quoteId) { setQuoteDetail(await api.updateQuoteLines(quoteId, lines)); }
      else if (inquiryId && versionNo) { const q = await api.createQuote(inquiryId, versionNo, lines); setQuoteId(q.id); setQuoteDetail(q); }
      await reloadQuotes(); notify("Quote saved.", "ok");
    } catch (e) { notify(`Quote error: ${(e as Error).message}`); }
  }
  return (
    <>
      <Hint>Products are pre-selected from the best suggestion; if you leave the quantity blank, the quantity in the requirement is used. The price is locked from the version active when the quote is created.</Hint>
      <h4>Quotes</h4>
      {quotes.length === 0 ? <p className="p-muted">No quotes for this inquiry.</p> : (
        <div className="p-list">
          {quotes.map((q) => (
            <button key={q.id} className={`p-listitem${q.id === quoteId ? " on" : ""}`} onClick={() => void selectQuote(q.id)}>
              <span><b>Version {q.version_no} quote</b> <Pill t={q.status} /></span>
              <span className="p-muted">{q.created_by}{q.approved_by ? ` · approved by: ${q.approved_by}` : ""}</span>
            </button>
          ))}
        </div>
      )}
      {editor && reqs.length > 0 && (
        <>
          <h4>Lines</h4>
          <table><thead><tr><th>Requirement</th><th>Product</th><th>Quantity</th></tr></thead><tbody>
            {reqs.map((r) => {
              const top = sugs.find((s) => s.requirement_id === r.id);
              return (
                <tr key={r.id} data-req={r.id}>
                  <td><b>{r.product_type}</b><br /><span className="p-muted">{r.quantity ?? "?"} {r.unit ?? ""}</span></td>
                  <td><select className="q-prod" aria-label={`Product — ${r.product_type}`} defaultValue={products.find((p) => top && p.code === top.product.code)?.id ?? ""}>
                    <option value="">— select —</option>
                    {products.map((p) => <option key={p.id} value={p.id}>{p.code} — {p.names.join(", ")}</option>)}
                  </select></td>
                  <td><input className="q-qty" type="number" min="0" step="any" placeholder={r.quantity != null ? String(r.quantity) : ""} style={{ width: 110 }} aria-label={`Quantity — ${r.product_type}`} /></td>
                </tr>
              );
            })}
          </tbody></table>
          <div className="p-row" style={{ marginTop: 10 }}>
            <button className="p-btn primary" onClick={() => void build(false)}>Create new quote</button>
            {quoteDetail?.status === "draft" && <button className="p-btn" onClick={() => void build(true)}>Update selected draft</button>}
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
  const admin = editor; // submit is for editors; approve/return role checks are in the API
  async function act(action: "submit" | "return" | "approve") {
    if (action === "approve" && !window.confirm("The quote will be approved and ready to export. Are you sure?")) return;
    try { setQuoteDetail(await api.quoteAction(q.id, action)); await reloadQuotes(); notify("Quote updated.", "ok"); }
    catch (e) { notify((e as Error).message); }
  }
  async function onExport() {
    if (!window.confirm("The approved quote will be exported and a document will be generated. Are you sure?")) return;
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
      <h4>Quote Detail <Pill t={q.status} /></h4>
      <table><thead><tr><th>Product</th><th>Quantity</th><th>Unit price</th><th>Amount</th></tr></thead><tbody>
        {q.lines.map((l) => <tr key={l.id}><td><b>{l.product.code}</b><br /><span className="p-muted">{l.product.names.join(", ")}</span></td><td>{l.quantity} {l.unit}</td><td>{money(l.unit_price, l.currency)}</td><td>{money(l.amount, l.currency)}</td></tr>)}
        {q.totals.map((t) => <tr key={t.currency} className="p-total-row"><td colSpan={3}>Total</td><td>{money(t.amount, t.currency)}</td></tr>)}
      </tbody></table>
      <p className="p-muted">Prepared by: {q.created_by}{q.approved_by ? ` · Approved by: ${q.approved_by}` : ""}<br />Line prices are locked from the price version active when the quote was created.</p>
      <div className="p-row">
        {editor && q.status === "draft" && <button className="p-btn primary" onClick={() => void act("submit")}>Submit for review</button>}
        {q.status === "in_review" && <><button className="p-btn primary" onClick={() => void act("approve")}>Approve</button><button className="p-btn" onClick={() => void act("return")}>Return</button></>}
        <button className="p-btn" onClick={() => void onPreview()}>Preview</button>
        {(q.status === "approved" || q.status === "exported") && <button className="p-btn primary" onClick={() => void onExport()}>Export</button>}
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
      if (!res.ok) throw new Error(`Could not fetch the PDF (${res.status})`);
      const blob = await res.blob();
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "quote.pdf"; a.click(); URL.revokeObjectURL(a.href);
    } catch (e) { notify((e as Error).message); }
  }
  return (
    <div className="p-modal-veil" onClick={(e) => { if (e.target === e.currentTarget) close(); }}>
      <div className="p-modal" role="dialog" aria-modal="true" aria-label="Quote document">
        <div className="p-quote-head"><h2>Quote {doc.preview ? "(Preview)" : ""}</h2><button className="p-btn sm" onClick={close}>Close</button></div>
        <p><b>Customer:</b> {String(doc.customer ?? "")} &nbsp; <b>Version:</b> {String(doc.version_no ?? "")} &nbsp; <Pill t={String(doc.status ?? "")} /></p>
        <table><thead><tr><th>Product</th><th>Quantity</th><th>Unit price</th><th>Amount</th></tr></thead><tbody>
          {lines.map((l, i) => <tr key={i}><td><b>{l.product_code}</b><br /><span className="p-muted">{(l.product_names ?? []).join(", ")}</span></td><td>{l.quantity} {l.unit}</td><td>{money(l.unit_price, l.currency)}</td><td>{money(l.amount, l.currency)}</td></tr>)}
          {totals.map((t) => <tr key={t.currency} className="p-total-row"><td colSpan={3}>Total</td><td>{money(t.amount, t.currency)}</td></tr>)}
        </tbody></table>
        {terms && <><h4>{terms.name}</h4><div className="p-termsbox">{terms.text}</div></>}
        <p className="p-muted">Prepared by: {String(doc.prepared_by ?? "")}{doc.approved_by ? ` · Approved by: ${String(doc.approved_by)}` : ""}</p>
        {!doc.preview && <div className="p-row"><button className="p-btn primary" onClick={() => void downloadPdf()}>Download PDF</button></div>}
        <span className="p-muted">{dt(Date.now() / 1000)}</span>
      </div>
    </div>
  );
}
