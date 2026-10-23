import { useEffect, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Check, Clock, Loader2, RotateCcw, Square, X } from "lucide-react";
import { api } from "../api/client";
import { useWorkspace, type StageState } from "../state/workspace";
import type { StreamEvent } from "../types";
import { Button, cx, Sparkle } from "../components/ui";

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
        <Sparkle className="sparkle-twinkle absolute top-6 right-8 text-blush-400" size={16} />
        <Sparkle className="sparkle-twinkle absolute top-14 right-16 text-violet-400 [animation-delay:1.4s]" size={10} />
        <div className="eyebrow mb-1.5">Analysing</div>
        <h1 className="display text-[34px] leading-tight">{job.request.title}</h1>
        <p className="mt-1 text-sm text-muted">
          {job.request.transcript.split(/\s+/).filter(Boolean).length.toLocaleString()} words · elapsed {seconds(totalMs)}
        </p>

        <div className="mt-6 h-2 overflow-hidden rounded-full bg-lavender-50" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Completed stages">
          <div className="h-full rounded-full bg-violet-500 transition-all duration-500" style={{ width: `${pct}%` }} />
        </div>
        <p className="mt-2 text-xs text-faint">
          {done} of {stages.length || "…"} stages complete — progress reflects stages actually finished on the server.
        </p>

        {queued && (
          <div className="mt-5 flex items-center gap-2 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-600">
            <Clock className="h-4 w-4" /> {queued}
          </div>
        )}
        {slowModels && !error && (
          <div className="mt-5 rounded-xl bg-lavender-50 px-4 py-3 text-sm leading-relaxed text-ink-soft">
            <b className="font-medium text-violet-700">Initialising models.</b> The first analysis after starting the server loads (and, the very
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
              <li key={s.key} className={cx("flex items-start gap-3 rounded-xl px-3 py-2.5 transition", running && "bg-lavender-50")}>
                <span
                  className={cx(
                    "mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full",
                    s.status === "completed" && "bg-sage-600 text-white",
                    running && "text-violet-600",
                    s.status === "failed" && "bg-rose-600 text-white",
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
                <span className="text-xs text-faint tabular-nums">
                  {s.status === "completed" && s.elapsedMs !== undefined && seconds(s.elapsedMs)}
                  {running && seconds(now - stageStartedAt)}
                </span>
              </li>
            );
          })}
        </ol>

        {error && (
          <div className="mt-6 rounded-2xl border border-rose-600/15 bg-rose-50 p-4">
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
          <div className="mt-6 rounded-2xl bg-mist p-4 text-sm text-muted">
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
