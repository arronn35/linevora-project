"use strict";
/* Linevora panel: a plain SaaS interface, framework-free. */

const S = {
  token: null, user: null, tab: "inquiries",
  inquiries: [], inquiryId: null,
  versions: [], versionNo: null, sub: "suggestions",
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
  return Number(n).toLocaleString("en-US") + (cur ? " " + esc(cur) : "");
}
function dt(ts) {
  return new Date(ts * 1000).toLocaleString("en-US");
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
  "draft": "p-gray", "open": "p-blue", "pending": "p-amber", "in_review": "p-amber",
  "approved": "p-green", "exported": "p-teal", "active": "p-green",
  "archived": "p-gray", "mandatory": "p-red", "info": "p-gray",
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
    S.quotes.some((q) => q.status === "exported"),
  ];
  const labels = ["Inquiry", "File", "Processing", "Quote", "Approval & sending"];
  const firstOpen = done.findIndex((d) => !d);
  return `<div class="steps">` + labels.map((l, i) =>
    `<span class="step ${done[i] ? "done" : i === firstOpen ? "active" : ""}">${i + 1}. ${l}</span>`).join(`<span class="steparr">→</span>`) + `</div>`;
}

/* ---------- loaders ---------- */

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
  if (S.sub === "suggestions" || S.sub === "quotes") S.suggestions = await api(base + "/suggestions");
  if (S.sub === "gaps") S.gaps = await api(base + "/gaps");
  if (S.sub === "alternatives") S.alternatives = await api(base + "/alternatives");
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

/* ---------- sign-in ---------- */

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
  } catch (e) { banner("Sign-in failed: " + e.message); }
  render();
}
async function doLogout() {
  try { if (S.token) await api("/auth/revoke", { method: "POST" }); } catch (e) {}
  try { localStorage.removeItem("linevora_token"); } catch (e) {}
  S.token = null; S.user = null; S.inquiryId = null; S.quoteDoc = null;
  banner(null); render();
}
function vLogin() {
  return `<div class="card login-card"><h2>Sign in</h2>
    <p class="muted">Turns scattered inquiries (PDF, email) into quotes with sources you can show: upload → process → review the suggestions → build the quote → approve.</p>
    <form class="stack" onsubmit="doLogin(event)">
      <input id="li-user" placeholder="Username" autocomplete="username" required>
      <input id="li-pass" type="password" placeholder="Password" autocomplete="current-password" required>
      <button class="btn btn-primary" type="submit">Sign in</button>
    </form></div>`;
}

/* ---------- shell ---------- */

async function goTab(k) {
  S.tab = k; S.quoteDoc = null; banner(null);
  try {
    if (k === "inquiries") await loadInquiries();
    if (k === "catalog") await loadCatalog();
    if (k === "pricing") { await loadCatalog(); await loadTerms(); await loadAllPrices(); }
    if (k === "audit") await loadAudit();
    if (k === "metrics") await loadMetrics();
  } catch (e) { banner("Loading error: " + e.message); }
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
  const roleHint = S.user.roles.includes("admin") ? "Pricing, products and approval authority are yours"
    : S.user.roles.includes("specialist") ? "You prepare inquiries and quotes" : "Read-only view";
  ub.innerHTML = `${esc(S.user.username)} · ${esc(S.user.roles.join(", "))} <span class="role-hint">${roleHint}</span> <button class="btn btn-light" onclick="doLogout()">Sign out</button>`;
  const allTabs = [["inquiries", "Inquiries"], ["catalog", "Catalog"], ["pricing", "Pricing & Terms"], ["audit", "Audit"], ["metrics", "Metrics"]];
  const tabs = allTabs.filter(([k]) => (k !== "audit" && k !== "metrics") || isAdmin());
  if (!tabs.find(([k]) => k === S.tab)) S.tab = "inquiries";
  let h = `<nav class="tabs">` + tabs.map(([k, l]) =>
    `<button class="tab${S.tab === k ? " active" : ""}" onclick="goTab('${k}')">${l}</button>`).join("") + `</nav>`;
  if (S.tab === "inquiries") h += vInquiries();
  else if (S.tab === "catalog") h += vCatalog();
  else if (S.tab === "pricing") h += vPricing();
  else if (S.tab === "audit") h += vAudit();
  else h += vMetrics();
  if (S.quoteDoc) h += vQuoteModal();
  v.innerHTML = h;
}

