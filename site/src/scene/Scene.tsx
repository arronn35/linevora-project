import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { Line2 } from "three/examples/jsm/lines/Line2.js";
import { LineGeometry } from "three/examples/jsm/lines/LineGeometry.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";
import { view } from "./view";
import { COUNT, PATH_POINTS, buildFormations, buildPaths, paperTexture } from "./formations";

const ease = (x: number) => x * x * (3 - 2 * x);
const SIGNAL = new THREE.Color("#ff5a1f");

function Documents() {
  const mesh = useRef<THREE.InstancedMesh>(null!);
  const formations = useMemo(buildFormations, []);
  const map = useMemo(paperTexture, []);
  // each page starts moving a little later than its neighbour — reads as a cascade
  const delay = useMemo(() => Array.from({ length: COUNT }, (_, i) => ((i * 7919) % COUNT) / COUNT), []);
  const tmp = useMemo(
    () => ({ p: new THREE.Vector3(), q: new THREE.Quaternion(), m: new THREE.Matrix4(), s: new THREE.Vector3(1, 1, 1) }),
    [],
  );

  useLayoutEffect(() => {
    const white = new THREE.Color("#ffffff");
    for (let i = 0; i < COUNT; i++) mesh.current.setColorAt(i, i === COUNT - 1 ? SIGNAL.clone().lerp(white, 0.55) : white);
    mesh.current.instanceColor!.needsUpdate = true;
  }, []);

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    const f = THREE.MathUtils.clamp(view.stage, 0, formations.length - 1.0001);
    const k = Math.floor(f);
    const u = f - k;
    const A = formations[k];
    const B = formations[k + 1];
    const drift = view.reduced ? 0 : 1;
    for (let i = 0; i < COUNT; i++) {
      const ui = ease(THREE.MathUtils.clamp((u - delay[i] * 0.45) / 0.55, 0, 1));
      tmp.p.lerpVectors(A[i].p, B[i].p, ui);
      tmp.q.slerpQuaternions(A[i].q, B[i].q, ui);
      tmp.p.y += Math.sin(t * 0.6 + i) * 0.05 * drift;
      tmp.m.compose(tmp.p, tmp.q, tmp.s);
      mesh.current.setMatrixAt(i, tmp.m);
    }
    mesh.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, COUNT]} frustumCulled={false}>
      <planeGeometry args={[1, 1.41]} />
      <meshStandardMaterial map={map} side={THREE.DoubleSide} roughness={0.92} metalness={0} />
    </instancedMesh>
  );
}

function BrandLine() {
  const paths = useMemo(buildPaths, []);
  const size = useThree((s) => s.size);
  const pulse = useRef<THREE.Group>(null!);

  const { line, geo, mat } = useMemo(() => {
    const geo = new LineGeometry();
    geo.setPositions(paths[0]);
    const mat = new LineMaterial({ color: SIGNAL.getHex(), linewidth: 2.4, transparent: true, depthWrite: false });
    return { line: new Line2(geo, mat), geo, mat };
  }, [paths]);

  useEffect(() => {
    mat.resolution.set(size.width, size.height);
  }, [mat, size]);
  useEffect(() => () => (geo.dispose(), mat.dispose()), [geo, mat]);

  const buf = useMemo(() => new Float32Array(PATH_POINTS * 3), []);

  useFrame(({ clock }) => {
    const f = THREE.MathUtils.clamp(view.stage, 0, paths.length - 1.0001);
    const k = Math.floor(f);
    const u = ease(f - k);
    const a = paths[k];
    const b = paths[k + 1];
    for (let i = 0; i < buf.length; i++) buf[i] = a[i] + (b[i] - a[i]) * u;
    geo.setPositions(buf);

    // a signal travelling along the line
    const s = view.reduced ? 0.5 : (clock.elapsedTime * 0.09) % 1;
    const idx = Math.min(PATH_POINTS - 1, Math.floor(s * (PATH_POINTS - 1))) * 3;
    pulse.current.position.set(buf[idx], buf[idx + 1], buf[idx + 2]);
  });

  return (
    <>
      <primitive object={line} />
      <group ref={pulse}>
        <mesh>
          <sphereGeometry args={[0.075, 20, 20]} />
          <meshBasicMaterial color="#ff5a1f" />
        </mesh>
        <mesh>
          <sphereGeometry args={[0.2, 20, 20]} />
          <meshBasicMaterial color="#ff5a1f" transparent opacity={0.18} depthWrite={false} />
        </mesh>
      </group>
    </>
  );
}

function Rig() {
  const group = useRef<THREE.Group>(null!);
  const { viewport, camera } = useThree();

  useFrame(({ clock }, dt) => {
    const wide = viewport.aspect > 1.15;
    const tx = wide ? 3.1 : 0;
    const ty = wide ? 0 : 1.7;
    const sc = wide ? 0.88 : 0.56;
    const g = group.current;
    const k = 1 - Math.exp(-dt * 4);
    g.position.x += (tx - g.position.x) * k;
    g.position.y += (ty - g.position.y) * k;
    g.scale.setScalar(g.scale.x + (sc - g.scale.x) * k);

    const spin = view.reduced ? 0 : Math.sin(clock.elapsedTime * 0.15) * 0.12;
    g.rotation.y += (view.mx * 0.22 + spin - g.rotation.y) * k;
    g.rotation.x += (view.my * 0.1 - g.rotation.x) * k;
    camera.position.y += ((-view.progress * 0.6) - camera.position.y) * k;
    camera.lookAt(0, 0, 0);
  });

  return (
    <group ref={group}>
      <Documents />
      <BrandLine />
    </group>
  );
}

export function Scene() {
  return (
    <Canvas
      flat
      dpr={[1, 1.75]}
      camera={{ position: [0, 0, 11], fov: 35 }}
      gl={{ alpha: true, antialias: true, powerPreference: "high-performance" }}
      style={{ position: "fixed", inset: 0, zIndex: 0 }}
      aria-hidden
    >
      <ambientLight intensity={1.15} />
      <directionalLight position={[3, 5, 6]} intensity={1.6} />
      <directionalLight position={[-5, -2, 3]} intensity={0.5} color="#ffd9c7" />
      <Rig />
    </Canvas>
  );
}
