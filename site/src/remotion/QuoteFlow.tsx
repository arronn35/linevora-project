import { AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { T } from "../tokens";

export const FPS = 30;
export const DURATION = 360;
export const SCENES = [
  { from: 0, label: "Talep" },
  { from: 90, label: "Eşleşme" },
  { from: 180, label: "Onay" },
  { from: 270, label: "Teklif" },
] as const;

const useIn = (delay = 0, damping = 18) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config: { damping, stiffness: 120 } });
};

const Fade = ({ children }: { children: React.ReactNode }) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 8, 80, 90], [0, 1, 1, 0], { extrapolateRight: "clamp" });
  return <AbsoluteFill style={{ opacity: o, padding: 64 }}>{children}</AbsoluteFill>;
};

const Tag = ({ children, color = T.mute }: { children: React.ReactNode; color?: string }) => (
  <div style={{ fontFamily: T.mono, fontSize: 18, letterSpacing: 2, textTransform: "uppercase", color }}>{children}</div>
);

const REQS = [
  { text: "DN50 paslanmaz küresel vana", src: "§2.1" },
  { text: "PN40 basınç sınıfı", src: "§2.3" },
  { text: "ATEX onaylı, 120 adet", src: "§4.2" },
];

function Inquiry() {
  const frame = useCurrentFrame();
  const body = "Merhaba, tesisimiz için DN50 paslanmaz küresel vana, PN40 sınıfında ve ATEX onaylı olarak 120 adet gerekiyor. Teslim: 6 hafta.";
  const chars = Math.floor(interpolate(frame, [4, 52], [0, body.length], { extrapolateRight: "clamp" }));
  return (
    <Fade>
      <Tag>01 · Talep alındı</Tag>
      <div style={{ display: "flex", gap: 48, marginTop: 28 }}>
        <div style={{ flex: 1.2, background: T.paper, border: `2px solid ${T.rule}`, padding: 36, minHeight: 360 }}>
          <div style={{ fontFamily: T.mono, fontSize: 17, color: T.mute }}>RFQ-2291.eml · 14:02</div>
          <div style={{ fontFamily: T.sans, fontSize: 30, lineHeight: 1.5, color: T.ink, marginTop: 20 }}>
            {body.slice(0, chars)}
            <span style={{ opacity: frame % 16 < 8 ? 1 : 0, color: T.signal }}>▍</span>
          </div>
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16, paddingTop: 8 }}>
          {REQS.map((r, i) => {
            const s = useIn(36 + i * 12);
            return (
              <div
                key={r.text}
                style={{
                  opacity: s,
                  transform: `translateX(${(1 - s) * 40}px)`,
                  borderLeft: `5px solid ${T.signal}`,
                  background: "rgba(255,90,31,0.10)",
                  padding: "16px 20px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span style={{ fontFamily: T.sans, fontSize: 26, color: T.ink }}>{r.text}</span>
                <span style={{ fontFamily: T.mono, fontSize: 18, color: T.signal }}>{r.src}</span>
              </div>
            );
          })}
          <Tag>Her gereksinim kaynağına bağlı</Tag>
        </div>
      </div>
    </Fade>
  );
}

const MATCHES = [
  { name: "KV-50-SS316 / PN40", score: 0.94, note: "" },
  { name: "KV-50-SS304 / PN25", score: 0.71, note: "basınç uyumsuz" },
  { name: "KV-50-ATEX-Z1", score: 0.88, note: "tolerans eksik" },
];

function Matching() {
  return (
    <Fade>
      <Tag>02 · Katalogla eşleşme</Tag>
      <div style={{ marginTop: 32, display: "flex", flexDirection: "column", gap: 22 }}>
        {MATCHES.map((m, i) => {
          const s = useIn(8 + i * 10, 22);
          const warn = m.score < 0.9;
          return (
            <div key={m.name} style={{ opacity: s, transform: `translateY(${(1 - s) * 24}px)` }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontFamily: T.sans, fontSize: 30, color: T.ink }}>
                <span>{m.name}</span>
                <span style={{ fontFamily: T.mono }}>{(m.score * s).toFixed(2)}</span>
              </div>
              <div style={{ height: 14, background: T.rule, marginTop: 10 }}>
                <div style={{ height: "100%", width: `${m.score * 100 * s}%`, background: warn ? T.mute : T.signal }} />
              </div>
              <div style={{ fontFamily: T.mono, fontSize: 17, color: warn ? T.signal : T.ok, marginTop: 8, height: 22 }}>
                {m.note ? `eksik bilgi → ${m.note}` : "tam eşleşme"}
              </div>
            </div>
          );
        })}
      </div>
    </Fade>
  );
}

