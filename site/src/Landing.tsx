import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { startViewTracking, view } from "./scene/view";
import { PANEL_URL } from "./tokens";
import { Demo } from "./components/Demo";

const Scene = lazy(() => import("./scene/Scene").then((m) => ({ default: m.Scene })));

const STEPS = [
  ["Alım", "Dosya ya da metin gelir; özgün hali değişmez biçimde saklanır, talep ve sürüm açılır."],
  ["Çıkarım", "Gereksinimler çıkarılır. Her biri geldiği bölüme işaret eder; işaretsiz çıkarım hatta girmez."],
  ["Eşleşme", "Farklı terminoyla yazılmış talepler bile katalog adaylarına skor ve gerekçeyle bağlanır."],
  ["Onay", "Ekip inceler, düzeltir, onaylar. Her karar denetim kaydına yazılır."],
  ["Teklif", "Yürürlükteki fiyat ve şart sürümüyle taslak çıkar; onaydan sonra belge alınır."],
] as const;

const RULES = [
  ["Kaynağı olmayan öneri gösterilmez.", "Her öneri, dayandığı belge bölümüne tek tıkla bağlanır."],
  ["Onay olmadan teklif çıkmaz.", "Bu kural arayüzde değil, veri katmanında denetlenir."],
  ["Yalnızca sürümlü fiyat ve şart.", "Eski teklifler, üretildikleri sürüme bağlı kalır."],
] as const;

const TRUST = [
  ["Kaynak gösterimi", "Her gereksinim ve teklif kalemi, geldiği belge bölümüne işaret eder. İşaretsiz bilgi hatta girmez."],
  ["Denetim izi", "Kim, neyi, ne zaman değiştirdi eklemeli kayıtta tutulur. Kayıt silinmez, geçmiş yeniden yazılmaz."],
  ["Sürümlü fiyat", "Teklif, kurulduğu anın fiyat ve şart sürümüne kilitlenir. Sonraki değişiklik eski teklifi etkilemez."],
] as const;

function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll(".rv");
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && (e.target.classList.add("in"), io.unobserve(e.target))),
      { threshold: 0.15 },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
}

function Rail() {
  const fill = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      if (fill.current) fill.current.style.transform = `scaleY(${view.progress})`;
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(raf);
  }, []);
  return (
    <div className="rail" aria-hidden>
      <div className="rail-fill" ref={fill} />
    </div>
  );
}

