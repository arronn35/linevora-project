import { useCallback, useEffect, useRef, useState } from "react";

/** Data hook refreshed at a fixed interval; pauses while the tab is hidden. */
export function usePolling<T>(fn: () => Promise<T>, intervalMs: number, enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const tick = useCallback(async () => {
    if (typeof document !== "undefined" && document.hidden) return;
    try {
      const v = await fnRef.current();
      setData(v); setError(null); setUpdatedAt(Date.now());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);
  useEffect(() => {
    if (!enabled) return;
    void tick();
    const id = setInterval(() => void tick(), intervalMs);
    const onVis = () => { if (!document.hidden) void tick(); };
    document.addEventListener("visibilitychange", onVis);
    return () => { clearInterval(id); document.removeEventListener("visibilitychange", onVis); };
  }, [enabled, intervalMs, tick]);
  return { data, error, updatedAt, refresh: tick };
}

export function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
