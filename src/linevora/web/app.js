"use strict";
/* Linevora paneli: yalın SaaS arayüzü, çerçevesiz. */

const S = {
  token: null, user: null, tab: "talepler",
  inquiries: [], inquiryId: null,
  versions: [], versionNo: null, sub: "oneriler",
  suggestions: null, gaps: null, alternatives: null,
  diff: null, diffFrom: null, diffTo: null,
  quotes: [], quoteId: null, quoteDetail: null, quoteDoc: null, filter: "",
  products: [], prices: {}, terms: [],
  audit: [], metrics: null, job: null, sourceView: null,
};

function esc(s) {
  return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function money(n, cur) {
  return Number(n).toLocaleString("tr-TR") + (cur ? " " + esc(cur) : "");
}
function dt(ts) {
  return new Date(ts * 1000).toLocaleString("tr-TR");
}
function banner(msg, kind) {
  const b = document.getElementById("banner");
  if (!msg) { b.hidden = true; b.textContent = ""; b.className = "banner"; return; }
  b.hidden = false; b.textContent = msg;
  b.className = "banner" + (kind === "ok" ? " banner-ok" : "");
}

async function api(path, opts) {
  opts = opts || {};
  const headers = Object.assign({}, opts.headers || {});
  if (S.token) headers["Authorization"] = "Bearer " + S.token;
  let body = opts.body;
  if (body !== undefined && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  const res = await fetch("/v1" + path, { method: opts.method || "GET", headers, body });
  let data = null;
  try { data = await res.json(); } catch (e) { data = null; }
  if (!res.ok) {
    const detail = data && data.detail !== undefined ? data.detail : res.status;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

const isAdmin = () => !!(S.user && S.user.roles.includes("admin"));
const isEditor = () => !!(S.user && (S.user.roles.includes("admin") || S.user.roles.includes("specialist")));

const PILL = {
  "taslak": "p-gray", "açık": "p-blue", "bekliyor": "p-amber", "incelemede": "p-amber",
  "onaylandı": "p-green", "dışa aktarıldı": "p-teal", "yürürlükte": "p-green",
  "arşiv": "p-gray", "zorunlu": "p-red", "bilgi": "p-gray",
  "queued": "p-gray", "running": "p-blue", "done": "p-green", "failed": "p-red",
};
function pill(t) {
  return `<span class="pill ${PILL[t] || "p-gray"}">${esc(t)}</span>`;
}

function hint(html) {
  return `<div class="hint">${html}</div>`;
}

function vSteps() {
  const done = [
    !!S.inquiryId,
    S.versions.length > 0,
    (S.job && S.job.status === "done") || !!(S.suggestions && S.suggestions.requirements && S.suggestions.requirements.length),
    S.quotes.length > 0,
    S.quotes.some((q) => q.status === "dışa aktarıldı"),
  ];
  const labels = ["Talep", "Dosya", "İşleme", "Teklif", "Onay ve gönderi"];
  const firstOpen = done.findIndex((d) => !d);
  return `<div class="steps">` + labels.map((l, i) =>
    `<span class="step ${done[i] ? "done" : i === firstOpen ? "active" : ""}">${i + 1}. ${l}</span>`).join(`<span class="steparr">→</span>`) + `</div>`;
}

/* ---------- yükleyiciler ---------- */

async function loadInquiries() {
  S.inquiries = (await api("/inquiries")).inquiries;
  if (S.inquiryId && !S.inquiries.find((i) => i.id === S.inquiryId)) S.inquiryId = null;
}
async function loadDetail() {
  S.versions = (await api(`/inquiries/${S.inquiryId}/versions`)).versions;
  if (!S.versions.find((v) => v.version_no === S.versionNo)) {
    S.versionNo = S.versions.length ? S.versions[S.versions.length - 1].version_no : null;
  }
  S.diffFrom = S.versions.length ? S.versions[0].version_no : null;
  S.diffTo = S.versionNo;
  S.quotes = (await api(`/inquiries/${S.inquiryId}/quotes`)).quotes;
  if (S.versionNo) await loadSub();
}
async function loadSub() {
  if (!S.versionNo) return;
  const base = `/inquiries/${S.inquiryId}/versions/${S.versionNo}`;
  if (S.sub === "oneriler" || S.sub === "teklifler") S.suggestions = await api(base + "/suggestions");
  if (S.sub === "eksikler") S.gaps = await api(base + "/gaps");
  if (S.sub === "alternatifler") S.alternatives = await api(base + "/alternatives");
}
async function loadCatalog() {
  S.products = (await api("/products")).products;
}
async function loadTerms() {
  S.terms = (await api("/terms")).terms;
}
async function loadAudit() {
  S.audit = (await api("/audit")).entries;
}
async function loadMetrics() {
  S.metrics = await api("/metrics");
}

/* ---------- giriş ---------- */

async function doLogin(ev) {
  ev.preventDefault(); banner(null);
  const u = document.getElementById("li-user").value.trim();
  const p = document.getElementById("li-pass").value;
  try {
    const t = await api("/auth/token", { method: "POST", body: { username: u, password: p } });
    S.token = t.access_token;
    try { localStorage.setItem("linevora_token", S.token); } catch (e) {}
    S.user = await api("/me");
    await loadInquiries();
  } catch (e) { banner("Giriş başarısız: " + e.message); }
  render();
}
async function doLogout() {
  try { if (S.token) await api("/auth/revoke", { method: "POST" }); } catch (e) {}
  try { localStorage.removeItem("linevora_token"); } catch (e) {}
  S.token = null; S.user = null; S.inquiryId = null; S.quoteDoc = null;
  banner(null); render();
}
function vLogin() {
  return `<div class="card login-card"><h2>Giriş</h2>
    <p class="muted">Dağınık talepleri (PDF, e-posta) kaynağı gösterilebilir tekliflere dönüştürür: yükle → işlet → önerileri kontrol et → teklif kur → onayla.</p>
    <form class="stack" onsubmit="doLogin(event)">
      <input id="li-user" placeholder="Kullanıcı adı" autocomplete="username" required>
      <input id="li-pass" type="password" placeholder="Parola" autocomplete="current-password" required>
      <button class="btn btn-primary" type="submit">Giriş yap</button>
    </form></div>`;
}

/* ---------- iskelet ---------- */

async function goTab(k) {
  S.tab = k; S.quoteDoc = null; banner(null);
  try {
    if (k === "talepler") await loadInquiries();
    if (k === "katalog") await loadCatalog();
    if (k === "fiyat") { await loadCatalog(); await loadTerms(); await loadAllPrices(); }
    if (k === "denetim") await loadAudit();
    if (k === "olcu") await loadMetrics();
  } catch (e) { banner("Yükleme hatası: " + e.message); }
  render();
}
async function loadAllPrices() {
  S.prices = {};
  for (const p of S.products) {
    S.prices[p.id] = (await api(`/prices?product_id=${p.id}`)).prices;
  }
}

function render() {
  const v = document.getElementById("view");
  const ub = document.getElementById("userbox");
  if (!S.token) {
    ub.innerHTML = "";
    v.innerHTML = vLogin();
    return;
  }
  const roleHint = S.user.roles.includes("admin") ? "Fiyat, ürün ve onay yetkisi sizde"
    : S.user.roles.includes("specialist") ? "Talep ve teklif hazırlarsınız" : "Salt okunur görüntüleme";
  ub.innerHTML = `${esc(S.user.username)} · ${esc(S.user.roles.join(", "))} <span class="role-hint">${roleHint}</span> <button class="btn btn-light" onclick="doLogout()">Çıkış</button>`;
  const allTabs = [["talepler", "Talepler"], ["katalog", "Katalog"], ["fiyat", "Fiyat & Şartlar"], ["denetim", "Denetim"], ["olcu", "Ölçümler"]];
  const tabs = allTabs.filter(([k]) => k !== "denetim" && k !== "olcu" || isAdmin());
  if (!tabs.find(([k]) => k === S.tab)) S.tab = "talepler";
  let h = `<nav class="tabs">` + tabs.map(([k, l]) =>
    `<button class="tab${S.tab === k ? " active" : ""}" onclick="goTab('${k}')">${l}</button>`).join("") + `</nav>`;
  if (S.tab === "talepler") h += vTalepler();
  else if (S.tab === "katalog") h += vKatalog();
  else if (S.tab === "fiyat") h += vFiyat();
  else if (S.tab === "denetim") h += vDenetim();
  else h += vOlcu();
  if (S.quoteDoc) h += vQuoteModal();
  v.innerHTML = h;
}

/* ---------- talepler ---------- */

function setFilter(v) { S.filter = v; render(); }
function vTalepler() {
  const q = (S.filter || "").toLocaleLowerCase("tr");
  const items = S.inquiries.filter((x) => !q || (x.title + " " + x.customer).toLocaleLowerCase("tr").includes(q)).map((q) =>
    `<button class="listitem${q.id === S.inquiryId ? " active" : ""}" onclick="selectInquiry('${q.id}')">` +
    `<b>${esc(q.title)}</b><span class="muted">${esc(q.customer)} · ${esc(q.status)}</span></button>`).join("");
  let left = `<div class="card"><h3>Talepler</h3><label class="muted">Ara <input aria-label="Talep ara" placeholder="müşteri / başlık" value="${esc(S.filter || "")}" onchange="setFilter(this.value)"></label><div class="list">${items || '<p class="muted">Kayıt yok.</p>'}</div>`;
  if (isEditor()) {
    left += `<h4>Yeni Talep</h4><form class="stack" onsubmit="newInquiry(event)">` +
      `<input id="ni-customer" placeholder="Müşteri" required><input id="ni-title" placeholder="Başlık" required>` +
      `<button class="btn btn-primary" type="submit">Aç</button></form>`;
  }
  left += `</div>`;
  const right = S.inquiryId ? vInquiryDetail() : `<div class="card"><p class="muted">Soldan bir talep seçin.</p></div>`;
  return `<div class="grid2"><div>${left}</div><div>${right}</div></div>`;
}

async function newInquiry(ev) {
  ev.preventDefault(); banner(null);
  try {
    const q = await api("/inquiries", { method: "POST", body: {
      customer: document.getElementById("ni-customer").value.trim(),
      title: document.getElementById("ni-title").value.trim() } });
    S.inquiryId = q.id; S.versionNo = null; S.sub = "oneriler"; S.job = null; S.quoteId = null;
    await loadInquiries(); await loadDetail();
  } catch (e) { banner(e.message); }
  render();
}
async function selectInquiry(id) {
  try { history.replaceState(null, "", "#talep/" + id); } catch (e) {}
  S.inquiryId = id; S.versionNo = null; S.sub = "oneriler"; S.job = null; S.quoteId = null; S.diff = null;
  banner(null);
  try { await loadDetail(); } catch (e) { banner(e.message); }
  render();
}
async function selectVersion(no) {
  S.versionNo = Number(no); S.job = null; S.diff = null; banner(null);
  try { await loadSub(); } catch (e) { banner(e.message); }
  render();
}
async function goSub(k) {
  S.sub = k; banner(null);
  try {
    if (k === "teklifler") await loadCatalog();
    await loadSub();
  } catch (e) { banner(e.message); }
  render();
}

function vInquiryDetail() {
  const q = S.inquiries.find((i) => i.id === S.inquiryId) || {};
  let h = `<div class="card"><h3>${esc(q.title || "")}</h3>` +
    `<p class="muted">${esc(q.customer || "")} · ${pill(q.status || "")}</p>`;
  h += vSteps();
  h += `<h4>Sürümler</h4>`;
  h += hint("Her yükleme yeni sürümdür; eskiler silinmez. Müşteri düzeltme gönderirse yeni dosya olarak yükleyin — Fark sekmesi değişenleri gösterir.");
  if (S.versions.length) {
    h += `<table><tr><th>No</th><th>Dosya</th><th>Sayfa</th><th></th></tr>` + S.versions.map((v) =>
      `<tr><td>${v.version_no}</td><td>${esc(v.filename)}</td><td>${v.pages.length}</td>` +
      `<td>${v.version_no === S.versionNo ? "<b>seçili</b>" : `<button class="btn" onclick="selectVersion(${v.version_no})">Seç</button>`}</td></tr>` +
      `<tr><td></td><td colspan="3"><details><summary>Metin önizleme</summary><pre class="text">${esc(v.pages.map((p) => `--- Sayfa ${p.number} ---\n${p.text}`).join("\n\n"))}</pre></details></td></tr>`
    ).join("") + `</table>`;
  } else {
    h += `<p class="muted">Henüz sürüm yok; aşağıdan dosya yükleyin.</p>`;
  }
  if (isEditor()) {
    h += `<h4>Sürüm Yükle</h4><form class="inline" onsubmit="uploadVersion(event)">` +
      `<input id="up-file" type="file" accept=".pdf,.txt,.md" required><button class="btn btn-primary" type="submit">Yükle</button></form>`;
  }
  h += `</div>`;
  if (S.versionNo) {
    h += `<div class="card"><h3>Sürüm ${S.versionNo} İşleme</h3>` + hint("Sistem metinden gereksinimleri çıkarır ve katalogla eşleştirir. Sonuç Öneriler sekmesine düşer; her öneriyi kaynak alıntısıyla doğrulayın.") + `<div class="row">`;
    if (isEditor()) h += `<button class="btn btn-primary" onclick="processVersion()">Gereksinim çıkar + eşleştir</button>`;
    if (S.job) h += `<span>İş: ${pill(S.job.status)} (deneme ${S.job.attempts})</span><button class="btn" onclick="refreshJob()">Durumu yenile</button>`;
    else h += `<span class="muted">Henüz işletilmedi.</span>`;
    h += `</div></div>`;
    const subs = [["oneriler", "Öneriler"], ["eksikler", "Eksikler"], ["alternatifler", "Alternatifler"], ["fark", "Fark"], ["teklifler", "Teklifler"]];
    h += `<div class="card"><div class="subtabs">` + subs.map(([k, l]) =>
      `<button class="subtab${S.sub === k ? " active" : ""}" onclick="goSub('${k}')">${l}</button>`).join("") + `</div>`;
    if (S.sub === "oneriler") h += vSubOneriler();
    else if (S.sub === "eksikler") h += vSubEksikler();
    else if (S.sub === "alternatifler") h += vSubAlternatifler();
    else if (S.sub === "fark") h += vSubFark();
    else h += vSubTeklifler();
    h += `</div>`;
  }
  return h;
}

async function uploadVersion(ev) {
  ev.preventDefault(); banner(null);
  const f = document.getElementById("up-file").files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append("file", f);
  try {
    const v = await api(`/inquiries/${S.inquiryId}/versions`, { method: "POST", body: fd });
    S.versionNo = v.version_no; S.job = null;
    await loadDetail();
  } catch (e) { banner("Yükleme hatası: " + e.message); }
  render();
}
async function processVersion() {
  banner(null);
  S.job = { status: "running", attempts: 0, job_id: null };
  render();
  try {
    const p = await api(`/inquiries/${S.inquiryId}/versions/${S.versionNo}/process`, { method: "POST" });
    let job = null;
    for (let i = 0; i < 40; i++) {
      job = await api(`/jobs/${p.job_id}`);
      if (job.status === "done" || job.status === "failed") break;
      await new Promise((r) => setTimeout(r, 500));
    }
    S.job = job;
    if (job.status === "done") await loadDetail();
    else banner("İş başarısız: " + (job.error || ""));
  } catch (e) { banner("İşleme hatası: " + e.message); }
  render();
}
async function refreshJob() {
  if (!S.job || !S.job.job_id) return;
  try {
    S.job = await api(`/jobs/${S.job.job_id}`);
    if (S.job.status === "done") await loadDetail();
  } catch (e) { banner(e.message); }
  render();
}

function vSubOneriler() {
  const d = S.suggestions;
  const desc = hint("Skor 0-1 arasındadır: 0.85 ve üzeri genelde birebir eşleşme, altı dikkatli inceleme ister. “bekliyor” rozeti, ekibin henüz karar vermediği anlamına gelir.");
  if (!d || !d.requirements.length) return desc + `<p class="muted">Gereksinim yok. Önce sürümü işletin.</p>`;
  return desc + d.requirements.map((r) => {
    const sugs = d.suggestions.filter((s) => s.requirement_id === r.id);
    const feat = Object.entries(r.features || {}).map(([k, v]) => `${esc(k)}=${esc(v)}`).join(", ");
    let h = `<div class="card"><b>${esc(r.product_type)}</b> <span class="muted">${esc(r.quantity === null || r.quantity === undefined ? "?" : r.quantity)} ${esc(r.unit || "")}${feat ? " · " + feat : ""}</span>` +
      `<br><span class="muted">Kaynak: sayfa ${r.source.page} — “${esc(r.source.quote)}”</span> <button class="btn" onclick="showSource('${r.id}')">Kaynağı göster</button>` +
      (S.sourceView === r.id ? `<pre class="srcview">${highlighted(r.source.page, r.source.quote)}</pre>` : "");
    if (!sugs.length) h += `<p class="muted">Öneri yok.</p>`;
    else h += `<table><tr><th>Ürün</th><th>Skor</th><th></th><th>Gerekçe</th></tr>` + sugs.map((s) =>
      `<tr><td><b>${esc(s.product.code)}</b><br><span class="muted">${esc(s.product.names.join(", "))}</span></td>` +
      `<td>${s.score.toFixed(2)}</td>` +
      `<td><div class="scorebar"><div style="width:${Math.round(s.score * 100)}%"></div></div></td>` +
      `<td>${s.reasons.map(esc).join("<br>")}<br>${pill(s.status)}${isEditor() && s.id ? ` <button class="btn" onclick="decideSuggestion('${s.id}','onaylandı')">Kabul</button> <button class="btn" onclick="decideSuggestion('${s.id}','reddedildi')">Reddet</button>` : ""}</td></tr>`).join("") + `</table>`;
    return h + `</div>`;
  }).join("");
}

function showSource(reqId) {
  S.sourceView = S.sourceView === reqId ? null : reqId;
  render();
}
function highlighted(pageNo, quote) {
  const v = S.versions.find((x) => x.version_no === S.versionNo);
  const pg = v && v.pages.find((x) => x.number === pageNo);
  if (!pg) return "Sayfa metni bulunamadı.";
  const text = esc(pg.text); const q = esc(quote);
  const i = text.toLocaleLowerCase("tr").indexOf(q.toLocaleLowerCase("tr"));
  if (i < 0) return text;
  return text.slice(0, i) + "<mark>" + text.slice(i, i + q.length) + "</mark>" + text.slice(i + q.length);
}
function vSubEksikler() {
  const d = S.gaps;
  const desc = hint("Bunlar müşteriye sorulacak sorulardır. “zorunlu” olanlar teklife girmeden tamamlanmalı; “bilgi” olanlar kaliteyi artırır.");
  if (!d || !d.gaps.length) return desc + `<p class="muted">Eksik yok — teklif kurulabilir.</p>`;
  return desc + `<div class="row" style="margin-bottom:10px"><button class="btn" onclick="copyGaps()">Soru listesini kopyala</button></div>` + `<table><tr><th>Alan</th><th>Soru</th><th>Önem</th><th>Durum</th><th></th></tr>` + d.gaps.map((g) =>
    `<tr><td>${esc(g.field)}</td><td>${esc(g.question)}</td><td>${pill(g.severity)}</td><td>${pill(g.status)}${g.answer ? "<br>" + esc(g.answer) : ""}</td><td>${isEditor() && g.status === "açık" ? `<button class="btn" onclick="answerGap('${g.id}')">Yanıtla</button>` : ""}</td></tr>`).join("") + `</table>`;
}

function vSubAlternatifler() {
  const d = S.alternatives;
  const desc = hint("Birebir ürün yoksa en yakın adaylar ölçüte göre karşılaştırılır. “Uyum” sütunu hangi şartın tuttuğunu gösterir; önerebilir misiniz kararı sizde.");
  if (!d || !d.alternatives.length) return desc + `<p class="muted">Alternatif yok (birebir eşleşme var ya da sürüm işletilmedi).</p>`;
  return desc + d.alternatives.map((a) =>
    `<div class="card"><b>${esc(a.product.code)}</b> <span class="muted">${esc(a.product.names.join(", "))} · skor ${a.score.toFixed(2)}</span> ${pill(a.status)}` +
    `<table><tr><th>Ölçüt</th><th>İstenen</th><th>Sunulan</th><th>Uyum</th></tr>` + a.comparison.map((r) =>
      `<tr><td>${esc(r.criterion)}</td><td>${esc(r.wanted)}</td><td>${esc(r.offered)}</td><td>${r.match ? "Evet" : "—"}</td></tr>`).join("") + `</table>` +
    `<span class="muted">${a.reasons.map(esc).join("<br>")}</span></div>`).join("");
}

function vSubFark() {
  const opts = S.versions.map((v) => v.version_no);
  const from = S.diffFrom !== null && S.diffFrom !== undefined ? S.diffFrom : opts[0];
  const to = S.diffTo !== null && S.diffTo !== undefined ? S.diffTo : opts[opts.length - 1];
  const sel = (id, val) => `<select id="${id}">` + opts.map((n) =>
    `<option value="${n}"${n === val ? " selected" : ""}>Sürüm ${n}</option>`).join("") + `</select>`;
  let h = hint("İki sürüm arasında miktarı, birimi veya özellikleri değişen; eklenen ve çıkarılan kalemler.") + `<form class="inline" onsubmit="loadDiff(event)">${sel("diff-a", from)}${sel("diff-b", to)}` +
    `<button class="btn btn-primary" type="submit">Karşılaştır</button></form>`;
  if (!S.diff) return h + `<p class="muted">İki sürüm seçip karşılaştırın.</p>`;
  if (!S.diff.changes.length) return h + `<p class="muted">Fark yok.</p>`;
  h += `<table><tr><th>Tür</th><th>Ürün</th><th>Alan</th><th>Eski</th><th>Yeni</th></tr>` + S.diff.changes.map((c) =>
    `<tr><td>${pill(c.type)}</td><td>${esc(c.product_type)}</td><td>${esc(c.field)}</td><td>${esc(c.old)}</td><td>${esc(c.new)}</td></tr>`).join("") + `</table>`;
  return h;
}
async function loadDiff(ev) {
  ev.preventDefault(); banner(null);
  const a = document.getElementById("diff-a").value;
  const b = document.getElementById("diff-b").value;
  S.diffFrom = Number(a); S.diffTo = Number(b);
  try { S.diff = await api(`/inquiries/${S.inquiryId}/versions/${a}/diff/${b}`); }
  catch (e) { banner(e.message); }
  render();
}
async function decideSuggestion(id, status) {
  banner(null);
  try { await api(`/suggestions/${id}`, { method: "PATCH", body: { status } }); await loadSub(); }
  catch (e) { banner(e.message); }
  render();
}
async function answerGap(id) {
  const answer = prompt("Yanıt / not:");
  if (answer === null) return;
  banner(null);
  try { await api(`/gaps/${id}/answer`, { method: "POST", body: { status: "yanıtlandı", answer } }); await loadSub(); }
  catch (e) { banner(e.message); }
  render();
}
async function downloadPdf() {
  banner(null);
  try {
    const res = await fetch(`/v1/quotes/${S.quoteId}/export.pdf`, { headers: { Authorization: "Bearer " + S.token } });
    if (!res.ok) throw new Error("PDF alınamadı (" + res.status + ")");
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "teklif.pdf"; a.click();
    URL.revokeObjectURL(a.href);
  } catch (e) { banner(e.message); }
}
async function copyGaps() {
  const d = S.gaps;
  if (!d || !d.gaps.length) return;
  const lines = ["Merhaba, teklif hazırlamak için şu bilgileri rica ediyoruz:"]
    .concat(d.gaps.map((g) => "- " + g.question));
  try {
    await navigator.clipboard.writeText(lines.join("\n"));
    banner("Soru listesi panoya kopyalandı.", "ok");
  } catch (e) {
    banner("Kopyalama başarısız: " + e.message);
  }
}

/* ---------- teklifler ---------- */

function vSubTeklifler() {
  const reqs = (S.suggestions && S.suggestions.requirements) || [];
  const sugs = (S.suggestions && S.suggestions.suggestions) || [];
  let h = hint("Ürünler en iyi öneriye göre önceden seçilidir; miktar boş bırakılırsa gereksinimdeki miktar kullanılır. Fiyat, teklif kurulduğu anda yürürlükteki sürümden kilitlenir.") + `<h4>Teklifler</h4>`;
  h += S.quotes.length ? `<div class="list">` + S.quotes.map((q) =>
    `<button class="listitem${q.id === S.quoteId ? " active" : ""}" onclick="selectQuote('${q.id}')">` +
    `<span><b>Sürüm ${q.version_no} teklifi</b> ${pill(q.status)}</span><span class="muted">${esc(q.created_by)}${q.approved_by ? " · onay: " + esc(q.approved_by) : ""}</span></button>`).join("") + `</div>`
    : `<p class="muted">Bu talepte teklif yok.</p>`;
  if (isEditor() && reqs.length) {
    h += `<h4>Kalemler</h4><table><tr><th>Gereksinim</th><th>Ürün</th><th>Miktar</th></tr>` + reqs.map((r) => {
      const top = sugs.find((s) => s.requirement_id === r.id);
      const opts = [`<option value="">— seçin —</option>`].concat(S.products.map((p) =>
        `<option value="${p.id}"${top && top.product.code === p.code ? " selected" : ""}>${esc(p.code)} — ${esc(p.names.join(", "))}</option>`)).join("");
      return `<tr data-req="${r.id}"><td><b>${esc(r.product_type)}</b><br><span class="muted">${esc(r.quantity === null || r.quantity === undefined ? "?" : r.quantity)} ${esc(r.unit || "")}</span></td>` +
        `<td><select class="q-prod">${opts}</select></td>` +
        `<td><input class="q-qty" type="number" min="0" step="any" placeholder="${esc(r.quantity === null || r.quantity === undefined ? "" : r.quantity)}" style="width:110px"></td></tr>`;
    }).join("") + `</table><div class="row">` +
      `<button class="btn btn-primary" onclick="buildQuote(false)">Yeni teklif oluştur</button>`;
    if (S.quoteDetail && S.quoteDetail.status === "taslak") {
      h += `<button class="btn" onclick="buildQuote(true)">Seçili taslağı güncelle</button>`;
    }
    h += `</div>`;
  }
  if (S.quoteDetail) h += vQuoteDetail();
  return h;
}
async function selectQuote(id) {
  S.quoteId = id; S.quoteDetail = null; banner(null);
  try { S.quoteDetail = await api(`/quotes/${id}`); } catch (e) { banner(e.message); }
  render();
}
async function buildQuote(edit) {
  banner(null);
  const lines = [];
  document.querySelectorAll("[data-req]").forEach((row) => {
    const prod = row.querySelector(".q-prod").value;
    const qtyRaw = row.querySelector(".q-qty").value;
    if (prod) lines.push({ requirement_id: row.getAttribute("data-req"), product_id: prod, quantity: qtyRaw === "" ? null : Number(qtyRaw) });
  });
  if (!lines.length) { banner("En az bir kalem için ürün seçin."); return; }
  try {
    if (edit) S.quoteDetail = await api(`/quotes/${S.quoteId}/lines`, { method: "PUT", body: { lines } });
    else {
      S.quoteDetail = await api(`/inquiries/${S.inquiryId}/versions/${S.versionNo}/quotes`, { method: "POST", body: { lines } });
      S.quoteId = S.quoteDetail.id;
    }
    S.quotes = (await api(`/inquiries/${S.inquiryId}/quotes`)).quotes;
  } catch (e) { banner("Teklif hatası: " + e.message); }
  render();
}
function vQuoteDetail() {
  const q = S.quoteDetail;
  let h = `<h4>Teklif Detayı ${pill(q.status)}</h4><table><tr><th>Ürün</th><th>Miktar</th><th>Birim fiyat</th><th>Tutar</th></tr>` +
    q.lines.map((l) =>
      `<tr><td><b>${esc(l.product.code)}</b><br><span class="muted">${esc(l.product.names.join(", "))}</span></td>` +
      `<td>${esc(l.quantity)} ${esc(l.unit)}</td><td>${money(l.unit_price, l.currency)}</td><td>${money(l.amount, l.currency)}</td></tr>`).join("") +
    q.totals.map((t) => `<tr class="total-row"><td colspan="3">Toplam</td><td>${money(t.amount, t.currency)}</td></tr>`).join("") + `</table>`;
  h += `<p class="muted">Hazırlayan: ${esc(q.created_by)}${q.approved_by ? " · Onaylayan: " + esc(q.approved_by) : ""}<br>Kalem fiyatları, kurulduğu anda yürürlükteki fiyat sürümünden kilitlenmiştir; sonraki fiyat değişimi bu teklifi etkilemez.</p><div class="row">`;
  if (isEditor() && q.status === "taslak") h += `<button class="btn btn-primary" onclick="quoteAction('submit')">İncelemeye sun</button>`;
  if (isAdmin() && q.status === "incelemede") h += `<button class="btn btn-primary" onclick="quoteAction('approve')">Onayla</button><button class="btn" onclick="quoteAction('return')">İade et</button>`;
  h += `<button class="btn" onclick="previewQuote()">Önizleme</button>`;
  if (isEditor() && (q.status === "onaylandı" || q.status === "dışa aktarıldı")) h += `<button class="btn btn-primary" onclick="exportQuote()">Dışa aktar</button>`;
  return h + `</div>`;
}
async function quoteAction(action) {
  if (action === "approve" && !confirm("Teklif onaylanacak ve dışa aktarmaya hazır olacak. Emin misiniz?")) return;
  banner(null);
  try {
    S.quoteDetail = await api(`/quotes/${S.quoteId}/${action}`, { method: "POST" });
    S.quotes = (await api(`/inquiries/${S.inquiryId}/quotes`)).quotes;
  } catch (e) { banner(e.message); }
  render();
}
async function exportQuote() {
  if (!confirm("Onaylanmış teklif dışa aktarılacak ve belge üretilecek. Emin misiniz?")) return;
  banner(null);
  try {
    S.quoteDoc = await api(`/quotes/${S.quoteId}/export`);
    S.quoteDetail = await api(`/quotes/${S.quoteId}`);
    S.quotes = (await api(`/inquiries/${S.inquiryId}/quotes`)).quotes;
  } catch (e) { banner(e.message); }
  render();
}
async function previewQuote() {
  banner(null);
  try {
    const q = S.quoteDetail;
    if (!q) return;
    if (!S.terms.length) await loadTerms();
    const t = S.terms.find((x) => x.id === q.terms_version_id);
    S.quoteDoc = {
      preview: true, quote_id: q.id, status: q.status, customer: q.customer,
      version_no: q.version_no,
      lines: q.lines.map((l) => ({ product_code: l.product.code, product_names: l.product.names, quantity: l.quantity, unit: l.unit, unit_price: l.unit_price, currency: l.currency, amount: l.amount })),
      totals: q.totals,
      terms: t ? { name: t.name, text: t.text } : null,
      prepared_by: q.created_by, approved_by: q.approved_by,
    };
  } catch (e) { banner(e.message); }
  render();
}
function closeModal() { S.quoteDoc = null; render(); }
function vQuoteModal() {
  const d = S.quoteDoc;
  return `<div class="modal-veil" onclick="if(event.target===this)closeModal()"><div class="modal">` +
    `<div class="quote-head"><h2>Teklif ${d.preview ? "(Önizleme)" : ""}</h2><button class="btn" onclick="closeModal()">Kapat</button></div>` +
    `<p><b>Müşteri:</b> ${esc(d.customer)} &nbsp; <b>Sürüm:</b> ${esc(d.version_no)} &nbsp; ${pill(d.status)}</p>` +
    `<table><tr><th>Ürün</th><th>Miktar</th><th>Birim fiyat</th><th>Tutar</th></tr>` +
    d.lines.map((l) => `<tr><td><b>${esc(l.product_code)}</b><br><span class="muted">${esc((l.product_names || []).join(", "))}</span></td><td>${esc(l.quantity)} ${esc(l.unit)}</td><td>${money(l.unit_price, l.currency)}</td><td>${money(l.amount, l.currency)}</td></tr>`).join("") +
    d.totals.map((t) => `<tr class="total-row"><td colspan="3">Toplam</td><td>${money(t.amount, t.currency)}</td></tr>`).join("") + `</table>` +
    (d.terms ? `<h4>${esc(d.terms.name)}</h4><div class="termsbox">${esc(d.terms.text)}</div>` : "") +
    `<p class="muted">Hazırlayan: ${esc(d.prepared_by)}${d.approved_by ? " · Onaylayan: " + esc(d.approved_by) : ""}</p>` +
    (!d.preview ? `<div class="row"><button class="btn btn-primary" onclick="downloadPdf()">PDF indir</button></div>` : "") +
    `</div></div>`;
}

/* ---------- katalog ---------- */

function vKatalog() {
  let h = `<div class="card"><h3>Ürünler</h3>` + hint("Eşanlamlılar çok önemlidir: müşteri ürünü başka isimle anarsa eşleşme buradan gelir. Kodu bir kez yazarsınız; adlar virgülle ayrılır.") + `<table><tr><th>Kod</th><th>Adlar</th><th>Özellikler</th><th>Birim</th></tr>` +
    S.products.map((p) => `<tr><td><b>${esc(p.code)}</b></td><td>${esc(p.names.join(", "))}${p.synonyms.length ? `<br><span class="muted">eş: ${esc(p.synonyms.join(", "))}</span>` : ""}</td><td>${esc(Object.entries(p.features || {}).map(([k, v]) => `${k}=${v}`).join(", "))}</td><td>${esc(p.unit)}</td></tr>`).join("") + `</table></div>`;
  if (isAdmin()) {
    h += `<div class="card"><h3>Yeni Ürün</h3><form class="inline" onsubmit="addProduct(event)">` +
      `<input id="np-code" placeholder="Kod" required><input id="np-names" placeholder="Adlar (virgülle)" required style="min-width:220px"><input id="np-unit" placeholder="Birim" value="adet" style="width:90px"><button class="btn btn-primary" type="submit">Ekle</button></form></div>`;
  }
  return h;
}
async function addProduct(ev) {
  ev.preventDefault(); banner(null);
  try {
    await api("/products", { method: "POST", body: {
      code: document.getElementById("np-code").value.trim(),
      names: document.getElementById("np-names").value.split(",").map((s) => s.trim()).filter(Boolean),
      unit: document.getElementById("np-unit").value.trim() || "adet" } });
    await loadCatalog();
  } catch (e) { banner(e.message); }
  render();
}

/* ---------- fiyat & şartlar ---------- */

function vFiyat() {
  let h = `<div class="card"><h3>Fiyatlar</h3>` + hint("Yeni fiyat taslak olarak eklenir; “Yürürlüğe al” derseniz teklifler yeni fiyatı kullanır. Eski teklifler kilitli fiyatlarını korur.") + S.products.map((p) => {
    const rows = (S.prices[p.id] || []).map((v) =>
      `<tr><td>${money(v.price, v.currency)}</td><td>${pill(v.status)}</td>` +
      `<td>${isAdmin() && v.status === "taslak" ? `<button class="btn" onclick="activatePrice('${v.id}')">Yürürlüğe al</button>` : ""}</td></tr>`).join("");
    let block = `<h4>${esc(p.code)} — ${esc(p.names.join(", "))}</h4>`;
    block += rows ? `<table><tr><th>Fiyat</th><th>Durum</th><th></th></tr>${rows}</table>` : `<p class="muted">Fiyat yok.</p>`;
    if (isAdmin()) {
      block += `<form class="inline" onsubmit="addPrice(event, '${p.id}')">` +
        `<input data-price placeholder="Fiyat" type="number" min="0" step="any" required style="width:130px"><input data-cur placeholder="Para birimi" value="TRY" style="width:90px"><button class="btn" type="submit">Taslak ekle</button></form>`;
    }
    return block;
  }).join("") + `</div>`;
  h += `<div class="card"><h3>Şartlar</h3><table><tr><th>Ad</th><th>Metin</th><th>Durum</th><th></th></tr>` +
    S.terms.map((t) => `<tr><td><b>${esc(t.name)}</b></td><td>${esc(t.text)}</td><td>${pill(t.status)}</td>` +
      `<td>${isAdmin() && t.status === "taslak" ? `<button class="btn" onclick="activateTerms('${t.id}')">Yürürlüğe al</button>` : ""}</td></tr>`).join("") + `</table>`;
  if (isAdmin()) {
    h += `<h4>Yeni Şart</h4><form class="inline" onsubmit="addTerms(event)">` +
      `<input id="nt-name" placeholder="Ad" required><input id="nt-text" placeholder="Metin" required style="min-width:280px"><button class="btn btn-primary" type="submit">Ekle</button></form>`;
  }
  return h + `</div>`;
}
async function addPrice(ev, productId) {
  ev.preventDefault(); banner(null);
  try {
    await api("/prices", { method: "POST", body: {
      product_id: productId,
      price: Number(ev.target.querySelector("[data-price]").value),
      currency: ev.target.querySelector("[data-cur]").value.trim() || "TRY" } });
    S.prices[productId] = (await api(`/prices?product_id=${productId}`)).prices;
  } catch (e) { banner(e.message); }
  render();
}
async function activatePrice(id) {
  banner(null);
  try { await api(`/prices/${id}/activate`, { method: "POST" }); await loadAllPrices(); }
  catch (e) { banner(e.message); }
  render();
}
async function addTerms(ev) {
  ev.preventDefault(); banner(null);
  try {
    await api("/terms", { method: "POST", body: {
      name: document.getElementById("nt-name").value.trim(),
      text: document.getElementById("nt-text").value.trim() } });
    await loadTerms();
  } catch (e) { banner(e.message); }
  render();
}
async function activateTerms(id) {
  banner(null);
  try { await api(`/terms/${id}/activate`, { method: "POST" }); await loadTerms(); }
  catch (e) { banner(e.message); }
  render();
}

/* ---------- denetim & ölçümler ---------- */

function vDenetim() {
  return `<div class="card"><div class="row" style="justify-content:space-between"><h3>Denetim Kaydı</h3><button class="btn" onclick="goTab('denetim')">Yenile</button></div>` +
    hint("Tüm önemli işlemler buraya yazılır; bir sorun olduğunda kimin ne yaptığını buradan izlersiniz.") + `<table><tr><th>#</th><th>Zaman</th><th>Aktör</th><th>İşlem</th><th>Hedef</th><th>Detay</th></tr>` +
    S.audit.slice().reverse().map((e) =>
      `<tr><td>${e.seq}</td><td>${dt(e.timestamp)}</td><td>${esc(e.actor)}</td><td>${esc(e.action)}</td><td>${esc(e.target)}</td><td>${esc(e.detail)}</td></tr>`).join("") + `</table></div>`;
}
function vOlcu() {
  const m = S.metrics;
  if (!m) return `<div class="card"><p class="muted">Ölçüm yok.</p></div>`;
  const cards = [
    [m.http.total, "HTTP isteği"],
    [m.jobs.by_status.done || 0, "Tamamlanan iş"],
    [m.jobs.by_status.failed || 0, "Başarısız iş"],
    [m.model.calls, "Model çağrısı"],
    [m.quotes.exported, "Dışa aktarılan teklif"],
    [m.quotes.avg_approval_seconds === null || m.quotes.avg_approval_seconds === undefined ? "—" : m.quotes.avg_approval_seconds + " sn", "Ort. onay süresi"],
  ];
  return hint("Sistemin genel sağlığı ve teklif hattının hızı. Ortalama onay süresi, teklifin sunulmasından onayına geçen süredir.") + `<div class="stat-grid">` + cards.map(([n, l]) =>
    `<div class="stat"><div class="n">${esc(n)}</div><div class="l">${esc(l)}</div></div>`).join("") + `</div>` +
    `<div class="card"><h3>Teklif Durumları</h3><p>` +
    Object.entries(m.quotes.by_status).map(([k, v]) => `${pill(k)} ${v}`).join(" &nbsp; ") + `</p>` +
    `<div class="row"><button class="btn" onclick="goTab('olcu')">Yenile</button></div></div>`;
}

(async function restoreSession() {
  try {
    const saved = localStorage.getItem("linevora_token");
    if (!saved) return;
    S.token = saved;
    S.user = await api("/me");
    const m = location.hash.match(/talep\/([a-z0-9]+)/i);
    await loadInquiries();
    if (m) { S.inquiryId = m[1]; await loadDetail(); }
    render();
  } catch (e) { S.token = null; S.user = null; render(); }
})();
render();