export function Landing() {
  const [ready, setReady] = useState(false);
  useReveal();
  useEffect(() => {
    const stop = startViewTracking();
    setReady(true);
    return stop;
  }, []);

  return (
    <>
      <div className="grain" aria-hidden />
      <Suspense fallback={null}>{ready && <Scene />}</Suspense>
      <Rail />

      <header className="nav">
        <a className="logo" href="#top" aria-label="Linevora">
          <i /> Linevora
        </a>
        <nav>
          <a href="#akis">Süreç</a>
          <a href="#demo">Demo</a>
          <a href="#guven">Güven</a>
          <a href="#kanit">Kanıt</a>
        </nav>
        <a className="btn sm" href={PANEL_URL}>Paneli aç</a>
      </header>

      <main id="top">
        <section className="hero" data-stage="0">
          <div className="wrap">
            <p className="eyebrow rv">Talepten teklife · kaynağı gösterilebilir</p>
            <h1 className="rv d1">Dağınık talep, <em>denetlenebilir teklif.</em></h1>
            <p className="lede rv d2">
              Linevora talebi okur, katalogla eşleştirir, teklifi ekibin onayından geçirir. Kaynağı gösterilemeyen bilgi önerilmez; onaylanmayan teklif gönderilmez.
            </p>
            <div className="cta rv d3">
              <a className="btn" href={PANEL_URL}>Panele gir</a>
              <a className="btn ghost" href="#akis">Süreci gör</a>
            </div>
            <p className="hero-note rv d3">Kaynak gösterimi · Denetim izi · Sürümlü fiyat — her adımda doğrulanabilir.</p>
          </div>
          <div className="scroll-hint" aria-hidden>kaydır ↓</div>
        </section>

        <section id="akis" className="sec" data-stage="1">
          <div className="wrap">
            <p className="eyebrow rv">Süreç</p>
            <h2 className="rv d1">Beş adım, <em>tek çizgi.</em></h2>
            <ol className="steps">
              {STEPS.map(([t, d], i) => (
                <li key={t} className="rv" style={{ transitionDelay: `${i * 70}ms` }}>
                  <span className="n">0{i + 1}</span>
                  <div>
                    <h3>{t}</h3>
                    <p>{d}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="demo" className="sec" data-stage="1">
          <div className="wrap wide">
            <p className="eyebrow rv">Canlı akış</p>
            <h2 className="rv d1">Bir e-postadan <em>onaylı teklife.</em></h2>
            <div className="rv d2"><Demo /></div>
          </div>
        </section>

        <section id="kurallar" className="sec" data-stage="2">
          <div className="wrap">
            <p className="eyebrow rv">Değişmez kurallar</p>
            <h2 className="rv d1">Hızlı olmak, <em>serbest olmak değil.</em></h2>
            <div className="rules">
              {RULES.map(([t, d], i) => (
                <article key={t} className="rv" style={{ transitionDelay: `${i * 90}ms` }}>
                  <b>{i + 1}</b>
                  <h3>{t}</h3>
                  <p>{d}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="guven" className="sec" data-stage="2">
          <div className="wrap">
            <p className="eyebrow rv">Güven kanıtları</p>
            <h2 className="rv d1">Her iddia, <em>kanıtına bağlı.</em></h2>
            <div className="rules">
              {TRUST.map(([t, d], i) => (
                <article key={t} className="rv" style={{ transitionDelay: `${i * 90}ms` }}>
                  <h3>{t}</h3>
                  <p>{d}</p>
                </article>
              ))}
            </div>
            <div className="cta rv" style={{ marginTop: 28 }}>
              <a className="btn" href={PANEL_URL}>Panelde doğrulayın</a>
            </div>
          </div>
        </section>

        <section id="kanit" className="sec" data-stage="2">
          <div className="wrap">
            <p className="eyebrow rv">Kanıt</p>
            <h2 className="rv d1">Ölçülmeyen şey <em>yayımlanmaz.</em></h2>
            <div className="bento">
              <div className="cell rv">
                <h3>Eval kapısı</h3>
                <p>Eşleştirme değişiklikleri sabit tarihsel sette ölçülür; eşik altında çıkış kodu 1 olur.</p>
                <div className="gate"><span style={{ width: "86%" }} /><i style={{ left: "80%" }} /></div>
                <small>skor 0.86 · eşik 0.80</small>
              </div>
              <div className="cell rv d1">
                <h3>Sürüm farkı</h3>
                <p>Müşteri talebi güncellediğinde neyin değiştiği satır satır görünür.</p>
                <pre className="diff"><s>− PN25 · 80 adet</s>{"\n"}<ins>+ PN40 · 120 adet</ins></pre>
              </div>
              <div className="cell rv d2">
                <h3>Denetim kaydı</h3>
                <p>Sürüm ve denetim kayıtları silinmez, yalnızca eklenir.</p>
                <ul className="log">
                  <li><code>14:02</code> talep açıldı</li>
                  <li><code>14:09</code> eşleşme düzeltildi</li>
                  <li><code>14:31</code> teklif onaylandı</li>
                </ul>
              </div>
              <div className="cell wide rv d1">
                <h3>Sınırları net bir bütün</h3>
                <p>Tek dağıtım birimi, keskin iç modül sınırları; dil modeli değiştirilebilir bir soyutlamanın arkasında.</p>
                <div className="chips">
                  {["API katmanı", "İşleme hattı", "Model soyutlaması", "Anlamsal dizin", "Katalog + fiyat", "Teklif motoru", "Denetim"].map((c) => <span key={c}>{c}</span>)}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="sec final" data-stage="3">
          <div className="wrap">
            <h2 className="rv">Çizgiyi <em>kapatın.</em></h2>
            <p className="lede rv d1">Bir talebi içeri alın, kaynağıyla kontrol edin, onayla gönderin.</p>
            <div className="cta rv d2">
              <a className="btn" href={PANEL_URL}>Panele gir</a>
              <a className="btn ghost" href="#guven">Güven kanıtları</a>
            </div>
          </div>
        </section>
      </main>

      <footer className="foot">
        <span>© Linevora</span>
        <span>Talepten teklife, kaynağı gösterilebilir.</span>
      </footer>
    </>
  );
}
