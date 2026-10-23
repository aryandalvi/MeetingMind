import { useEffect, useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { Lock } from "lucide-react";
import { api } from "../api/client";
import { useWorkspace } from "../state/workspace";
import type { HealthResponse } from "../types";
import { cx, Logo } from "./ui";

export function useHealth(pollMs = 0) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () =>
      api
        .health()
        .then((h) => alive && (setHealth(h), setError(null)))
        .catch((e) => alive && setError((e as Error).message));
    load();
    const t = pollMs ? setInterval(load, pollMs) : undefined;
    return () => {
      alive = false;
      if (t) clearInterval(t);
    };
  }, [pollMs]);
  return { health, error };
}

function ModelPill() {
  const { health, error } = useHealth(15000);
  if (error) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-2.5 py-1 text-xs font-medium text-rose-600" title={error}>
        <span className="h-1.5 w-1.5 rounded-full bg-rose-600" /> API offline
      </span>
    );
  }
  if (!health) return null;
  const active = health.models.filter((m) => m.state !== "disabled");
  const ready = active.filter((m) => m.state === "ready").length;
  const failed = active.some((m) => m.state === "failed");
  const label = failed ? "Model issue" : ready === active.length ? "Models ready" : ready === 0 ? "Models load on first run" : "Models loading";
  const tone = failed ? "bg-amber-50 text-amber-600" : ready === active.length ? "bg-sage-50 text-sage-600" : "bg-lavender-50 text-violet-600";
  const dot = failed ? "bg-amber-600" : ready === active.length ? "bg-sage-600" : "bg-violet-500";
  return (
    <span
      className={cx("hidden items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium sm:inline-flex", tone)}
      title={health.models.map((m) => `${m.role}: ${m.state}${m.error ? ` (${m.error})` : ""}`).join("\n")}
    >
      <span className={cx("h-1.5 w-1.5 rounded-full", dot)} /> {label}
    </span>
  );
}

export function Layout() {
  const { report } = useWorkspace();
  const link = ({ isActive }: { isActive: boolean }) =>
    cx("rounded-lg px-2.5 py-1.5 text-sm whitespace-nowrap transition sm:px-3", isActive ? "bg-lavender-50 font-medium text-violet-700" : "text-muted hover:text-ink");
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-line/80 bg-surface/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-2 px-4 sm:gap-4 sm:px-6">
          <Link to="/" aria-label="MeetingMind home" className="shrink-0">
            <Logo />
          </Link>
          <nav className="ml-1 flex min-w-0 items-center gap-0.5 overflow-x-auto sm:ml-2 sm:gap-1">
            <NavLink to="/" end className={link}>
              Dashboard
            </NavLink>
            <NavLink to="/new" className={link}>
              New analysis
            </NavLink>
            {report && (
              <NavLink to="/results" className={link}>
                Results
              </NavLink>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <ModelPill />
          </div>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-line bg-surface/60">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-xs text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <span className="inline-flex items-center gap-1.5">
            <Lock className="h-3.5 w-3.5" /> Transcripts are processed temporarily and never stored. Reports live only in this browser tab.
          </span>
          <span>MeetingMind · Your meetings, made meaningful</span>
        </div>
      </footer>
    </div>
  );
}
