import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { FileBarChart2, Home, Lock, Plus, Wand2 } from "lucide-react";
import { api } from "../api/client";
import { useWorkspace } from "../state/workspace";
import { SECTIONS, sectionPath } from "../pages/sections";
import type { HealthResponse } from "../types";
import { cx, Logo, ThemeToggle } from "./ui";

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

function ModelPill({ className }: { className?: string }) {
  const { health, error } = useHealth(15000);
  if (error) {
    return (
      <span className={cx("inline-flex items-center gap-1.5 rounded-full border border-rose-600/30 bg-rose-50 px-2.5 py-1 font-mono text-[11px] text-rose-600", className)} title={error}>
        <span className="h-1.5 w-1.5 rounded-full bg-rose-600" /> API offline
      </span>
    );
  }
  if (!health) return null;
  const active = health.models.filter((m) => m.state !== "disabled");
  const ready = active.filter((m) => m.state === "ready").length;
  const failed = active.some((m) => m.state === "failed");
  const label = failed ? "Model issue" : ready === active.length ? "Models ready" : ready === 0 ? "Models load on first run" : "Models loading";
  const tone = failed
    ? "border-amber-600/30 bg-amber-50 text-amber-600"
    : ready === active.length
      ? "border-lime-300 bg-lime-50 text-lime-400"
      : "border-lavender-200 bg-lavender-50 text-violet-300";
  const dot = failed ? "bg-amber-600" : ready === active.length ? "live-dot" : "bg-violet-400";
  return (
    <span
      className={cx("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[11px]", tone, className)}
      title={health.models.map((m) => `${m.role}: ${m.state}${m.error ? ` (${m.error})` : ""}`).join("\n")}
    >
      <span className={cx("h-1.5 w-1.5 rounded-full", dot)} /> {label}
    </span>
  );
}

const sideLink = ({ isActive }: { isActive: boolean }) =>
  cx(
    "group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13.5px] transition",
    isActive
      ? "bg-wash-2 font-medium text-ink ring-1 ring-line-strong before:absolute before:top-2 before:bottom-2 before:-left-3 before:w-[3px] before:rounded-full before:bg-violet-500 before:shadow-[0_0_10px_var(--color-violet-500)]"
      : "text-muted hover:bg-wash-1 hover:text-ink",
  );

function Sidebar() {
  const { report } = useWorkspace();
  const navigate = useNavigate();
  return (
    <aside className="sticky top-0 hidden h-screen w-[264px] shrink-0 flex-col border-r border-line bg-surface/50 backdrop-blur-xl lg:flex">
      <div className="flex items-center justify-between px-5 pt-5 pb-4">
        <Link to="/" aria-label="MeetingMind home">
          <Logo />
        </Link>
        <div className="flex items-center gap-2">
          <span className="kbd">local</span>
          <ThemeToggle />
        </div>
      </div>
      <div className="px-4">
        <button
          onClick={() => navigate("/new")}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-b from-violet-500 to-violet-800 py-2.5 text-sm font-semibold text-white shadow-[var(--shadow-glow)] transition hover:brightness-115"
        >
          <Plus className="h-4 w-4" /> Quick analyze
        </button>
      </div>

      <nav className="mt-6 flex-1 overflow-y-auto px-4 pb-4" aria-label="Main">
        <div className="mb-2 px-3 font-mono text-[10px] tracking-[0.14em] text-faint uppercase">Workspace</div>
        <ul className="space-y-0.5">
          <li>
            <NavLink to="/" end className={sideLink}>
              <Home className="h-4 w-4" /> Dashboard
            </NavLink>
          </li>
          <li>
            <NavLink to="/new" className={sideLink}>
              <Wand2 className="h-4 w-4" /> New analysis
            </NavLink>
          </li>
        </ul>

        {report && (
          <>
            <div className="mt-6 mb-2 flex items-center gap-2 px-3 font-mono text-[10px] tracking-[0.14em] text-faint uppercase">
              <span className="live-dot" /> Current report
            </div>
            <div className="mb-2 truncate px-3 text-[13px] font-semibold text-ink-soft" title={report.meeting.title}>
              {report.meeting.title}
            </div>
            <ul className="space-y-0.5">
              {SECTIONS.map(({ key, label, icon: Icon, count }) => (
                <li key={key}>
                  <NavLink to={sectionPath(key)} end className={sideLink}>
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="flex-1 truncate">{label}</span>
                    {count && <span className="font-mono text-[11px] text-faint tabular-nums">{count(report)}</span>}
                  </NavLink>
                </li>
              ))}
            </ul>
          </>
        )}
      </nav>

      <div className="border-t border-line p-4">
        <div className="flex items-start gap-2.5 rounded-xl border border-line bg-wash-1 p-3">
          <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sage-600" />
          <p className="text-[11.5px] leading-relaxed text-muted">Processed on your server, never stored. Reports live only in this tab.</p>
        </div>
      </div>
    </aside>
  );
}

const TITLES: Record<string, string> = { "": "Dashboard", new: "New analysis", processing: "Analysing", results: "Report" };

export function Layout() {
  const { report } = useWorkspace();
  const { pathname } = useLocation();
  const crumb = TITLES[pathname.split("/")[1] ?? ""] ?? "";
  const mobileLink = ({ isActive }: { isActive: boolean }) =>
    cx("rounded-lg px-2.5 py-1.5 text-sm whitespace-nowrap transition", isActive ? "bg-wash-3 font-medium text-ink" : "text-muted hover:text-ink");

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 border-b border-line bg-mist/70 backdrop-blur-xl">
          <div className="flex h-14 items-center gap-3 px-4 sm:px-6">
            <Link to="/" aria-label="MeetingMind home" className="shrink-0 lg:hidden">
              <Logo />
            </Link>
            <nav className="flex min-w-0 items-center gap-0.5 overflow-x-auto lg:hidden">
              <NavLink to="/" end className={mobileLink}>
                Home
              </NavLink>
              <NavLink to="/new" className={mobileLink}>
                New
              </NavLink>
              {report && (
                <NavLink to="/results" className={mobileLink}>
                  Results
                </NavLink>
              )}
            </nav>
            <div className="hidden min-w-0 items-center gap-2 font-mono text-[12px] text-faint lg:flex">
              <span>workspace</span>
              <span>/</span>
              <span className="text-ink-soft">{crumb.toLowerCase()}</span>
              {pathname.startsWith("/results") && report && (
                <>
                  <span>/</span>
                  <span className="inline-flex min-w-0 items-center gap-1.5 truncate text-ink-soft">
                    <FileBarChart2 className="h-3.5 w-3.5 shrink-0 text-violet-400" />
                    <span className="truncate">{report.meeting.title}</span>
                  </span>
                </>
              )}
            </div>
            <div className="ml-auto flex items-center gap-3">
              <span className="hidden font-mono text-[11px] text-faint xl:inline">spaCy · MiniLM · DistilBART</span>
              <ModelPill className="hidden sm:inline-flex" />
              <ThemeToggle className="lg:hidden" />
            </div>
          </div>
        </header>
        <main className="flex-1">
          <Outlet />
        </main>
        <footer className="border-t border-line">
          <div className="flex flex-col gap-2 px-4 py-5 font-mono text-[11px] text-faint sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <span className="inline-flex items-center gap-1.5">
              <Lock className="h-3.5 w-3.5" /> Transcripts are processed temporarily and never stored.
            </span>
            <span>MeetingMind · your meetings, made meaningful</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
