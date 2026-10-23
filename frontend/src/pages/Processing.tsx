import { useEffect, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Check, Clock, Loader2, RotateCcw, Square, X } from "lucide-react";
import { api } from "../api/client";
import { useWorkspace, type StageState } from "../state/workspace";
import type { StreamEvent } from "../types";
import { Button, cx, Waveform } from "../components/ui";

function seconds(ms: number) {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

export function Processing() {
  const navigate = useNavigate();
  const { job, startJob, clearJob, setReport, report } = useWorkspace();
  const [stages, setStages] = useState<StageState[]>([]);
  const [queued, setQueued] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelled, setCancelled] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [stageStartedAt, setStageStartedAt] = useState<number>(Date.now());
  const started = useRef<number | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!job || started.current === job.startedAt) return; // run once per job (StrictMode-safe)
    started.current = job.startedAt;
    setStages([]);
    setError(null);
    setQueued(null);
    setCancelled(false);
    const ctrl = new AbortController();
    controller.current = ctrl;

    const onEvent = (e: StreamEvent) => {
      if (e.type === "accepted") {
        setStages(e.stages.map((s) => ({ key: s.key, label: s.label, status: "pending" })));
      } else if (e.type === "queued") {
        setQueued(e.message);
      } else if (e.type === "stage") {
        setQueued(null);
        if (e.status === "started") setStageStartedAt(Date.now());
        setStages((prev) =>
          prev.map((s) =>
            s.key === e.stage
              ? {
                  ...s,
                  status: e.status,
                  detail: e.detail ?? (e.status === "started" ? null : s.detail),
                  elapsedMs: e.elapsed_ms ?? s.elapsedMs,
                }
              : s,
          ),
        );
      } else if (e.type === "result") {
        setReport(e.report);
        clearJob();
        navigate("/results", { replace: true });
      } else if (e.type === "error") {
        setError(e.message);
      }
    };

    api.analyzeStream(job.request, onEvent, ctrl.signal).catch((err: Error) => {
      if (err.name === "AbortError") return;
      setError(err.message);
    });
  }, [job, navigate, setReport, clearJob]);

  // After a result arrives the job is cleared; send the user to the report, not back to the editor.
  if (!job) return <Navigate to={report ? "/results" : "/new"} replace />;

  const active = stages.find((s) => s.status === "started" || s.status === "progress");
  const done = stages.filter((s) => s.status === "completed").length;
  const pct = stages.length ? Math.round((done / stages.length) * 100) : 0;
  const totalMs = now - job.startedAt;
  const slowModels = active?.key === "models" && now - stageStartedAt > 4000;

  function cancel() {
    controller.current?.abort();
    setCancelled(true);
  }

  function retry() {
    if (job) startJob(job.request);
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <div className="card relative overflow-hidden p-6 sm:p-8">
        <div aria-hidden="true" className="pointer-events-none absolute -top-24 -right-20 h-60 w-60 rounded-full bg-violet-500/25 blur-3xl" />
        {!error && !cancelled && <Waveform bars={16} height={30} className="absolute top-7 right-7 hidden sm:inline-flex" />}
        <div className="eyebrow mb-2 flex items-center gap-2">
          <span className="live-dot" /> Analysing
        </div>
        <h1 className="display relative text-[32px] leading-tight sm:text-[38px]">{job.request.title}</h1>
        <p className="mt-1.5 font-mono text-[12px] text-muted">
          {job.request.transcript.split(/\s+/).filter(Boolean).length.toLocaleString()} words · elapsed {seconds(totalMs)}
        </p>

        <div className="mt-6 h-1.5 overflow-hidden rounded-full bg-wash-2" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Completed stages">
          <div className="h-full rounded-full bg-gradient-to-r from-violet-500 via-violet-400 to-lime-400 shadow-[0_0_12px_rgb(139_92_246/0.6)] transition-all duration-500" style={{ width: `${pct}%` }} />
        </div>
        <p className="mt-2 font-mono text-[11px] text-faint">
          {done} of {stages.length || "…"} stages complete — progress reflects stages actually finished on the server.
        </p>

        {queued && (
          <div className="mt-5 flex items-center gap-2 rounded-xl border border-amber-600/25 bg-amber-50 px-4 py-3 text-sm text-amber-600">
            <Clock className="h-4 w-4" /> {queued}
          </div>
        )}
        {slowModels && !error && (
          <div className="mt-5 rounded-xl border border-lavender-200 bg-lavender-50 px-4 py-3 text-sm leading-relaxed text-ink-soft">
            <b className="font-semibold text-violet-300">Initialising models.</b> The first analysis after starting the server loads (and, the very
            first time, downloads about 1.3 GB of) NLP models. Later analyses skip this step.
          </div>
        )}

        <ol className="mt-6 space-y-1">
          {stages.length === 0 && !error && (
            <li className="flex items-center gap-3 py-2 text-sm text-muted">
              <Loader2 className="h-4 w-4 animate-spin text-violet-500" /> Connecting to the analysis server…
            </li>
          )}
          {stages.map((s) => {
            const running = s.status === "started" || s.status === "progress";
            return (
              <li key={s.key} className={cx("flex items-start gap-3 rounded-xl px-3 py-2.5 transition", running && "bg-lavender-50 ring-1 ring-lavender-200")}>
                <span
                  className={cx(
                    "mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full",
                    s.status === "completed" && "bg-lime-400 text-[var(--color-on-vivid)] shadow-[0_0_10px_color-mix(in_srgb,var(--color-lime-400)_50%,transparent)]",
                    running && "text-violet-400",
                    s.status === "failed" && "bg-rose-600 text-[var(--color-on-vivid)]",
                    s.status === "pending" && "border border-line-strong",
                  )}
                >
                  {s.status === "completed" && <Check className="h-3 w-3" strokeWidth={3} />}
                  {running && <Loader2 className="h-4 w-4 animate-spin" />}
                  {s.status === "failed" && <X className="h-3 w-3" strokeWidth={3} />}
                </span>
                <div className="min-w-0 flex-1">
                  <div className={cx("text-sm", s.status === "pending" ? "text-faint" : "font-medium text-ink")}>{s.label}</div>
                  {s.detail && <div className="mt-0.5 text-xs text-muted">{s.detail}</div>}
                </div>
                <span className="font-mono text-[11px] text-faint tabular-nums">
                  {s.status === "completed" && s.elapsedMs !== undefined && seconds(s.elapsedMs)}
                  {running && seconds(now - stageStartedAt)}
                </span>
              </li>
            );
          })}
        </ol>

        {error && (
          <div className="mt-6 rounded-2xl border border-rose-600/30 bg-rose-50 p-4">
            <div className="flex items-start gap-2 text-sm text-rose-600">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <div className="font-medium">The analysis could not be completed</div>
                <div className="mt-0.5 text-rose-600/90">{error}</div>
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <Button size="sm" icon={<RotateCcw className="h-3.5 w-3.5" />} onClick={retry}>
                Try again
              </Button>
              <Button size="sm" variant="secondary" icon={<ArrowLeft className="h-3.5 w-3.5" />} onClick={() => (clearJob(), navigate("/new"))}>
                Back to the editor
              </Button>
            </div>
          </div>
        )}
        {cancelled && !error && (
          <div className="mt-6 rounded-2xl border border-line bg-wash-1 p-4 text-sm text-muted">
            Cancelled. The server may finish the current run in the background, but the result is discarded and nothing is stored.
            <div className="mt-3 flex gap-2">
              <Button size="sm" icon={<RotateCcw className="h-3.5 w-3.5" />} onClick={retry}>
                Start again
              </Button>
              <Button size="sm" variant="secondary" onClick={() => (clearJob(), navigate("/new"))}>
                Back to the editor
              </Button>
            </div>
          </div>
        )}
        {!error && !cancelled && (
          <div className="mt-6 flex justify-end">
            <Button variant="ghost" size="sm" icon={<Square className="h-3.5 w-3.5" />} onClick={cancel}>
              Cancel
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
