import { useCallback, useEffect, useRef, useState } from "react";
import { api, getToken, isAdmin, mpApi, setToken, type User } from "./api";
import { useLive } from "./views/Observe";
import { AuditView, ObserveView } from "./views/Observe";
import { CatalogView, PricingView } from "./views/Catalog";
import { InquiriesView } from "./views/Inquiries";
import { Marketplace, Overview } from "../marketplace/Marketplace";
import { Banner, PageHeader, Skeleton } from "./ui";
import "./panel.css";

type Tab = "genel" | "kesfet" | "olustur" | "ilanlarim" | "tekliflerim" | "mesajlar" | "talepler" | "katalog" | "fiyat" | "izleme" | "denetim";

const NAV_GROUPS: { label: string; items: [Tab, string][] }[] = [
  { label: "Genel", items: [["genel", "Genel Bakış"]] },
  { label: "Pazar Yeri", items: [["kesfet", "Keşfet"], ["olustur", "İlan oluştur"], ["ilanlarim", "İlanlarım"], ["tekliflerim", "Tekliflerim"], ["mesajlar", "Mesajlar"]] },
  { label: "Operasyon", items: [["talepler", "Talepler"]] },
  { label: "Yönetim", items: [["katalog", "Katalog"], ["fiyat", "Fiyat & Şartlar"], ["izleme", "İzleme"], ["denetim", "Denetim"]] },
];

const TAB_META: Record<Tab, { title: string; desc: string }> = {
  genel: { title: "Genel Bakış", desc: "Yayındaki ilanlarınız, bekleyen işler ve son hareketler tek bakışta." },
  kesfet: { title: "İlanları keşfet", desc: "Yayımdaki tedarik talepleri ve satış ilanları. Kaynağı gösterilemeyen bilgi tamamlanmaz." },
  olustur: { title: "İlan oluştur", desc: "İhtiyacınızı anlatın; kontrol adımında onaylamadan hiçbir şey yayımlanmaz." },
  ilanlarim: { title: "İlanlarım", desc: "Kendi ilanlarınız: taslak, yayında, sonuçlanan ve kapananlar." },
  tekliflerim: { title: "Tekliflerim", desc: "Verdiğiniz teklifler ve revizyonları. Rakip teklifler size gösterilmez." },
  mesajlar: { title: "Mesajlar", desc: "Bildirimler ve ilan sahibi–teklif veren konuşmaları." },
  talepler: { title: "Talepler", desc: "Dağınık talepler kaynağı gösterilebilir tekliflere dönüşür: yükle, işlet, kontrol et, onayla." },
  katalog: { title: "Katalog", desc: "Ürün kodları, adlar ve eşanlamlılar. Eşleşme kalitesi buradan gelir." },
  fiyat: { title: "Fiyat & Şartlar", desc: "Sürümli fiyat ve şartlar; teklif, kurulduğu anın sürümüne kilitlenir." },
  izleme: { title: "İzleme", desc: "Sistem sağlığı, iş kuyruğu ve model kullanımı — yalnızca admin." },
  denetim: { title: "Denetim", desc: "Kayıtlar yalnızca eklenir, silinmez. Kimin ne yaptığı buradan izlenir." },
};