/* ---------- inquiries ---------- */

function setFilter(v) { S.filter = v; render(); }
function vInquiries() {
  const q = (S.filter || "").toLocaleLowerCase("en");
  const items = S.inquiries.filter((x) => !q || (x.title + " " + x.customer).toLocaleLowerCase("en").includes(q)).map((q) =>
    `<button class="listitem${q.id === S.inquiryId ? " active" : ""}" onclick="selectInquiry('${q.id}')">` +
    `<b>${esc(q.title)}</b><span class="muted">${esc(q.customer)} · ${esc(q.status)}</span></button>`).join("");
  let left = `<div class="card"><h3>Inquiries</h3><label class="muted">Search <input aria-label="Search inquiries" placeholder="customer / title" value="${esc(S.filter || "")}" onchange="setFilter(this.value)"></label><div class="list">${items || '<p class="muted">No records.</p>'}</div>`;
  if (isEditor()) {
    left += `<h4>New Inquiry</h4><form class="stack" onsubmit="newInquiry(event)">` +
      `<input id="ni-customer" placeholder="Customer" required><input id="ni-title" placeholder="Title" required>` +
      `<button class="btn btn-primary" type="submit">Open</button></form>`;
  }
  left += `</div>`;
  const right = S.inquiryId ? vInquiryDetail() : `<div class="card"><p class="muted">Select an inquiry on the left.</p></div>`;
  return `<div class="grid2"><div>${left}</div><div>${right}</div></div>`;
}

async function newInquiry(ev) {
  ev.preventDefault(); banner(null);
  try {
    const q = await api("/inquiries", { method: "POST", body: {
      customer: document.getElementById("ni-customer").value.trim(),
      title: document.getElementById("ni-title").value.trim() } });
    S.inquiryId = q.id; S.versionNo = null; S.sub = "suggestions"; S.job = null; S.quoteId = null;
    await loadInquiries(); await loadDetail();
  } catch (e) { banner(e.message); }
  render();
}
async function selectInquiry(id) {
  try { history.replaceState(null, "", "#inquiry/" + id); } catch (e) {}
  S.inquiryId = id; S.versionNo = null; S.sub = "suggestions"; S.job = null; S.quoteId = null; S.diff = null;
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
    if (k === "quotes") await loadCatalog();
    await loadSub();
  } catch (e) { banner(e.message); }
  render();
}

function vInquiryDetail() {
  const q = S.inquiries.find((i) => i.id === S.inquiryId) || {};
  let h = `<div class="card"><h3>${esc(q.title || "")}</h3>` +
    `<p class="muted">${esc(q.customer || "")} · ${pill(q.status || "")}</p>`;
  h += vSteps();
  h += `<h4>Versions</h4>`;
  h += hint("Every upload is a new version; older ones are never deleted. If the customer sends a correction, upload it as a new file — the Diff tab shows what changed.");
  if (S.versions.length) {
    h += `<table><tr><th>No</th><th>File</th><th>Pages</th><th></th></tr>` + S.versions.map((v) =>
      `<tr><td>${v.version_no}</td><td>${esc(v.filename)}</td><td>${v.pages.length}</td>` +
      `<td>${v.version_no === S.versionNo ? "<b>selected</b>" : `<button class="btn" onclick="selectVersion(${v.version_no})">Select</button>`}</td></tr>` +
      `<tr><td></td><td colspan="3"><details><summary>Text preview</summary><pre class="text">${esc(v.pages.map((p) => `--- Page ${p.number} ---\n${p.text}`).join("\n\n"))}</pre></details></td></tr>`
    ).join("") + `</table>`;
  } else {
    h += `<p class="muted">No versions yet; upload a file below.</p>`;
  }
  if (isEditor()) {
    h += `<h4>Upload Version</h4><form class="inline" onsubmit="uploadVersion(event)">` +
      `<input id="up-file" type="file" accept=".pdf,.txt,.md" required><button class="btn btn-primary" type="submit">Upload</button></form>`;
  }
  h += `</div>`;
  if (S.versionNo) {
    h += `<div class="card"><h3>Process Version ${S.versionNo}</h3>` + hint("The system extracts requirements from the text and matches them against the catalog. Results land in the Suggestions tab; verify each suggestion against its source quote.") + `<div class="row">`;
    if (isEditor()) h += `<button class="btn btn-primary" onclick="processVersion()">Extract requirements + match</button>`;
    if (S.job) h += `<span>Job: ${pill(S.job.status)} (attempt ${S.job.attempts})</span><button class="btn" onclick="refreshJob()">Refresh status</button>`;
    else h += `<span class="muted">Not processed yet.</span>`;
    h += `</div></div>`;
    const subs = [["suggestions", "Suggestions"], ["gaps", "Gaps"], ["alternatives", "Alternatives"], ["diff", "Diff"], ["quotes", "Quotes"]];
    h += `<div class="card"><div class="subtabs">` + subs.map(([k, l]) =>
      `<button class="subtab${S.sub === k ? " active" : ""}" onclick="goSub('${k}')">${l}</button>`).join("") + `</div>`;
    if (S.sub === "suggestions") h += vSubSuggestions();
    else if (S.sub === "gaps") h += vSubGaps();
    else if (S.sub === "alternatives") h += vSubAlternatives();
    else if (S.sub === "diff") h += vSubDiff();
    else h += vSubQuotes();
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
  } catch (e) { banner("Loading error: " + e.message); }
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
    else banner("Job failed: " + (job.error || ""));
  } catch (e) { banner("Processing error: " + e.message); }
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

