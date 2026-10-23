import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { ActionItem, AnalysisReport, AnalyzeRequest, Deadline, ExtractResponse, StageStatus } from "../types";

/**
 * Everything lives in memory only: no localStorage, no server-side history.
 * Reloading the page or pressing "New analysis" discards the workspace.
 */

export interface Draft {
  title: string;
  date: string;
  context: string;
  transcript: string;
  file: Pick<ExtractResponse, "filename" | "file_type" | "pages" | "warnings" | "word_count"> | null;
}

export interface StageState {
  key: string;
  label: string;
  status: StageStatus;
  detail?: string | null;
  elapsedMs?: number;
}

export interface Job {
  request: AnalyzeRequest;
  startedAt: number;
}

export type ActionPatch = Partial<Pick<ActionItem, "description" | "owner" | "status" | "priority" | "needs_review">> & {
  deadlineDate?: string | null;
  deadlineText?: string;
};

interface Workspace {
  draft: Draft;
  setDraft: (patch: Partial<Draft>) => void;
  job: Job | null;
  startJob: (request: AnalyzeRequest) => void;
  clearJob: () => void;
  report: AnalysisReport | null;
  setReport: (report: AnalysisReport) => void;
  updateAction: (id: string, patch: ActionPatch) => void;
  addAction: () => string;
  deleteAction: (id: string) => void;
  resetWorkspace: () => void;
}

export const todayIso = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

const emptyDraft = (): Draft => ({ title: "", date: todayIso(), context: "", transcript: "", file: null });

const Ctx = createContext<Workspace | null>(null);

function applyPatch(item: ActionItem, patch: ActionPatch): ActionItem {
  const next: ActionItem = { ...item, edited: true };
  if (patch.description !== undefined) next.description = patch.description;
  if (patch.status !== undefined) next.status = patch.status;
  if (patch.priority !== undefined) next.priority = patch.priority;
  if (patch.owner !== undefined) {
    next.owner = patch.owner.trim() || "Unassigned";
    next.owner_source = next.owner === "Unassigned" ? "unassigned" : "user";
  }
  if (patch.deadlineDate !== undefined || patch.deadlineText !== undefined) {
    const date = patch.deadlineDate !== undefined ? patch.deadlineDate : (item.deadline?.normalized_date ?? null);
    const text = patch.deadlineText ?? date ?? "";
    if (!date && !text.trim()) {
      next.deadline = null;
    } else {
      const deadline: Deadline = {
        id: item.deadline?.id ?? `D-${item.id}`,
        text: text || date || "",
        normalized_date: date,
        date_type: "user",
        granularity: date ? "day" : "unknown",
        is_ambiguous: !date,
        note: "Set by the user.",
        related_action_id: item.id,
        evidence: item.deadline?.evidence ?? [],
      };
      next.deadline = deadline;
    }
  }
  if (patch.needs_review !== undefined) {
    next.needs_review = patch.needs_review;
    if (!patch.needs_review) next.review_reasons = [];
  }
  return next;
}

/** Keep the report-level deadline list and stats consistent with edited action items. */
function syncDerived(report: AnalysisReport): AnalysisReport {
  const actionIds = new Set(report.action_items.map((a) => a.id));
  const standalone = report.deadlines.filter((d) => !d.related_action_id || !actionIds.has(d.related_action_id));
  const fromActions = report.action_items.filter((a) => a.deadline).map((a) => a.deadline as Deadline);
  const deadlines = [...fromActions, ...standalone].sort((a, b) =>
    (a.normalized_date ?? "9999") < (b.normalized_date ?? "9999") ? -1 : 1,
  );
  const people = report.people.map((p) => ({
    ...p,
    action_items: report.action_items.filter((a) => a.owner.split(" & ").includes(p.name)).length,
  }));
  return {
    ...report,
    deadlines,
    people,
    edited_at: new Date().toISOString().slice(0, 19) + "Z",
    stats: {
      ...report.stats,
      action_items: report.action_items.length,
      unassigned_action_items: report.action_items.filter((a) => a.owner === "Unassigned").length,
      items_needing_review:
        report.action_items.filter((a) => a.needs_review).length +
        report.decisions.filter((d) => d.needs_review).length +
        report.risks.filter((r) => r.needs_review).length,
    },
  };
}

export function WorkspaceProvider({ children, initialReport = null }: { children: ReactNode; initialReport?: AnalysisReport | null }) {
  const [draft, setDraftState] = useState<Draft>(emptyDraft);
  const [job, setJob] = useState<Job | null>(null);
  const [report, setReportState] = useState<AnalysisReport | null>(initialReport);
  const reportRef = useRef(report);
  reportRef.current = report;

  const setDraft = useCallback((patch: Partial<Draft>) => setDraftState((d) => ({ ...d, ...patch })), []);
  const startJob = useCallback((request: AnalyzeRequest) => setJob({ request, startedAt: Date.now() }), []);
  const clearJob = useCallback(() => setJob(null), []);
  const setReport = useCallback((r: AnalysisReport) => setReportState(r), []);

  const updateAction = useCallback((id: string, patch: ActionPatch) => {
    setReportState((r) =>
      r ? syncDerived({ ...r, action_items: r.action_items.map((a) => (a.id === id ? applyPatch(a, patch) : a)) }) : r,
    );
  }, []);

  const addAction = useCallback(() => {
    const current = reportRef.current?.action_items ?? [];
    const max = current.reduce((m, a) => Math.max(m, Number(a.id.replace(/\D/g, "")) || 0), 0);
    const newId = `A${max + 1}`;
    setReportState((r) => {
      if (!r) return r;
      const item: ActionItem = {
        id: newId,
        description: "New action item",
        owner: "Unassigned",
        owner_source: "user",
        deadline: null,
        status: "open",
        priority: "medium",
        is_inferred: false,
        needs_review: false,
        review_reasons: [],
        signal: "strong",
        evidence: [],
        edited: true,
      };
      return syncDerived({ ...r, action_items: [...r.action_items, item] });
    });
    return newId;
  }, []);

  const deleteAction = useCallback((id: string) => {
    setReportState((r) => (r ? syncDerived({ ...r, action_items: r.action_items.filter((a) => a.id !== id) }) : r));
  }, []);

  const resetWorkspace = useCallback(() => {
    setReportState(null);
    setJob(null);
    setDraftState(emptyDraft());
  }, []);

  // Development-only hook so end-to-end scripts can load a report without re-running the models.
  useEffect(() => {
    if (import.meta.env.DEV) (window as unknown as { __meetingmind?: object }).__meetingmind = { setReport };
  }, [setReport]);

  // Warn before closing the tab while a report or draft exists (nothing is saved anywhere).
  useEffect(() => {
    if (!report && !draft.transcript) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [report, draft.transcript]);

  const value = useMemo(
    () => ({ draft, setDraft, job, startJob, clearJob, report, setReport, updateAction, addAction, deleteAction, resetWorkspace }),
    [draft, setDraft, job, startJob, clearJob, report, setReport, updateAction, addAction, deleteAction, resetWorkspace],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWorkspace(): Workspace {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return ctx;
}
