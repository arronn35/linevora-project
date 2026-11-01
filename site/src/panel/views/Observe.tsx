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
  if (!live) return <div className="p-card"><p className="p-muted">Ölçümler yükleniyor…</p></div>;
  const m = live.metrics; const u = live.usage;
  const failed = m.jobs.by_status.failed || 0;
  return (
    <>
      <Hint>Sistemin genel sağlığı ve teklif hattının hızı. Ortalama onay süresi, teklifin sunulmasından onayına geçen süredir. Bu ekran {auto ? "her 4 saniyede" : "manuel"} yenilenir.</Hint>
      <div className="p-row" style={{ marginBottom: 12 }}>
        <button className="p-btn sm" onClick={() => setAuto((v) => !v)}>{auto ? "Otomatik yenilemeyi durdur" : "Otomatik yenilemeyi başlat"}</button>
        <span className="p-muted">Model: {u.by_model.join(", ") || "—"} · Tahmini token: {u.estimated_tokens.toLocaleString("tr-TR")} · Ort. gecikme: {u.avg_latency_ms != null ? `${u.avg_latency_ms} ms` : "—"}</span>
      </div>
      <div className="p-stat-grid">
        <div className="p-stat"><div className="n">{m.http.total}</div><div className="l">HTTP isteği</div></div>
        <div className="p-stat"><div className="n">{m.http.by_class["2xx"] ?? 0} / {m.http.by_class["4xx"] ?? 0} / {m.http.by_class["5xx"] ?? 0}</div><div className="l">2xx / 4xx / 5xx</div></div>
        <div className="p-stat"><div className="n">{m.jobs.by_status.done || 0}</div><div className="l">Tamamlanan iş</div></div>
        <div className={`p-stat${failed ? " warn" : ""}`}><div className="n">{failed}</div><div className="l">Başarısız iş (dead-letter)</div></div>
        <div className="p-stat"><div className="n">{m.model.calls} <span style={{ fontSize: 14 }}>({m.model.ok}✓ / {m.model.failed}✗)</span></div><div className="l">Model çağrısı</div></div>
        <div className="p-stat"><div className="n">{m.quotes.exported}</div><div className="l">Dışa aktarılan teklif</div></div>
        <div className="p-stat"><div className="n">{m.quotes.avg_approval_seconds != null ? `${m.quotes.avg_approval_seconds} sn` : "—"}</div><div className="l">Ort. onay süresi</div></div>
        <div className="p-stat"><div className="n">{Math.round(m.http.uptime_seconds)} sn</div><div className="l">Çalışma süresi</div></div>
      </div>

      <div className="p-card">
        <h3>Teklif Durumları</h3>
        <p>{Object.entries(m.quotes.by_status).map(([k, v]) => <span key={k} style={{ marginRight: 12 }}><Pill t={k} /> {v}</span>)}</p>
        <h4>İş Durumları</h4>
        <p>{Object.entries(m.jobs.by_status).map(([k, v]) => <span key={k} style={{ marginRight: 12 }}><Pill t={k} /> {v}</span>)}{Object.keys(m.jobs.by_status).length === 0 && <span className="p-muted">İş yok.</span>}</p>
      </div>

      {live.dead.length > 0 && (
        <div className="p-card">
          <h3>Dead-letter — başarısız işler</h3>
          <table><thead><tr><th>İş</th><th>Tür</th><th>Deneme</th><th>Hata</th></tr></thead><tbody>
            {live.dead.map((j) => <tr key={j.job_id}><td><code>{j.job_id.slice(0, 8)}…</code></td><td>{j.kind}</td><td>{j.attempts}</td><td>{j.error ?? "—"}</td></tr>)}
          </tbody></table>
        </div>
      )}

      <div className="p-card">
        <h3>Canlı denetim akışı</h3>
        <p className="p-muted">Son {live.audit.length} olay · yeni olaylar otomatik düşer. Kaynağı olmayan öneri gösterilmez; her işlem buraya yazılır.</p>
        <ul className="p-audit-stream">
          {live.audit.slice().reverse().slice(0, 20).map((e) => (
            <li key={e.seq}><code>{new Date(e.timestamp * 1000).toLocaleTimeString("tr-TR")}</code><span><b>{e.actor}</b> · {e.action} <span className="p-muted">{e.target}{e.detail ? ` — ${e.detail}` : ""}</span></span></li>
          ))}
        </ul>
      </div>
      <span className="p-muted">Prometheus: <code>GET /v1/metrics/prometheus</code> · Model kullanımı: <code>GET /v1/metrics/model-usage</code></span>
      {void notify}
    </>
  );
}

export function AuditView({ entries, refresh, notify }: { entries: AuditEntry[]; refresh: () => void; notify: (m: string, k?: "ok" | "err") => void }) {
  const [q, setQ] = useState("");
  const filtered = entries.filter((e) => !q || `${e.actor} ${e.action} ${e.target} ${e.detail}`.toLocaleLowerCase("tr").includes(q.toLocaleLowerCase("tr")));
  return (
    <div className="p-card">
      <div className="p-row" style={{ justifyContent: "space-between" }}>
        <h3 style={{ margin: 0 }}>Denetim Kaydı</h3>
        <span className="p-row">
          <input placeholder="aktör / işlem / hedef ara" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Denetim ara" />
          <button className="p-btn sm" onClick={refresh}>Yenile</button>
          <button className="p-btn sm" onClick={async () => { try { await api.snapshot(); notify("Anlık görüntü kaydedildi.", "ok"); } catch (e) { notify((e as Error).message); } }}>Anlık görüntü al</button>
        </span>
      </div>
      <Hint>Tüm önemli işlemler buraya yazılır; bir sorun olduğunda kimin ne yaptığını buradan izlersiniz. Kayıtlar yalnızca eklenir, silinmez.</Hint>
      <table><thead><tr><th>#</th><th>Zaman</th><th>Aktör</th><th>İşlem</th><th>Hedef</th><th>Detay</th></tr></thead><tbody>
        {filtered.slice().reverse().map((e) => (
          <tr key={e.seq}><td>{e.seq}</td><td>{dt(e.timestamp)}</td><td>{e.actor}</td><td>{e.action}</td><td>{e.target}</td><td>{e.detail}</td></tr>
        ))}
      </tbody></table>
      {filtered.length === 0 && <p className="p-muted">Kayıt yok.</p>}
    </div>
  );
}
