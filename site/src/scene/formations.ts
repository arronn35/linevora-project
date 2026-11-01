import * as THREE from "three";

export const COUNT = 44;

// Deterministic PRNG so the scatter looks the same on every load.
function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export type Pose = { p: THREE.Vector3; q: THREE.Quaternion };

const pose = (pos: THREE.Vector3, euler: THREE.Euler, tilt?: THREE.Matrix4): Pose => {
  const m = new THREE.Matrix4().compose(
    pos,
    new THREE.Quaternion().setFromEuler(euler),
    new THREE.Vector3(1, 1, 1),
  );
  if (tilt) m.premultiply(tilt);
  const p = new THREE.Vector3();
  const q = new THREE.Quaternion();
  m.decompose(p, q, new THREE.Vector3());
  return { p, q };
};

export const flowCurve = (t: number) =>
  new THREE.Vector3(
    THREE.MathUtils.lerp(-3.1, 3.1, t),
    Math.sin(t * Math.PI * 1.6 - 0.4) * 1.25,
    Math.cos(t * Math.PI * 1.2) * 0.7,
  );

const ringPoint = (a: number, tilt: THREE.Matrix4) =>
  new THREE.Vector3(Math.cos(a) * 2.7, Math.sin(a * 2) * 0.22, Math.sin(a) * 2.7).applyMatrix4(tilt);

export function buildFormations(): Pose[][] {
  const r = rng(1912);
  const ringTilt = new THREE.Matrix4().makeRotationX(0.55);
  const stackTilt = new THREE.Matrix4().makeRotationX(0.95).premultiply(new THREE.Matrix4().makeRotationY(-0.35));

  const scatter: Pose[] = [];
  const flow: Pose[] = [];
  const ring: Pose[] = [];
  const stack: Pose[] = [];

  for (let i = 0; i < COUNT; i++) {
    const t = i / (COUNT - 1);

    scatter.push(
      pose(
        new THREE.Vector3((r() - 0.5) * 5.6, (r() - 0.5) * 5.6, (r() - 0.5) * 5),
        new THREE.Euler(r() * 6.28, r() * 6.28, r() * 6.28),
      ),
    );

    // pages standing along the line like frames on a film strip
    const c = flowCurve(t);
    const ahead = flowCurve(Math.min(1, t + 0.01));
    const yaw = 1.2 + Math.atan2(ahead.y - c.y, ahead.x - c.x) * 0.2;
    flow.push(pose(c, new THREE.Euler(0, yaw, Math.atan2(ahead.y - c.y, ahead.x - c.x) * 0.5)));

    const a = t * Math.PI * 2;
    ring.push(pose(ringPoint(a, ringTilt), new THREE.Euler(0, -a + Math.PI / 2, 0), ringTilt));

    stack.push(
      pose(
        new THREE.Vector3((r() - 0.5) * 0.07, i * 0.05 - 1.1, (r() - 0.5) * 0.07),
        new THREE.Euler(-Math.PI / 2, 0, (r() - 0.5) * 0.09),
        stackTilt,
      ),
    );
  }
  return [scatter, flow, ring, stack];
}

// Brand line: one path per formation, same point count so they can be blended.
export const PATH_POINTS = 160;

export function buildPaths(): Float32Array[] {
  const ringTilt = new THREE.Matrix4().makeRotationX(0.55);
  const sample = (fn: (t: number) => THREE.Vector3) => {
    const out = new Float32Array(PATH_POINTS * 3);
    for (let i = 0; i < PATH_POINTS; i++) fn(i / (PATH_POINTS - 1)).toArray(out, i * 3);
    return out;
  };
  const wide = sample((t) =>
    new THREE.Vector3(
      THREE.MathUtils.lerp(-4.4, 4.4, t),
      Math.sin(t * 6.0) * 0.55 + (t - 0.5) * 1.4,
      Math.sin(t * 3.4) * 1.2,
    ),
  );
  const flow = sample(flowCurve);
  const ring = sample((t) => ringPoint(t * Math.PI * 2 + 0.0001, ringTilt));
  const check = new THREE.CatmullRomCurve3(
    [
      new THREE.Vector3(-4.2, -1.9, 0.6),
      new THREE.Vector3(-1.6, -1.9, 0.9),
      new THREE.Vector3(-0.7, -2.5, 1.1),
      new THREE.Vector3(0.3, -0.9, 1.1),
      new THREE.Vector3(1.6, 0.9, 0.9),
      new THREE.Vector3(3.6, 2.3, 0.6),
    ],
    false,
    "centripetal",
  );
  const done = sample((t) => check.getPointAt(t));
  return [wide, flow, ring, done];
}

export function paperTexture(): THREE.CanvasTexture {
  const w = 320;
  const h = 452;
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const g = c.getContext("2d")!;
  const r = rng(77);

  g.fillStyle = "#f7f6f0";
  g.fillRect(0, 0, w, h);
  g.strokeStyle = "#d4d2c7";
  g.lineWidth = 2;
  g.strokeRect(1, 1, w - 2, h - 2);

  g.fillStyle = "#0e0f10";
  g.fillRect(24, 26, 72, 9);
  g.fillStyle = "#b9b7ab";
  g.fillRect(24, 44, 120, 5);
  g.fillRect(w - 78, 26, 54, 5);

  let y = 82;
  while (y < h - 150) {
    const width = 120 + r() * (w - 48 - 120);
    if (r() < 0.16) {
      g.fillStyle = "rgba(255,90,31,0.28)";
      g.fillRect(22, y - 3, width + 4, 12);
      g.fillStyle = "#ff5a1f";
      g.fillRect(22, y - 3, 3, 12);
    }
    g.fillStyle = "#8f8e86";
    g.fillRect(24, y, width, 5);
    y += 16 + (r() < 0.2 ? 12 : 0);
  }

  // spec table
  const ty = h - 128;
  g.strokeStyle = "#c9c7bb";
  g.lineWidth = 1.5;
  for (let row = 0; row < 4; row++) {
    g.strokeRect(24, ty + row * 24, w - 48, 24);
    g.fillStyle = "#a9a89e";
    g.fillRect(32, ty + row * 24 + 9, 54 + r() * 40, 5);
    g.fillRect(w - 92, ty + row * 24 + 9, 44, 5);
  }
  g.beginPath();
  g.moveTo(w / 2 - 20, ty);
  g.lineTo(w / 2 - 20, ty + 96);
  g.stroke();

  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  return tex;
}
