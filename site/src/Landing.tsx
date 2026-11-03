import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { startViewTracking, view } from "./scene/view";
import { PANEL_URL } from "./tokens";
import { Demo } from "./components/Demo";

const Scene = lazy(() => import("./scene/Scene").then((m) => ({ default: m.Scene })));

const STEPS = [
  ["Intake", "A file or message arrives; the original is stored unchanged and an inquiry and version are opened."],
  ["Extraction", "Requirements are extracted. Each one points to the section it came from; an extraction without a pointer never enters the pipeline."],
  ["Matching", "Even requests written with different terminology are linked to catalog candidates with a score and a rationale."],
  ["Approval", "The team reviews, corrects and approves. Every decision is written to the audit log."],
  ["Quote", "A draft is produced from the active price and terms version; the document is issued only after approval."],
] as const;

const RULES = [
  ["No suggestion is shown without a source.", "Every suggestion links back to the document section it relies on, in one click."],
  ["No quote goes out without approval.", "This rule is enforced in the data layer, not just the interface."],
  ["Only versioned prices and terms.", "Older quotes stay bound to the version they were created with."],
] as const;

const TRUST = [
  ["Source references", "Every requirement and quote line points to the document section it came from. Information without a pointer never enters the pipeline."],
  ["Audit trail", "Who changed what and when is kept in an append-only log. Records are never deleted and history is never rewritten."],
  ["Versioned pricing", "A quote is locked to the price and terms version in effect when it was created. Later changes do not affect it."],
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
          <a href="#process">Process</a>
          <a href="#demo">Demo</a>
          <a href="#trust">Trust</a>
          <a href="#proof">Proof</a>
        </nav>
        <a className="btn sm" href={PANEL_URL}>Open the panel</a>
      </header>

      <main id="top">
        <section className="hero" data-stage="0">
          <div className="wrap">
            <p className="eyebrow rv">From inquiry to quote · with sources you can show</p>
            <h1 className="rv d1">A scattered inquiry, <em>an auditable quote.</em></h1>
            <p className="lede rv d2">
              Linevora reads the inquiry, matches it against the catalog and puts the quote through team approval. Information that cannot be sourced is never suggested; a quote that is not approved is never sent.
            </p>
            <div className="cta rv d3">
              <a className="btn" href={PANEL_URL}>Go to the panel</a>
              <a className="btn ghost" href="#process">See the process</a>
            </div>
            <p className="hero-note rv d3">Source references · Audit trail · Versioned pricing — verifiable at every step.</p>
          </div>
          <div className="scroll-hint" aria-hidden>scroll ↓</div>
        </section>

        <section id="process" className="sec" data-stage="1">
          <div className="wrap">
            <p className="eyebrow rv">Process</p>
            <h2 className="rv d1">Five steps, <em>one line.</em></h2>
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
            <p className="eyebrow rv">Live flow</p>
            <h2 className="rv d1">From one email <em>to an approved quote.</em></h2>
            <div className="rv d2"><Demo /></div>
          </div>
        </section>

        <section id="rules" className="sec" data-stage="2">
          <div className="wrap">
            <p className="eyebrow rv">Non-negotiable rules</p>
            <h2 className="rv d1">Being fast <em>is not being loose.</em></h2>
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

        <section id="trust" className="sec" data-stage="2">
          <div className="wrap">
            <p className="eyebrow rv">Trust evidence</p>
            <h2 className="rv d1">Every claim, <em>tied to its proof.</em></h2>
            <div className="rules">
              {TRUST.map(([t, d], i) => (
                <article key={t} className="rv" style={{ transitionDelay: `${i * 90}ms` }}>
                  <h3>{t}</h3>
                  <p>{d}</p>
                </article>
              ))}
            </div>
            <div className="cta rv" style={{ marginTop: 28 }}>
              <a className="btn" href={PANEL_URL}>Verify it in the panel</a>
            </div>
          </div>
        </section>

        <section id="proof" className="sec" data-stage="2">
          <div className="wrap">
            <p className="eyebrow rv">Proof</p>
            <h2 className="rv d1">What is not measured <em>is not shipped.</em></h2>
            <div className="bento">
              <div className="cell rv">
                <h3>Eval gate</h3>
                <p>Matching changes are measured on a fixed historical set; below the threshold the exit code is 1.</p>
                <div className="gate"><span style={{ width: "86%" }} /><i style={{ left: "80%" }} /></div>
                <small>score 0.86 · threshold 0.80</small>
              </div>
              <div className="cell rv d1">
                <h3>Version diff</h3>
                <p>When the customer updates a request, what changed is visible line by line.</p>
                <pre className="diff"><s>− PN25 · 80 pcs</s>{"\n"}<ins>+ PN40 · 120 pcs</ins></pre>
              </div>
              <div className="cell rv d2">
                <h3>Audit log</h3>
                <p>Version and audit records are never deleted, only appended.</p>
                <ul className="log">
                  <li><code>14:02</code> inquiry opened</li>
                  <li><code>14:09</code> match corrected</li>
                  <li><code>14:31</code> quote approved</li>
                </ul>
              </div>
              <div className="cell wide rv d1">
                <h3>A whole with clear boundaries</h3>
                <p>A single deployment unit with sharp internal module boundaries; the language model sits behind a replaceable abstraction.</p>
                <div className="chips">
                  {["API layer", "Processing pipeline", "Model abstraction", "Semantic index", "Catalog + pricing", "Quote engine", "Audit"].map((c) => <span key={c}>{c}</span>)}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="sec final" data-stage="3">
          <div className="wrap">
            <h2 className="rv">Close <em>the line.</em></h2>
            <p className="lede rv d1">Bring an inquiry in, check it against its source, and send it with approval.</p>
            <div className="cta rv d2">
              <a className="btn" href={PANEL_URL}>Go to the panel</a>
              <a className="btn ghost" href="#trust">Trust evidence</a>
            </div>
          </div>
        </section>
      </main>

      <footer className="foot">
        <span>© Linevora</span>
        <span>From inquiry to quote, with sources you can show.</span>
      </footer>
    </>
  );
}
