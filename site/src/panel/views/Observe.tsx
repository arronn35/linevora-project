import { useState } from "react";
import { api, dt, type AuditEntry, type Metrics, type ModelUsage } from "../api";
import { usePolling } from "../hooks";
import { Hint, Pill } from "../ui";

export interface LiveData { metrics: Metrics; usage: ModelUsage; audit: AuditEntry[]; dead: { job_id: string; kind: string; attempts: number; error: string | null }[]; health: string }

export function useLive(enabled: boolean, intervalMs = 4000) {
  return usePolling<LiveData>(async () => {
    const [metrics, usage, audit, dead, health] = await Promise.all([
      api.metrics(), api.modelUsage(), api.audit(40, 0), api.deadLetter(), api.health().catch(() => ({ status: "?" })),
    ]);
    return { metrics, usage, audit: audit.entries, dead: dead.jobs, health: health.status };
  }, intervalMs, enabled);
}

export function ObserveView({ live, notify }: { live: LiveData | null; notify: (m: string, k?: "ok" | "err") => void }) {
  const [auto, setAuto] = useState(true);
  if (!live) return <div className="p-card"><p className="p-muted">Loading metrics…</p></div>;
  const m = live.metrics; const u = live.usage;
  const failed = m.jobs.by_status.failed || 0;
  return (
    <>
      <Hint>Overall system health and the speed of the quote pipeline. Average approval time is the time from submitting a quote to its approval. This screen refreshes {auto ? "every 4 seconds" : "manually"}.</Hint>
      <div className="p-row" style={{ marginBottom: 12 }}>
        <button className="p-btn sm" onClick={() => setAuto((v) => !v)}>{auto ? "Stop auto-refresh" : "Start auto-refresh"}</button>
        <span className="p-muted">Model: {u.by_model.join(", ") || "—"} · Est. tokens: {u.estimated_tokens.toLocaleString("en-US")} · Avg. latency: {u.avg_latency_ms != null ? `${u.avg_latency_ms} ms` : "—"}</span>
      </div>
      <div className="p-stat-grid">
        <div className="p-stat"><div className="n">{m.http.total}</div><div className="l">HTTP requests</div></div>
        <div className="p-stat"><div className="n">{m.http.by_class["2xx"] ?? 0} / {m.http.by_class["4xx"] ?? 0} / {m.http.by_class["5xx"] ?? 0}</div><div className="l">2xx / 4xx / 5xx</div></div>
        <div className="p-stat"><div className="n">{m.jobs.by_status.done || 0}</div><div className="l">Completed jobs</div></div>
        <div className={`p-stat${failed ? " warn" : ""}`}><div className="n">{failed}</div><div className="l">Failed jobs (dead-letter)</div></div>
        <div className="p-stat"><div className="n">{m.model.calls} <span style={{ fontSize: 14 }}>({m.model.ok}✓ / {m.model.failed}✗)</span></div><div className="l">Model calls</div></div>
        <div className="p-stat"><div className="n">{m.quotes.exported}</div><div className="l">Exported quotes</div></div>
        <div className="p-stat"><div className="n">{m.quotes.avg_approval_seconds != null ? `${m.quotes.avg_approval_seconds} sec` : "—"}</div><div className="l">Avg. approval time</div></div>
        <div className="p-stat"><div className="n">{Math.round(m.http.uptime_seconds)} sec</div><div className="l">Uptime</div></div>
      </div>

      <div className="p-card">
        <h3>Quote Statuses</h3>
        <p>{Object.entries(m.quotes.by_status).map(([k, v]) => <span key={k} style={{ marginRight: 12 }}><Pill t={k} /> {v}</span>)}</p>
        <h4>Job Statuses</h4>
        <p>{Object.entries(m.jobs.by_status).map(([k, v]) => <span key={k} style={{ marginRight: 12 }}><Pill t={k} /> {v}</span>)}{Object.keys(m.jobs.by_status).length === 0 && <span className="p-muted">No jobs.</span>}</p>
      </div>

      {live.dead.length > 0 && (
        <div className="p-card">
          <h3>Dead-letter — failed jobs</h3>
          <table><thead><tr><th>Job</th><th>Kind</th><th>Attempts</th><th>Error</th></tr></thead><tbody>
            {live.dead.map((j) => <tr key={j.job_id}><td><code>{j.job_id.slice(0, 8)}…</code></td><td>{j.kind}</td><td>{j.attempts}</td><td>{j.error ?? "—"}</td></tr>)}
          </tbody></table>
        </div>
      )}

      <div className="p-card">
        <h3>Live audit stream</h3>
        <p className="p-muted">Last {live.audit.length} events · new events arrive automatically. No suggestion is shown without a source; every operation is written here.</p>
        <ul className="p-audit-stream">
          {live.audit.slice().reverse().slice(0, 20).map((e) => (
            <li key={e.seq}><code>{new Date(e.timestamp * 1000).toLocaleTimeString("en-US")}</code><span><b>{e.actor}</b> · {e.action} <span className="p-muted">{e.target}{e.detail ? ` — ${e.detail}` : ""}</span></span></li>
          ))}
        </ul>
      </div>
      <span className="p-muted">Prometheus: <code>GET /v1/metrics/prometheus</code> · Model usage: <code>GET /v1/metrics/model-usage</code></span>
      {void notify}
    </>
  );
}

export function AuditView({ entries, refresh, notify }: { entries: AuditEntry[]; refresh: () => void; notify: (m: string, k?: "ok" | "err") => void }) {
  const [q, setQ] = useState("");
  const filtered = entries.filter((e) => !q || `${e.actor} ${e.action} ${e.target} ${e.detail}`.toLocaleLowerCase("en").includes(q.toLocaleLowerCase("en")));
  return (
    <div className="p-card">
      <div className="p-row" style={{ justifyContent: "space-between" }}>
        <h3 style={{ margin: 0 }}>Audit Log</h3>
        <span className="p-row">
          <input placeholder="search actor / action / target" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search audit log" />
          <button className="p-btn sm" onClick={refresh}>Refresh</button>
          <button className="p-btn sm" onClick={async () => { try { await api.snapshot(); notify("Snapshot saved.", "ok"); } catch (e) { notify((e as Error).message); } }}>Take snapshot</button>
        </span>
      </div>
      <Hint>Every important operation is written here; when something goes wrong you can trace who did what. Records are only appended, never deleted.</Hint>
      <table><thead><tr><th>#</th><th>Time</th><th>Actor</th><th>Action</th><th>Target</th><th>Detail</th></tr></thead><tbody>
        {filtered.slice().reverse().map((e) => (
          <tr key={e.seq}><td>{e.seq}</td><td>{dt(e.timestamp)}</td><td>{e.actor}</td><td>{e.action}</td><td>{e.target}</td><td>{e.detail}</td></tr>
        ))}
      </tbody></table>
      {filtered.length === 0 && <p className="p-muted">No records.</p>}
    </div>
  );
}
