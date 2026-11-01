// Scroll/pointer state shared between the DOM layer and the WebGL scene.
// Mutated outside React so the render loop never waits on a re-render.
export const view = {
  stage: 0, // continuous formation index: 0 scatter, 1 flow, 2 ring, 3 stack
  progress: 0, // 0..1 page scroll
  mx: 0,
  my: 0,
  reduced: false,
};

export function startViewTracking(): () => void {
  view.reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let anchors: { y: number; f: number }[] = [];
  const measure = () => {
    anchors = Array.from(document.querySelectorAll<HTMLElement>("[data-stage]")).map((el) => {
      const r = el.getBoundingClientRect();
      return { y: r.top + window.scrollY + r.height / 2, f: Number(el.dataset.stage) };
    });
  };

  const update = () => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    view.progress = max > 0 ? window.scrollY / max : 0;
    const y = window.scrollY + window.innerHeight * 0.5;
    if (!anchors.length) return;
    if (y <= anchors[0].y) return void (view.stage = anchors[0].f);
    for (let i = 0; i < anchors.length - 1; i++) {
      const a = anchors[i];
      const b = anchors[i + 1];
      if (y <= b.y) {
        view.stage = a.f + (b.f - a.f) * ((y - a.y) / (b.y - a.y));
        return;
      }
    }
    view.stage = anchors[anchors.length - 1].f;
  };

  const onMove = (e: PointerEvent) => {
    view.mx = (e.clientX / window.innerWidth) * 2 - 1;
    view.my = (e.clientY / window.innerHeight) * 2 - 1;
  };
  const onResize = () => {
    measure();
    update();
  };

  measure();
  update();
  const ro = new ResizeObserver(onResize);
  ro.observe(document.body);
  window.addEventListener("scroll", update, { passive: true });
  window.addEventListener("resize", onResize);
  window.addEventListener("pointermove", onMove, { passive: true });
  window.addEventListener("load", onResize);
  return () => {
    ro.disconnect();
    window.removeEventListener("scroll", update);
    window.removeEventListener("resize", onResize);
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("load", onResize);
  };
}
