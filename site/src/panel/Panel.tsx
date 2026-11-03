import { useCallback, useEffect, useRef, useState } from "react";
import { api, getToken, isAdmin, mpApi, setToken, type User } from "./api";
import { useLive } from "./views/Observe";
import { AuditView, ObserveView } from "./views/Observe";
import { CatalogView, PricingView } from "./views/Catalog";
import { InquiriesView } from "./views/Inquiries";
import { Marketplace, Overview } from "../marketplace/Marketplace";
import { Banner, PageHeader, Skeleton } from "./ui";
import "./panel.css";

type Tab = "overview" | "explore" | "create" | "my-listings" | "my-offers" | "messages" | "inquiries" | "catalog" | "pricing" | "observe" | "audit";

const NAV_GROUPS: { label: string; items: [Tab, string][] }[] = [
  { label: "General", items: [["overview", "Overview"]] },
  { label: "Marketplace", items: [["explore", "Explore"], ["create", "Create listing"], ["my-listings", "My listings"], ["my-offers", "My offers"], ["messages", "Messages"]] },
  { label: "Operations", items: [["inquiries", "Inquiries"]] },
  { label: "Administration", items: [["catalog", "Catalog"], ["pricing", "Pricing & Terms"], ["observe", "Observability"], ["audit", "Audit"]] },
];

const TAB_META: Record<Tab, { title: string; desc: string }> = {
  overview: { title: "Overview", desc: "Your published listings, pending work and recent activity at a glance." },
  explore: { title: "Explore listings", desc: "Published procurement requests and sales listings. Information that cannot be sourced is never completed for you." },
  create: { title: "Create listing", desc: "Describe what you need; nothing is published until you approve it at the review step." },
  "my-listings": { title: "My listings", desc: "Your listings: drafts, published, awarded and closed." },
  "my-offers": { title: "My offers", desc: "Offers you have made and their revisions. Competing offers are never shown to you." },
  messages: { title: "Messages", desc: "Notifications and conversations between listing owners and offerers." },
  inquiries: { title: "Inquiries", desc: "Scattered inquiries become quotes with sources you can show: upload, process, review, approve." },
  catalog: { title: "Catalog", desc: "Product codes, names and synonyms. Match quality comes from here." },
  pricing: { title: "Pricing & Terms", desc: "Versioned prices and terms; a quote is locked to the version in effect when it was created." },
  observe: { title: "Observability", desc: "System health, the job queue and model usage — admin only." },
  audit: { title: "Audit", desc: "Records are only appended, never deleted. Who did what is tracked here." },
};