export function Panel() {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);
  const [tab, setTab] = useState<Tab>("genel");
  const [banner, setBanner] = useState<{ msg: string; kind: "ok" | "err" } | null>(null);
  const [unread, setUnread] = useState(0);
  const navRef = useRef<HTMLElement>(null);
  const notify = useCallback((msg: string, kind: "ok" | "err" = "err") => {
    setBanner({ msg, kind });
    if (kind === "ok") window.setTimeout(() => setBanner((b) => (b?.msg === msg ? null : b)), 4000);
  }, []);
  const admin = isAdmin(user);
  const live = useLive(!!user && admin, 4000);
  const [auditFull, setAuditFull] = useState<import("./api").AuditEntry[]>([]);
  const loadAuditFull = useCallback(async () => {
    try { setAuditFull((await api.audit(200, 0)).entries); } catch (e) { notify((e as Error).message); }
  }, [notify]);
  useEffect(() => { if (tab === "denetim" && admin) void loadAuditFull(); }, [tab, admin, loadAuditFull]);

  useEffect(() => {
    (async () => {
      if (!getToken()) { setBooting(false); return; }
      try { setUser(await api.me()); } catch { setToken(null); }
      setBooting(false);
    })();
  }, []);

  /* Okunmamış bildirim sayısı — üst bar göstergesi */
  useEffect(() => {
    if (!user) { setUnread(0); return; }
    let alive = true;
    const load = async () => {
      try {
        const r = await mpApi.notifications();
        if (alive) setUnread(r.notifications.filter((n) => !n.read).length);
      } catch { /* gösterge sessizce eski değerde kalır */ }
    };
    void load();
    const id = window.setInterval(() => void load(), 20000);
    return () => { alive = false; window.clearInterval(id); };
  }, [user, tab]);

  async function onLogin(e: React.FormEvent) {
    e.preventDefault();
    const f = e.target as HTMLFormElement;
    const u = f.querySelector<HTMLInputElement>("#p-user")!.value.trim();
    const p = f.querySelector<HTMLInputElement>("#p-pass")!.value;
    try {
      const t = await api.login(u, p);
      setToken(t.access_token);
      setUser(await api.me());
      setBanner(null);
    } catch (err) { notify(`Giriş başarısız: ${(err as Error).message}`); }
  }
  async function onLogout() {
    try { await api.revoke(); } catch { /* yoksay */ }
    setToken(null); setUser(null); setBanner(null); setTab("genel");
  }

  if (booting) {
    return (
      <div className="panel-root">
        <div className="p-main" aria-busy="true">
          <Skeleton lines={4} label="Panel yükleniyor" />
          <p className="p-muted" role="status">Yükleniyor…</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="panel-root">
        <header className="p-topbar">
          <a className="p-logo" href="/" aria-label="Linevora ana sayfa"><i aria-hidden /> <span className="brand">Linevora</span> <small>Teklif Paneli</small></a>
          <a className="p-btn ghost-dark" href="/" style={{ textDecoration: "none" }}>Vitrin</a>
        </header>
        <div className="p-main">
          <Banner msg={banner?.msg ?? null} kind={banner?.kind} />
          <div className="p-login">
            <p className="p-eyebrow">Panele giriş</p>
            <h2>Tekrar <em>hoş geldiniz.</em></h2>
            <p className="p-muted">Dağınık talepleri (PDF, e-posta) kaynağı gösterilebilir tekliflere dönüştürür: yükle → işlet → önerileri kontrol et → teklif kur → onayla.</p>
            <form className="p-stack" style={{ marginTop: 16 }} onSubmit={onLogin}>
              <label htmlFor="p-user">Kullanıcı adı</label>
              <input id="p-user" placeholder="Kullanıcı adı" autoComplete="username" required aria-label="Kullanıcı adı" />
              <label htmlFor="p-pass">Parola</label>
              <input id="p-pass" type="password" placeholder="Parola" autoComplete="current-password" required aria-label="Parola" />
              <button className="p-btn primary" type="submit">Giriş yap</button>
            </form>
            <p className="p-muted" style={{ marginTop: 12 }}>Geliştirme: <code>admin / admin123</code> · Roller: admin, specialist, viewer</p>
          </div>
        </div>
      </div>
    );
  }

  const roleHint = user.roles.includes("admin") ? "Fiyat, ürün ve onay yetkisi sizde"
    : user.roles.includes("specialist") ? "Talep ve teklif hazırlarsınız" : "Salt okunur görüntüleme";
  const visibleInGroup = (items: [Tab, string][]) =>
    items.filter(([k]) => (k === "izleme" || k === "denetim" ? admin : true));
  const allVisible = NAV_GROUPS.flatMap((g) => visibleInGroup(g.items)).map(([k]) => k);
  const go = (t: Tab) => { setTab(t); setBanner(null); };

  const onNavKey = (e: React.KeyboardEvent) => {
    if (!["ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft", "Home", "End"].includes(e.key)) return;
    const btns = Array.from(navRef.current?.querySelectorAll<HTMLButtonElement>("[data-nav-item]") ?? []);
    const i = btns.indexOf(document.activeElement as HTMLButtonElement);
    if (i < 0) return;
    e.preventDefault();
    const next = e.key === "Home" ? 0 : e.key === "End" ? btns.length - 1
      : (i + (e.key === "ArrowDown" || e.key === "ArrowRight" ? 1 : -1) + btns.length) % btns.length;
    btns[next]?.focus();
  };

  const m = live.data?.metrics;
  const failedJobs = m?.jobs.by_status.failed || 0;
  const meta = TAB_META[tab];

  return (
    <div className="panel-root">
      <a className="p-skip" href="#panel-main">İçeriğe atla</a>
      <header className="p-topbar">
        <a className="p-logo" href="/panel" aria-label="Linevora panel ana sayfa"><i aria-hidden /> <span className="brand">Linevora</span> <small>Teklif Paneli · İzlenebilir</small></a>
        <div className="p-topbar-right">
          <span className="p-live-state">
            <span className={`live-dot${live.data || !admin ? "" : " off"}`} aria-hidden />
            <span role="status">{admin ? (live.data ? "Canlı" : "Bağlanıyor") : "Oturum açık"}</span>
          </span>
          <div className="p-context" aria-label="Hesap bağlamı">
            <span className="ctx-user">{user.username}</span>
            <span className="ctx-role">{user.roles.join(", ")}</span>
            <span className="role-hint">{roleHint}</span>
          </div>
          <button
            type="button" className="p-notif" onClick={() => go("mesajlar")}
            aria-label={unread ? `Bildirimler, ${unread} okunmamış` : "Bildirimler, okunmamış yok"}
            aria-current={tab === "mesajlar" ? "page" : undefined}
          >
            Bildirimler
            <span className="p-notif-badge" hidden={unread === 0} aria-hidden>{unread > 99 ? "99+" : unread}</span>
          </button>
          <a className="p-btn ghost-dark" href="/" style={{ textDecoration: "none" }}>Vitrin</a>
          <button type="button" className="p-btn ghost-dark" onClick={() => void onLogout()}>Çıkış</button>
        </div>
      </header>

      <div className="p-shell">
        <aside className="p-sidebar">
          <nav ref={navRef} aria-label="Panel bölümleri" onKeyDown={onNavKey}>
            {NAV_GROUPS.map((g) => {
              const items = visibleInGroup(g.items);
              if (!items.length) return null;
              return (
                <div className="p-navgroup" key={g.label}>
                  <p className="p-navlabel" id={`nav-${g.label}`}>{g.label}</p>
                  <ul className="p-navlist" aria-labelledby={`nav-${g.label}`}>
                    {items.map(([k, l]) => (
                      <li key={k}>
                        <button
                          type="button" data-nav-item className={`p-navitem${tab === k ? " on" : ""}`}
                          aria-current={tab === k ? "page" : undefined}
                          onClick={() => go(k)}
                        >
                          {l}
                          {k === "mesajlar" && unread > 0 ? <span className="nav-count" aria-label={`${unread} okunmamış`}>{unread > 99 ? "99+" : unread}</span> : null}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </nav>
        </aside>

        <div className="p-content">
          <main className="p-main" id="panel-main" tabIndex={-1}>
            {!allVisible.includes(tab) && <TabGuard setTab={setTab} />}
            <Banner msg={banner?.msg ?? null} kind={banner?.kind} />
            <PageHeader
              title={meta.title}
              desc={meta.desc}
              actions={tab === "genel" ? (
                <button type="button" className="p-btn primary" onClick={() => go("olustur")}>İlan oluştur</button>
              ) : tab === "kesfet" ? (
                <button type="button" className="p-btn primary" onClick={() => go("olustur")}>İlan oluştur</button>
              ) : tab === "mesajlar" && unread > 0 ? (
                <span className="p-muted" role="status">{unread} okunmamış bildirim</span>
              ) : undefined}
            />

            {admin && (
              <div className="p-live" aria-label="Canlı sistem durumu">
                <div className="p-live-cell"><b>{live.data ? live.data.health : "—"}</b><span>Sağlık</span></div>
                <div className="p-live-cell"><b>{m ? m.http.total : "—"}</b><span>HTTP isteği</span></div>
                <div className="p-live-cell"><b>{m ? `${m.jobs.by_status.running || 0} çalışıyor · ${m.jobs.by_status.queued || 0} kuyrukta` : "—"}</b><span>İşler</span></div>
                <div className={`p-live-cell${failedJobs ? " warn" : ""}`}><b>{m ? `${m.jobs.by_status.done || 0} tamam · ${failedJobs} başarısız` : "—"}</b><span>İş sonucu</span></div>
                <div className="p-live-cell"><b>{m ? `${m.model.calls} çağrı` : "—"}</b><span>Model</span></div>
                <div className="p-live-cell"><b>{live.updatedAt ? new Date(live.updatedAt).toLocaleTimeString("tr-TR") : "—"}</b><span>Son güncelleme · 4 sn</span></div>
              </div>
            )}
            {!admin && (
              <div className="p-live" aria-label="Sistem durumu">
                <div className="p-live-cell"><b>{user.roles.join(", ")}</b><span>Rolünüz</span></div>
                <div className="p-live-cell"><b>İzleme admin yetkisi ister</b><span>Metrikler yalnızca admin</span></div>
              </div>
            )}

            {tab === "genel" && <Overview user={user} notify={notify} go={(t) => setTab(t as Tab)} />}
            {(tab === "kesfet" || tab === "olustur" || tab === "ilanlarim" || tab === "tekliflerim" || tab === "mesajlar") && (
              <Marketplace key={tab} user={user} initial={tab} notify={notify} go={(t) => setTab(t as Tab)} />
            )}
            {tab === "talepler" && <InquiriesView user={user} notify={notify} />}
            {tab === "katalog" && <CatalogView user={user} notify={notify} />}
            {tab === "fiyat" && <PricingView user={user} notify={notify} />}
            {tab === "izleme" && admin && <ObserveView live={live.data} notify={notify} />}
            {tab === "denetim" && admin && <AuditView entries={auditFull.length ? auditFull : live.data?.audit ?? []} refresh={() => { void loadAuditFull(); void live.refresh(); }} notify={notify} />}
          </main>
        </div>
      </div>
    </div>
  );
}

/** Yetkisiz sekmede kalınırsa (rol değişimi) genel bakışa düşürür. */
function TabGuard({ setTab }: { setTab: (t: Tab) => void }) {
  useEffect(() => { setTab("genel"); }, [setTab]);
  return null;
}
