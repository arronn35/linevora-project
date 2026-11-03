import { useEffect, useState } from "react";
import { api, isAdmin, money, type Price, type Product, type Terms, type User } from "../api";
import { Hint, Pill } from "../ui";

export function CatalogView({ user, notify }: { user: User; notify: (m: string, k?: "ok" | "err") => void }) {
  const admin = isAdmin(user);
  const [products, setProducts] = useState<Product[]>([]);
  const [form, setForm] = useState({ code: "", names: "", unit: "pcs" });
  async function load() { setProducts((await api.products()).products); }
  useEffect(() => { void load().catch((e) => notify((e as Error).message)); }, [notify]);
  return (
    <div className="p-card">
      <h3>Products</h3>
      <Hint>Synonyms matter a lot: if the customer calls the product by another name, the match comes from here. You write the code once; names are comma-separated.</Hint>
      <table><thead><tr><th>Code</th><th>Names</th><th>Features</th><th>Unit</th></tr></thead><tbody>
        {products.map((p) => (
          <tr key={p.id}><td><b>{p.code}</b></td>
            <td>{p.names.join(", ")}{p.synonyms.length ? <><br /><span className="p-muted">syn: {p.synonyms.join(", ")}</span></> : null}</td>
            <td>{Object.entries(p.features || {}).map(([k, v]) => `${k}=${String(v)}`).join(", ")}</td><td>{p.unit}</td></tr>
        ))}
      </tbody></table>
      {admin && (
        <>
          <h4>New Product</h4>
          <form className="p-inline" onSubmit={async (e) => {
            e.preventDefault();
            try { await api.createProduct(form.code.trim(), form.names.split(",").map((s) => s.trim()).filter(Boolean), form.unit.trim() || "pcs"); setForm({ code: "", names: "", unit: "pcs" }); await load(); notify("Product added.", "ok"); }
            catch (err) { notify((err as Error).message); }
          }}>
            <input placeholder="Code" required value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
            <input placeholder="Names (comma-separated)" required style={{ minWidth: 220 }} value={form.names} onChange={(e) => setForm({ ...form, names: e.target.value })} />
            <input placeholder="Unit" style={{ width: 90 }} value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} />
            <button className="p-btn primary" type="submit">Add</button>
          </form>
        </>
      )}
    </div>
  );
}

export function PricingView({ user, notify }: { user: User; notify: (m: string, k?: "ok" | "err") => void }) {
  const admin = isAdmin(user);
  const [products, setProducts] = useState<Product[]>([]);
  const [prices, setPrices] = useState<Record<string, Price[]>>({});
  const [terms, setTerms] = useState<Terms[]>([]);
  const [nt, setNt] = useState({ name: "", text: "" });
  async function loadAll() {
    const ps = (await api.products()).products; setProducts(ps);
    const map: Record<string, Price[]> = {};
    for (const p of ps) map[p.id] = (await api.prices(p.id)).prices;
    setPrices(map); setTerms((await api.terms()).terms);
  }
  useEffect(() => { void loadAll().catch((e) => notify((e as Error).message)); }, [notify]);
  return (
    <>
      <div className="p-card">
        <h3>Prices</h3>
        <Hint>A new price is added as a draft; when you activate it, quotes use the new price. Older quotes keep their locked prices.</Hint>
        {products.map((p) => (
          <div key={p.id}>
            <h4>{p.code} — {p.names.join(", ")}</h4>
            {(prices[p.id] ?? []).length === 0 ? <p className="p-muted">No price.</p> : (
              <table><thead><tr><th>Price</th><th>Status</th><th /></tr></thead><tbody>
                {(prices[p.id] ?? []).map((v) => (
                  <tr key={v.id}><td>{money(v.price, v.currency)}</td><td><Pill t={v.status} /></td>
                    <td>{admin && v.status === "draft" && <button className="p-btn sm" onClick={async () => { try { await api.activatePrice(v.id); await loadAll(); } catch (e) { notify((e as Error).message); } }}>Activate</button>}</td></tr>
                ))}
              </tbody></table>
            )}
            {admin && (
              <form className="p-inline" style={{ marginTop: 6 }} onSubmit={async (e) => {
                e.preventDefault();
                const form = e.currentTarget;
                const price = Number(form.querySelector<HTMLInputElement>("[data-price]")?.value);
                const cur = form.querySelector<HTMLInputElement>("[data-cur]")?.value.trim() || "USD";
                try { await api.createPrice(p.id, price, cur); setPrices((m) => ({ ...m, [p.id]: [] })); await loadAll(); notify("Price draft added.", "ok"); }
                catch (err) { notify((err as Error).message); }
              }}>
                <input data-price placeholder="Price" type="number" min="0" step="any" required style={{ width: 130 }} aria-label={`Price — ${p.code}`} />
                <input data-cur placeholder="Currency" defaultValue="USD" style={{ width: 90 }} aria-label={`Currency — ${p.code}`} />
                <button className="p-btn sm" type="submit">Add draft</button>
              </form>
            )}
          </div>
        ))}
      </div>
      <div className="p-card">
        <h3>Terms</h3>
        <table><thead><tr><th>Name</th><th>Text</th><th>Status</th><th /></tr></thead><tbody>
          {terms.map((t) => (
            <tr key={t.id}><td><b>{t.name}</b></td><td>{t.text}</td><td><Pill t={t.status} /></td>
              <td>{admin && t.status === "draft" && <button className="p-btn sm" onClick={async () => { try { await api.activateTerms(t.id); await loadAll(); } catch (e) { notify((e as Error).message); } }}>Activate</button>}</td></tr>
          ))}
        </tbody></table>
        {admin && (
          <>
            <h4>New Terms</h4>
            <form className="p-inline" onSubmit={async (e) => {
              e.preventDefault();
              try { await api.createTerms(nt.name.trim(), nt.text.trim()); setNt({ name: "", text: "" }); await loadAll(); notify("Terms added.", "ok"); }
              catch (err) { notify((err as Error).message); }
            }}>
              <input placeholder="Name" required value={nt.name} onChange={(e) => setNt({ ...nt, name: e.target.value })} />
              <input placeholder="Text" required style={{ minWidth: 280 }} value={nt.text} onChange={(e) => setNt({ ...nt, text: e.target.value })} />
              <button className="p-btn primary" type="submit">Add</button>
            </form>
          </>
        )}
      </div>
    </>
  );
}