export function Panel() {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);
  const [tab, setTab] = useState<Tab>("overview");
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
  useEffect(() => { if (tab === "audit" && admin) void loadAuditFull(); }, [tab, admin, loadAuditFull]);

  useEffect(() => {
    (async () => {
      if (!getToken()) { setBooting(false); return; }
      try { setUser(await api.me()); } catch { setToken(null); }
      setBooting(false);
    })();
  }, []);

  /* Unread notification count — top bar indicator */
  useEffect(() => {
    if (!user) { setUnread(0); return; }
    let alive = true;
    const load = async () => {
      try {
        const r = await mpApi.notifications();
        if (alive) setUnread(r.notifications.filter((n) => !n.read).length);
      } catch { /* the indicator silently keeps its last value */ }
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
    } catch (err) { notify(`Sign-in failed: ${(err as Error).message}`); }
  }
  async function onLogout() {
    try { await api.revoke(); } catch { /* ignore */ }
    setToken(null); setUser(null); setBanner(null); setTab("overview");
  }

  if (booting) {
    return (
      <div className="panel-root">
        <div className="p-main" aria-busy="true">
          <Skeleton lines={4} label="Loading panel" />
          <p className="p-muted" role="status">Loading…</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="panel-root">
        <header className="p-topbar">
          <a className="p-logo" href="/" aria-label="Linevora home"><i aria-hidden /> <span className="brand">Linevora</span> <small>Quote Panel</small></a>
          <a className="p-btn ghost-dark" href="/" style={{ textDecoration: "none" }}>Showcase</a>
        </header>
        <div className="p-main">
          <Banner msg={banner?.msg ?? null} kind={banner?.kind} />
          <div className="p-login">
            <p className="p-eyebrow">Panel sign-in</p>
            <h2>Welcome <em>back.</em></h2>
            <p className="p-muted">Turn scattered inquiries (PDF, email) into quotes with sources you can show: upload → process → review the suggestions → build the quote → approve.</p>
            <form className="p-stack" style={{ marginTop: 16 }} onSubmit={onLogin}>
              <label htmlFor="p-user">Username</label>
              <input id="p-user" placeholder="Username" autoComplete="username" required aria-label="Username" />
              <label htmlFor="p-pass">Password</label>
              <input id="p-pass" type="password" placeholder="Password" autoComplete="current-password" required aria-label="Password" />
              <button className="p-btn primary" type="submit">Sign in</button>
            </form>
            <p className="p-muted" style={{ marginTop: 12 }}>Development: <code>admin / admin123</code> · Roles: admin, specialist, viewer</p>
          </div>
        </div>
      </div>
    );
  }

  const roleHint = user.roles.includes("admin") ? "Pricing, products and approval authority are yours"
    : user.roles.includes("specialist") ? "You prepare inquiries and quotes" : "Read-only view";
  const visibleInGroup = (items: [Tab, string][]) =>
    items.filter(([k]) => (k === "observe" || k === "audit" ? admin : true));
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
      <a className="p-skip" href="#panel-main">Skip to content</a>
      <header className="p-topbar">
        <a className="p-logo" href="/panel" aria-label="Linevora panel home"><i aria-hidden /> <span className="brand">Linevora</span> <small>Quote Panel · Traceable</small></a>
        <div className="p-topbar-right">
          <span className="p-live-state">
            <span className={`live-dot${live.data || !admin ? "" : " off"}`} aria-hidden />
            <span role="status">{admin ? (live.data ? "Live" : "Connecting") : "Signed in"}</span>
          </span>
          <div className="p-context" aria-label="Account context">
            <span className="ctx-user">{user.username}</span>
            <span className="ctx-role">{user.roles.join(", ")}</span>
            <span className="role-hint">{roleHint}</span>
          </div>
          <button
            type="button" className="p-notif" onClick={() => go("messages")}
            aria-label={unread ? `Notifications, ${unread} unread` : "Notifications, none unread"}
            aria-current={tab === "messages" ? "page" : undefined}
          >
            Notifications
            <span className="p-notif-badge" hidden={unread === 0} aria-hidden>{unread > 99 ? "99+" : unread}</span>
          </button>
          <a className="p-btn ghost-dark" href="/" style={{ textDecoration: "none" }}>Showcase</a>
          <button type="button" className="p-btn ghost-dark" onClick={() => void onLogout()}>Sign out</button>
        </div>
      </header>

      <div className="p-shell">
        <aside className="p-sidebar">
          <nav ref={navRef} aria-label="Panel sections" onKeyDown={onNavKey}>
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
                          {k === "messages" && unread > 0 ? <span className="nav-count" aria-label={`${unread} unread`}>{unread > 99 ? "99+" : unread}</span> : null}
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
              actions={tab === "overview" ? (
                <button type="button" className="p-btn primary" onClick={() => go("create")}>Create listing</button>
              ) : tab === "explore" ? (
                <button type="button" className="p-btn primary" onClick={() => go("create")}>Create listing</button>
              ) : tab === "messages" && unread > 0 ? (
                <span className="p-muted" role="status">{unread} unread notification{unread === 1 ? "" : "s"}</span>
              ) : undefined}
            />

            {admin && (
              <div className="p-live" aria-label="Live system status">
                <div className="p-live-cell"><b>{live.data ? live.data.health : "—"}</b><span>Health</span></div>
                <div className="p-live-cell"><b>{m ? m.http.total : "—"}</b><span>HTTP requests</span></div>
                <div className="p-live-cell"><b>{m ? `${m.jobs.by_status.running || 0} running · ${m.jobs.by_status.queued || 0} queued` : "—"}</b><span>Jobs</span></div>
                <div className={`p-live-cell${failedJobs ? " warn" : ""}`}><b>{m ? `${m.jobs.by_status.done || 0} done · ${failedJobs} failed` : "—"}</b><span>Job outcome</span></div>
                <div className="p-live-cell"><b>{m ? `${m.model.calls} calls` : "—"}</b><span>Model</span></div>
                <div className="p-live-cell"><b>{live.updatedAt ? new Date(live.updatedAt).toLocaleTimeString("en-US") : "—"}</b><span>Last updated · 4s</span></div>
              </div>
            )}
            {!admin && (
              <div className="p-live" aria-label="System status">
                <div className="p-live-cell"><b>{user.roles.join(", ")}</b><span>Your role</span></div>
                <div className="p-live-cell"><b>Observability requires admin</b><span>Metrics are admin only</span></div>
              </div>
            )}

            {tab === "overview" && <Overview user={user} notify={notify} go={(t) => setTab(t as Tab)} />}
            {(tab === "explore" || tab === "create" || tab === "my-listings" || tab === "my-offers" || tab === "messages") && (
              <Marketplace key={tab} user={user} initial={tab} notify={notify} go={(t) => setTab(t as Tab)} />
            )}
            {tab === "inquiries" && <InquiriesView user={user} notify={notify} />}
            {tab === "catalog" && <CatalogView user={user} notify={notify} />}
            {tab === "pricing" && <PricingView user={user} notify={notify} />}
            {tab === "observe" && admin && <ObserveView live={live.data} notify={notify} />}
            {tab === "audit" && admin && <AuditView entries={auditFull.length ? auditFull : live.data?.audit ?? []} refresh={() => { void loadAuditFull(); void live.refresh(); }} notify={notify} />}
          </main>
        </div>
      </div>
    </div>
  );
}

/** If the user stays on an unauthorized tab (role change), fall back to the overview. */
function TabGuard({ setTab }: { setTab: (t: Tab) => void }) {
  useEffect(() => { setTab("overview"); }, [setTab]);
  return null;
}