function Approval() {
  const frame = useCurrentFrame();
  const stamp = spring({ frame: frame - 44, fps: FPS, config: { damping: 9, stiffness: 160 } });
  return (
    <Fade>
      <Tag>03 · Ekip onayı</Tag>
      <div style={{ display: "flex", gap: 56, marginTop: 36, alignItems: "center" }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 18 }}>
          {["Eşleşmeler incelendi", "Eksik bilgi müşteriye soruldu", "Fiyat sürümü: 2026-10"].map((t, i) => {
            const s = useIn(6 + i * 10);
            return (
              <div key={t} style={{ display: "flex", alignItems: "center", gap: 18, opacity: s }}>
                <div style={{ width: 34, height: 34, border: `3px solid ${T.ink}`, background: s > 0.7 ? T.ink : "transparent", color: T.bone, fontSize: 24, textAlign: "center", lineHeight: "30px" }}>
                  {s > 0.7 ? "✓" : ""}
                </div>
                <span style={{ fontFamily: T.sans, fontSize: 30, color: T.ink }}>{t}</span>
              </div>
            );
          })}
        </div>
        <div
          style={{
            flex: 0.8,
            height: 240,
            display: "grid",
            placeItems: "center",
            border: `6px solid ${T.signal}`,
            color: T.signal,
            fontFamily: T.serif,
            fontSize: 74,
            fontStyle: "italic",
            transform: `rotate(-7deg) scale(${interpolate(stamp, [0, 1], [2.2, 1])})`,
            opacity: stamp,
          }}
        >
          Onaylandı
        </div>
      </div>
    </Fade>
  );
}

function Quote() {
  const frame = useCurrentFrame();
  const lines = [
    ["KV-50-SS316 / PN40 × 120", 41280],
    ["ATEX sertifika paketi", 3600],
    ["Nakliye · 6 hafta", 2150],
  ] as const;
  const total = lines.reduce((a, l) => a + l[1], 0);
  const count = interpolate(frame, [34, 66], [0, total], { extrapolateRight: "clamp", extrapolateLeft: "clamp" });
  return (
    <AbsoluteFill style={{ padding: 64, opacity: interpolate(frame, [0, 8], [0, 1]) }}>
      <Tag>04 · Teklif çıktısı</Tag>
      <div style={{ marginTop: 28, background: T.paper, border: `2px solid ${T.rule}`, padding: "32px 40px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontFamily: T.mono, fontSize: 18, color: T.mute }}>
          <span>TKL-2291 · v3</span>
          <span>Şartlar 2026-10 · onaylı</span>
        </div>
        {lines.map(([n, v], i) => {
          const s = useIn(6 + i * 9, 20);
          return (
            <div key={n} style={{ display: "flex", justifyContent: "space-between", fontFamily: T.sans, fontSize: 28, color: T.ink, padding: "16px 0", borderBottom: `1.5px solid ${T.rule}`, opacity: s, transform: `translateY(${(1 - s) * 16}px)` }}>
              <span>{n}</span>
              <span style={{ fontFamily: T.mono }}>€{v.toLocaleString("tr-TR")}</span>
            </div>
          );
        })}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 22 }}>
          <span style={{ fontFamily: T.serif, fontStyle: "italic", fontSize: 40, color: T.ink }}>Toplam</span>
          <span style={{ fontFamily: T.mono, fontSize: 48, color: T.signal }}>€{Math.round(count).toLocaleString("tr-TR")}</span>
        </div>
      </div>
    </AbsoluteFill>
  );
}

export const QuoteFlow = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: T.bone }}>
      <Sequence from={0} durationInFrames={90}><Inquiry /></Sequence>
      <Sequence from={90} durationInFrames={90}><Matching /></Sequence>
      <Sequence from={180} durationInFrames={90}><Approval /></Sequence>
      <Sequence from={270} durationInFrames={90}><Quote /></Sequence>
      <div style={{ position: "absolute", left: 0, bottom: 0, height: 6, width: `${(frame / DURATION) * 100}%`, background: T.signal }} />
    </AbsoluteFill>
  );
};
