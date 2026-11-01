import { useEffect, useState } from "react";
import { Landing } from "./Landing";
import { Panel } from "./panel/Panel";

function route(): "landing" | "panel" {
  if (typeof window === "undefined") return "landing";
  return window.location.pathname === "/panel" || window.location.pathname.startsWith("/panel/") ? "panel" : "landing";
}

export function App() {
  const [r, setR] = useState(route);
  useEffect(() => {
    const onPop = () => setR(route());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  return r === "panel" ? <Panel /> : <Landing />;
}
