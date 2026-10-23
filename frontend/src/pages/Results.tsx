import { useState } from "react";
import { Navigate, NavLink, useNavigate, useParams } from "react-router-dom";
import { CalendarDays, Clock, Plus, Users } from "lucide-react";
import { useWorkspace } from "../state/workspace";
import { formatDate } from "../lib/format";
import { Badge, Button, cx } from "../components/ui";
import { ExportMenu } from "../components/ExportMenu";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Overview } from "../results/Overview";
import { ExecutiveSummary, Topics } from "../results/Summary";
import { Decisions, Deadlines, NextSteps, Questions, Risks } from "../results/Items";
import { ActionItems } from "../results/ActionItems";
import { Keywords, PeopleEntities } from "../results/People";
import { TranscriptEvidence } from "../results/Transcript";
import { SECTIONS, sectionPath } from "./sections";

export { SECTIONS };

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
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="fade-up mb-7 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Badge tone="lime">
              <span className="live-dot" /> analysis complete
            </Badge>
            <Badge tone="gray">{report.summary.method} summary</Badge>
            {report.edited_at && <Badge tone="blush">edited</Badge>}
          </div>
          <h1 className="display text-[34px] leading-[1.05] break-words sm:truncate sm:text-[46px]">{report.meeting.title}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 font-mono text-[12px] text-muted">
            <span className="inline-flex items-center gap-1.5">
              <CalendarDays className="h-3.5 w-3.5" />
              {report.meeting.date ? formatDate(report.meeting.date, { weekday: "short" }) : "No meeting date"}
            </span>
            {report.stats.duration && (
              <span className="inline-flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5" /> {report.stats.duration}
              </span>
            )}
            <span>{report.stats.word_count.toLocaleString()} words</span>
            <span className="inline-flex items-center gap-1.5">
              <Users className="h-3.5 w-3.5" /> {report.stats.speaker_count} speakers
            </span>
            {report.meeting.context && <span className="text-faint">· {report.meeting.context}</span>}
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="secondary" icon={<Plus className="h-4 w-4" />} onClick={() => setConfirmReset(true)}>
            New analysis
          </Button>
          <ExportMenu report={report} />
        </div>
      </div>

      <div className="grid gap-6">
        <nav aria-label="Report sections" className="-mx-4 overflow-x-auto px-4 lg:hidden">
          <ul className="flex gap-1.5">
            {SECTIONS.map(({ key, label, icon: Icon, count }) => (
              <li key={key} className="shrink-0">
                <NavLink
                  to={sectionPath(key)}
                  end
                  className={({ isActive }) =>
                    cx(
                      "flex items-center gap-2 rounded-full border px-3 py-1.5 text-[13px] whitespace-nowrap transition",
                      isActive ? "border-lavender-300 bg-lavender-100 font-medium text-ink" : "border-line text-muted hover:text-ink",
                    )
                  }
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span>{label}</span>
                  {count && <span className="font-mono text-[11px] text-faint tabular-nums">{count(report)}</span>}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div key={section} className="fade-up min-w-0">
          {body}
        </div>
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
