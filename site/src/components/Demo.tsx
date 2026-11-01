import { useEffect, useRef, useState } from "react";
import { Player, type PlayerRef } from "@remotion/player";
import { DURATION, FPS, QuoteFlow, SCENES } from "../remotion/QuoteFlow";

export function Demo() {
  const ref = useRef<PlayerRef>(null);
  const [scene, setScene] = useState(0);

  useEffect(() => {
    const p = ref.current;
    if (!p) return;
    const onFrame = ({ detail }: { detail: { frame: number } }) => {
      const i = SCENES.reduce((acc, s, idx) => (detail.frame >= s.from ? idx : acc), 0);
      setScene((c) => (c === i ? c : i));
    };
    p.addEventListener("frameupdate", onFrame);
    return () => p.removeEventListener("frameupdate", onFrame);
  }, []);

  return (
    <div className="demo">
      <div className="demo-frame">
        <Player
          ref={ref}
          component={QuoteFlow}
          durationInFrames={DURATION}
          compositionWidth={1280}
          compositionHeight={720}
          fps={FPS}
          loop
          autoPlay
          clickToPlay
          style={{ width: "100%", aspectRatio: "16/9" }}
          acknowledgeRemotionLicense
        />
      </div>
      <div className="demo-steps" role="tablist" aria-label="Akış adımları">
        {SCENES.map((s, i) => (
          <button
            key={s.label}
            role="tab"
            aria-selected={scene === i}
            className={scene === i ? "on" : ""}
            onClick={() => {
              ref.current?.seekTo(s.from);
              ref.current?.play();
            }}
          >
            <span>0{i + 1}</span>
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
