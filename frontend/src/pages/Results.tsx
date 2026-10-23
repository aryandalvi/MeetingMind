import { useState } from "react";
import { Navigate, NavLink, useNavigate, useParams } from "react-router-dom";
import {
  CalendarClock,
  FileText,
  Gavel,
  HelpCircle,
  LayoutDashboard,
  ListChecks,
  Plus,
  Quote,
  ShieldAlert,
  Signpost,
  Tags,
  Users,
  Waypoints,
} from "lucide-react";
import { useWorkspace } from "../state/workspace";
import { formatDate } from "../lib/format";
import { Button, cx } from "../components/ui";
import { ExportMenu } from "../components/ExportMenu";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Overview } from "../results/Overview";
import { ExecutiveSummary, Topics } from "../results/Summary";
import { Decisions, Deadlines, NextSteps, Questions, Risks } from "../results/Items";
import { ActionItems } from "../results/ActionItems";
import { Keywords, PeopleEntities } from "../results/People";
import { TranscriptEvidence } from "../results/Transcript";
import type { AnalysisReport } from "../types";

type SectionDef = { key: string; label: string; icon: typeof FileText; count?: (r: AnalysisReport) => number };

export const SECTIONS: SectionDef[] = [
  { key: "overview", label: "Overview", icon: LayoutDashboard },
  { key: "summary", label: "Executive summary", icon: FileText },
  { key: "topics", label: "Discussion topics", icon: Waypoints, count: (r) => r.topics.length },
  { key: "decisions", label: "Decisions", icon: Gavel, count: (r) => r.decisions.length },
  { key: "actions", label: "Action items", icon: ListChecks, count: (r) => r.action_items.length },
  { key: "deadlines", label: "Deadlines", icon: CalendarClock, count: (r) => r.deadlines.length },
  { key: "risks", label: "Risks & blockers", icon: ShieldAlert, count: (r) => r.risks.length },
  { key: "questions", label: "Unresolved questions", icon: HelpCircle, count: (r) => r.questions.length },
  { key: "people", label: "People & entities", icon: Users, count: (r) => r.entities.length },
  { key: "keywords", label: "Keywords", icon: Tags, count: (r) => r.keywords.length },
  { key: "evidence", label: "Transcript evidence", icon: Quote, count: (r) => r.sentences.length },
  { key: "next", label: "Recommended next steps", icon: Signpost, count: (r) => r.next_steps.length },
];

export function Results() {
  const { section = "overview" } = useParams();
  const { report, resetWorkspace } = useWorkspace();
  const navigate = useNavigate();
  const [confirmReset, setConfirmReset] = useState(false);

  if (!report) return <Navigate to="/new" replace />;
  if (!SECTIONS.some((s) => s.key === section)) return <Navigate to="/results" replace />;

  const body = {
    overview: <Overview report={report} />,
    summary: <ExecutiveSummary report={report} />,
    topics: <Topics report={report} />,
    decisions: <Decisions report={report} />,
    actions: <ActionItems />,
    deadlines: <Deadlines report={report} />,
    risks: <Risks report={report} />,
    questions: <Questions report={report} />,
    people: <PeopleEntities report={report} />,
    keywords: <Keywords report={report} />,
    evidence: <TranscriptEvidence report={report} />,
    next: <NextSteps report={report} />,
  }[section];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <div className="eyebrow mb-1">Meeting report</div>
          <h1 className="display truncate text-[36px] leading-tight sm:text-[42px]">{report.meeting.title}</h1>
          <p className="mt-1 text-sm text-muted">
            {report.meeting.date ? formatDate(report.meeting.date, { weekday: "long" }) : "No meeting date"}
            {report.meeting.context && <> · {report.meeting.context}</>}
            {report.edited_at && <span className="ml-2 rounded-full bg-blush-50 px-2 py-0.5 text-xs text-blush-600">edited</span>}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="secondary" icon={<Plus className="h-4 w-4" />} onClick={() => setConfirmReset(true)}>
            New analysis
          </Button>
          <ExportMenu report={report} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[236px_1fr]">
        <nav aria-label="Report sections" className="-mx-4 overflow-x-auto px-4 lg:mx-0 lg:overflow-visible lg:px-0">
          <ul className="flex gap-1.5 lg:sticky lg:top-24 lg:flex-col lg:gap-0.5">
            {SECTIONS.map(({ key, label, icon: Icon, count }) => (
              <li key={key} className="shrink-0">
                <NavLink
                  to={key === "overview" ? "/results" : `/results/${key}`}
                  end
                  className={({ isActive }) =>
                    cx(
                      "flex items-center gap-2.5 rounded-xl px-3 py-2 text-[13.5px] whitespace-nowrap transition",
                      isActive ? "bg-surface font-medium text-violet-700 shadow-[var(--shadow-soft)] ring-1 ring-line" : "text-muted hover:bg-surface/70 hover:text-ink",
                    )
                  }
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="flex-1">{label}</span>
                  {count && <span className="text-xs text-faint tabular-nums">{count(report)}</span>}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className="min-w-0">{body}</div>
      </div>

      <ConfirmDialog
        open={confirmReset}
        title="Start a new analysis?"
        confirmLabel="Discard report"
        onCancel={() => setConfirmReset(false)}
        onConfirm={() => {
          resetWorkspace();
          navigate("/new");
        }}
      >
        This report and your edits exist only in this tab and will be cleared. Use <b>Export</b> first if you want to keep them.
      </ConfirmDialog>
    </div>
  );
}