function vSubSuggestions() {
  const d = S.suggestions;
  const desc = hint("The score is between 0 and 1: 0.85 and above is usually an exact match, below that needs careful review. A \u201cpending\u201d badge means the team has not decided yet.");
  if (!d || !d.requirements.length) return desc + `<p class="muted">No requirements. Process the version first.</p>`;
  return desc + d.requirements.map((r) => {
    const sugs = d.suggestions.filter((s) => s.requirement_id === r.id);
    const feat = Object.entries(r.features || {}).map(([k, v]) => `${esc(k)}=${esc(v)}`).join(", ");
    let h = `<div class="card"><b>${esc(r.product_type)}</b> <span class="muted">${esc(r.quantity === null || r.quantity === undefined ? "?" : r.quantity)} ${esc(r.unit || "")}${feat ? " · " + feat : ""}</span>` +
      `<br><span class="muted">Source: page ${r.source.page} — “${esc(r.source.quote)}”</span> <button class="btn" onclick="showSource('${r.id}')">Show source</button>` +
      (S.sourceView === r.id ? `<pre class="srcview">${highlighted(r.source.page, r.source.quote)}</pre>` : "");
    if (!sugs.length) h += `<p class="muted">No suggestions.</p>`;
    else h += `<table><tr><th>Product</th><th>Score</th><th></th><th>Rationale</th></tr>` + sugs.map((s) =>
      `<tr><td><b>${esc(s.product.code)}</b><br><span class="muted">${esc(s.product.names.join(", "))}</span></td>` +
      `<td>${s.score.toFixed(2)}</td>` +
      `<td><div class="scorebar"><div style="width:${Math.round(s.score * 100)}%"></div></div></td>` +
      `<td>${s.reasons.map(esc).join("<br>")}<br>${pill(s.status)}${isEditor() && s.id ? ` <button class="btn" onclick="decideSuggestion('${s.id}','approved')">Accept</button> <button class="btn" onclick="decideSuggestion('${s.id}','rejected')">Reject</button>` : ""}</td></tr>`).join("") + `</table>`;
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
  if (!pg) return "Page text not found.";
  const text = esc(pg.text); const q = esc(quote);
  const i = text.toLocaleLowerCase("en").indexOf(q.toLocaleLowerCase("en"));
  if (i < 0) return text;
  return text.slice(0, i) + "<mark>" + text.slice(i, i + q.length) + "</mark>" + text.slice(i + q.length);
}
function vSubGaps() {
  const d = S.gaps;
  const desc = hint("These are questions to ask the customer. \u201cMandatory\u201d ones must be completed before the quote; \u201cinfo\u201d ones improve quality.");
  if (!d || !d.gaps.length) return desc + `<p class="muted">No gaps — a quote can be built.</p>`;
  return desc + `<div class="row" style="margin-bottom:10px"><button class="btn" onclick="copyGaps()">Copy question list</button></div>` + `<table><tr><th>Field</th><th>Question</th><th>Severity</th><th>Status</th><th></th></tr>` + d.gaps.map((g) =>
    `<tr><td>${esc(g.field)}</td><td>${esc(g.question)}</td><td>${pill(g.severity)}</td><td>${pill(g.status)}${g.answer ? "<br>" + esc(g.answer) : ""}</td><td>${isEditor() && g.status === "open" ? `<button class="btn" onclick="answerGap('${g.id}')">Answer</button>` : ""}</td></tr>`).join("") + `</table>`;
}

function vSubAlternatives() {
  const d = S.alternatives;
  const desc = hint("When there is no exact product, the closest candidates are compared by criterion. The \u201cMatch\u201d column shows which condition holds; whether to suggest it is your decision.");
  if (!d || !d.alternatives.length) return desc + `<p class="muted">No alternatives (there is an exact match, or the version was not processed).</p>`;
  return desc + d.alternatives.map((a) =>
    `<div class="card"><b>${esc(a.product.code)}</b> <span class="muted">${esc(a.product.names.join(", "))} · score ${a.score.toFixed(2)}</span> ${pill(a.status)}` +
    `<table><tr><th>Criterion</th><th>Wanted</th><th>Offered</th><th>Match</th></tr>` + a.comparison.map((r) =>
      `<tr><td>${esc(r.criterion)}</td><td>${esc(r.wanted)}</td><td>${esc(r.offered)}</td><td>${r.match ? "Yes" : "—"}</td></tr>`).join("") + `</table>` +
    `<span class="muted">${a.reasons.map(esc).join("<br>")}</span></div>`).join("");
}

function vSubDiff() {
  const opts = S.versions.map((v) => v.version_no);
  const from = S.diffFrom !== null && S.diffFrom !== undefined ? S.diffFrom : opts[0];
  const to = S.diffTo !== null && S.diffTo !== undefined ? S.diffTo : opts[opts.length - 1];
  const sel = (id, val) => `<select id="${id}">` + opts.map((n) =>
    `<option value="${n}"${n === val ? " selected" : ""}>Version ${n}</option>`).join("") + `</select>`;
  let h = hint("Items whose quantity, unit or features changed between two versions; items added and removed.") + `<form class="inline" onsubmit="loadDiff(event)">${sel("diff-a", from)}${sel("diff-b", to)}` +
    `<button class="btn btn-primary" type="submit">Compare</button></form>`;
  if (!S.diff) return h + `<p class="muted">Select two versions and compare.</p>`;
  if (!S.diff.changes.length) return h + `<p class="muted">No differences.</p>`;
  h += `<table><tr><th>Type</th><th>Product</th><th>Field</th><th>Old</th><th>New</th></tr>` + S.diff.changes.map((c) =>
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
  const answer = prompt("Answer / note:");
  if (answer === null) return;
  banner(null);
  try { await api(`/gaps/${id}/answer`, { method: "POST", body: { status: "answered", answer } }); await loadSub(); }
  catch (e) { banner(e.message); }
  render();
}
async function downloadPdf() {
  banner(null);
  try {
    const res = await fetch(`/v1/quotes/${S.quoteId}/export.pdf`, { headers: { Authorization: "Bearer " + S.token } });
    if (!res.ok) throw new Error("Could not fetch the PDF (" + res.status + ")");
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "quote.pdf"; a.click();
    URL.revokeObjectURL(a.href);
  } catch (e) { banner(e.message); }
}
async function copyGaps() {
  const d = S.gaps;
  if (!d || !d.gaps.length) return;
  const lines = ["Hello, to prepare your quote we would like the following information:"]
    .concat(d.gaps.map((g) => "- " + g.question));
  try {
    await navigator.clipboard.writeText(lines.join("\n"));
    banner("Question list copied to clipboard.", "ok");
  } catch (e) {
    banner("Copy failed: " + e.message);
  }
}

/* ---------- quotes ---------- */

function vSubQuotes() {
  const reqs = (S.suggestions && S.suggestions.requirements) || [];
  const sugs = (S.suggestions && S.suggestions.suggestions) || [];
  let h = hint("Products are pre-selected from the best suggestion; if you leave the quantity blank, the quantity in the requirement is used. The price is locked from the version active when the quote is created.") + `<h4>Quotes</h4>`;
  h += S.quotes.length ? `<div class="list">` + S.quotes.map((q) =>
    `<button class="listitem${q.id === S.quoteId ? " active" : ""}" onclick="selectQuote('${q.id}')">` +
    `<span><b>Version ${q.version_no} quote</b> ${pill(q.status)}</span><span class="muted">${esc(q.created_by)}${q.approved_by ? " · approved by: " + esc(q.approved_by) : ""}</span></button>`).join("") + `</div>`
    : `<p class="muted">No quotes for this inquiry.</p>`;
  if (isEditor() && reqs.length) {
    h += `<h4>Lines</h4><table><tr><th>Requirement</th><th>Product</th><th>Quantity</th></tr>` + reqs.map((r) => {
      const top = sugs.find((s) => s.requirement_id === r.id);
      const opts = [`<option value="">— select —</option>`].concat(S.products.map((p) =>
        `<option value="${p.id}"${top && top.product.code === p.code ? " selected" : ""}>${esc(p.code)} — ${esc(p.names.join(", "))}</option>`)).join("");
      return `<tr data-req="${r.id}"><td><b>${esc(r.product_type)}</b><br><span class="muted">${esc(r.quantity === null || r.quantity === undefined ? "?" : r.quantity)} ${esc(r.unit || "")}</span></td>` +
        `<td><select class="q-prod">${opts}</select></td>` +
        `<td><input class="q-qty" type="number" min="0" step="any" placeholder="${esc(r.quantity === null || r.quantity === undefined ? "" : r.quantity)}" style="width:110px"></td></tr>`;
    }).join("") + `</table><div class="row">` +
      `<button class="btn btn-primary" onclick="buildQuote(false)">Create new quote</button>`;
    if (S.quoteDetail && S.quoteDetail.status === "draft") {
      h += `<button class="btn" onclick="buildQuote(true)">Update selected draft</button>`;
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
  if (!lines.length) { banner("Select a product for at least one line."); return; }
  try {
    if (edit) S.quoteDetail = await api(`/quotes/${S.quoteId}/lines`, { method: "PUT", body: { lines } });
    else {
      S.quoteDetail = await api(`/inquiries/${S.inquiryId}/versions/${S.versionNo}/quotes`, { method: "POST", body: { lines } });
      S.quoteId = S.quoteDetail.id;
    }
    S.quotes = (await api(`/inquiries/${S.inquiryId}/quotes`)).quotes;
  } catch (e) { banner("Quote error: " + e.message); }
  render();
}
function vQuoteDetail() {
  const q = S.quoteDetail;
  let h = `<h4>Quote Detail ${pill(q.status)}</h4><table><tr><th>Product</th><th>Quantity</th><th>Unit price</th><th>Amount</th></tr>` +
    q.lines.map((l) =>
      `<tr><td><b>${esc(l.product.code)}</b><br><span class="muted">${esc(l.product.names.join(", "))}</span></td>` +
      `<td>${esc(l.quantity)} ${esc(l.unit)}</td><td>${money(l.unit_price, l.currency)}</td><td>${money(l.amount, l.currency)}</td></tr>`).join("") +
    q.totals.map((t) => `<tr class="total-row"><td colspan="3">Total</td><td>${money(t.amount, t.currency)}</td></tr>`).join("") + `</table>`;
  h += `<p class="muted">Prepared by: ${esc(q.created_by)}${q.approved_by ? " · Approved by: " + esc(q.approved_by) : ""}<br>Line prices are locked from the price version active when the quote was created; a later price change does not affect this quote.</p><div class="row">`;
  if (isEditor() && q.status === "draft") h += `<button class="btn btn-primary" onclick="quoteAction('submit')">Submit for review</button>`;
  if (isAdmin() && q.status === "in_review") h += `<button class="btn btn-primary" onclick="quoteAction('approve')">Approve</button><button class="btn" onclick="quoteAction('return')">Return</button>`;
  h += `<button class="btn" onclick="previewQuote()">Preview</button>`;
  if (isEditor() && (q.status === "approved" || q.status === "exported")) h += `<button class="btn btn-primary" onclick="exportQuote()">Export</button>`;
  return h + `</div>`;
}
async function quoteAction(action) {
  if (action === "approve" && !confirm("The quote will be approved and ready to export. Are you sure?")) return;
  banner(null);
  try {
    S.quoteDetail = await api(`/quotes/${S.quoteId}/${action}`, { method: "POST" });
    S.quotes = (await api(`/inquiries/${S.inquiryId}/quotes`)).quotes;
  } catch (e) { banner(e.message); }
  render();
}
async function exportQuote() {
  if (!confirm("The approved quote will be exported and a document will be generated. Are you sure?")) return;
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
    `<div class="quote-head"><h2>Quote ${d.preview ? "(Preview)" : ""}</h2><button class="btn" onclick="closeModal()">Close</button></div>` +
    `<p><b>Customer:</b> ${esc(d.customer)} &nbsp; <b>Version:</b> ${esc(d.version_no)} &nbsp; ${pill(d.status)}</p>` +
    `<table><tr><th>Product</th><th>Quantity</th><th>Unit price</th><th>Amount</th></tr>` +
    d.lines.map((l) => `<tr><td><b>${esc(l.product_code)}</b><br><span class="muted">${esc((l.product_names || []).join(", "))}</span></td><td>${esc(l.quantity)} ${esc(l.unit)}</td><td>${money(l.unit_price, l.currency)}</td><td>${money(l.amount, l.currency)}</td></tr>`).join("") +
    d.totals.map((t) => `<tr class="total-row"><td colspan="3">Total</td><td>${money(t.amount, t.currency)}</td></tr>`).join("") + `</table>` +
    (d.terms ? `<h4>${esc(d.terms.name)}</h4><div class="termsbox">${esc(d.terms.text)}</div>` : "") +
    `<p class="muted">Prepared by: ${esc(d.prepared_by)}${d.approved_by ? " · Approved by: " + esc(d.approved_by) : ""}</p>` +
    (!d.preview ? `<div class="row"><button class="btn btn-primary" onclick="downloadPdf()">Download PDF</button></div>` : "") +
    `</div></div>`;
}

/* ---------- catalog ---------- */

function vCatalog() {
  let h = `<div class="card"><h3>Products</h3>` + hint("Synonyms matter a lot: if the customer calls the product by another name, the match comes from here. You write the code once; names are comma-separated.") + `<table><tr><th>Code</th><th>Names</th><th>Features</th><th>Unit</th></tr>` +
    S.products.map((p) => `<tr><td><b>${esc(p.code)}</b></td><td>${esc(p.names.join(", "))}${p.synonyms.length ? `<br><span class="muted">syn: ${esc(p.synonyms.join(", "))}</span>` : ""}</td><td>${esc(Object.entries(p.features || {}).map(([k, v]) => `${k}=${v}`).join(", "))}</td><td>${esc(p.unit)}</td></tr>`).join("") + `</table></div>`;
  if (isAdmin()) {
    h += `<div class="card"><h3>New Product</h3><form class="inline" onsubmit="addProduct(event)">` +
      `<input id="np-code" placeholder="Code" required><input id="np-names" placeholder="Names (comma-separated)" required style="min-width:220px"><input id="np-unit" placeholder="Unit" value="pcs" style="width:90px"><button class="btn btn-primary" type="submit">Add</button></form></div>`;
  }
  return h;
}
async function addProduct(ev) {
  ev.preventDefault(); banner(null);
  try {
    await api("/products", { method: "POST", body: {
      code: document.getElementById("np-code").value.trim(),
      names: document.getElementById("np-names").value.split(",").map((s) => s.trim()).filter(Boolean),
      unit: document.getElementById("np-unit").value.trim() || "pcs" } });
    await loadCatalog();
  } catch (e) { banner(e.message); }
  render();
}

/* ---------- pricing & terms ---------- */

function vPricing() {
  let h = `<div class="card"><h3>Prices</h3>` + hint("A new price is added as a draft; when you activate it, quotes use the new price. Older quotes keep their locked prices.") + S.products.map((p) => {
    const rows = (S.prices[p.id] || []).map((v) =>
      `<tr><td>${money(v.price, v.currency)}</td><td>${pill(v.status)}</td>` +
      `<td>${isAdmin() && v.status === "draft" ? `<button class="btn" onclick="activatePrice('${v.id}')">Activate</button>` : ""}</td></tr>`).join("");
    let block = `<h4>${esc(p.code)} — ${esc(p.names.join(", "))}</h4>`;
    block += rows ? `<table><tr><th>Price</th><th>Status</th><th></th></tr>${rows}</table>` : `<p class="muted">No price.</p>`;
    if (isAdmin()) {
      block += `<form class="inline" onsubmit="addPrice(event, '${p.id}')">` +
        `<input data-price placeholder="Price" type="number" min="0" step="any" required style="width:130px"><input data-cur placeholder="Currency" value="USD" style="width:90px"><button class="btn" type="submit">Add draft</button></form>`;
    }
    return block;
  }).join("") + `</div>`;
  h += `<div class="card"><h3>Terms</h3><table><tr><th>Name</th><th>Text</th><th>Status</th><th></th></tr>` +
    S.terms.map((t) => `<tr><td><b>${esc(t.name)}</b></td><td>${esc(t.text)}</td><td>${pill(t.status)}</td>` +
      `<td>${isAdmin() && t.status === "draft" ? `<button class="btn" onclick="activateTerms('${t.id}')">Activate</button>` : ""}</td></tr>`).join("") + `</table>`;
  if (isAdmin()) {
    h += `<h4>New Terms</h4><form class="inline" onsubmit="addTerms(event)">` +
      `<input id="nt-name" placeholder="Name" required><input id="nt-text" placeholder="Text" required style="min-width:280px"><button class="btn btn-primary" type="submit">Add</button></form>`;
  }
  return h + `</div>`;
}
async function addPrice(ev, productId) {
  ev.preventDefault(); banner(null);
  try {
    await api("/prices", { method: "POST", body: {
      product_id: productId,
      price: Number(ev.target.querySelector("[data-price]").value),
      currency: ev.target.querySelector("[data-cur]").value.trim() || "USD" } });
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

/* ---------- audit & metrics ---------- */

function vAudit() {
  return `<div class="card"><div class="row" style="justify-content:space-between"><h3>Audit Log</h3><button class="btn" onclick="goTab('audit')">Refresh</button></div>` +
    hint("Every important operation is written here; when something goes wrong you can trace who did what.") + `<table><tr><th>#</th><th>Time</th><th>Actor</th><th>Action</th><th>Target</th><th>Detail</th></tr>` +
    S.audit.slice().reverse().map((e) =>
      `<tr><td>${e.seq}</td><td>${dt(e.timestamp)}</td><td>${esc(e.actor)}</td><td>${esc(e.action)}</td><td>${esc(e.target)}</td><td>${esc(e.detail)}</td></tr>`).join("") + `</table></div>`;
}
function vMetrics() {
  const m = S.metrics;
  if (!m) return `<div class="card"><p class="muted">No metrics.</p></div>`;
  const cards = [
    [m.http.total, "HTTP requests"],
    [m.jobs.by_status.done || 0, "Completed jobs"],
    [m.jobs.by_status.failed || 0, "Failed jobs"],
    [m.model.calls, "Model calls"],
    [m.quotes.exported, "Exported quotes"],
    [m.quotes.avg_approval_seconds === null || m.quotes.avg_approval_seconds === undefined ? "—" : m.quotes.avg_approval_seconds + " sec", "Avg. approval time"],
  ];
  return hint("Overall system health and the speed of the quote pipeline. Average approval time is the time from submitting a quote to its approval.") + `<div class="stat-grid">` + cards.map(([n, l]) =>
    `<div class="stat"><div class="n">${esc(n)}</div><div class="l">${esc(l)}</div></div>`).join("") + `</div>` +
    `<div class="card"><h3>Quote Statuses</h3><p>` +
    Object.entries(m.quotes.by_status).map(([k, v]) => `${pill(k)} ${v}`).join(" &nbsp; ") + `</p>` +
    `<div class="row"><button class="btn" onclick="goTab('metrics')">Refresh</button></div></div>`;
}

(async function restoreSession() {
  try {
    const saved = localStorage.getItem("linevora_token");
    if (!saved) return;
    S.token = saved;
    S.user = await api("/me");
    const m = location.hash.match(/inquiry\/([a-z0-9]+)/i);
    await loadInquiries();
    if (m) { S.inquiryId = m[1]; await loadDetail(); }
    render();
  } catch (e) { S.token = null; S.user = null; render(); }
})();
render();

