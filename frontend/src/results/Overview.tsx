import { useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowRight, Clock, Flag, Gavel, HelpCircle, ListChecks, MessagesSquare, ShieldAlert, Users } from "lucide-react";
import type { AnalysisReport } from "../types";
import { plural } from "../lib/format";
import { Badge, SectionHeader, Sparkle, Stat } from "../components/ui";
import { TalkShareChart } from "./charts";

export function Overview({ report }: { report: AnalysisReport }) {
  const s = report.stats;
  const navigate = useNavigate();
  const speakers = report.people.filter((p) => p.is_speaker);
  const totalMs = Object.values(report.timings_ms).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      <SectionHeader eyebrow="Overview" title="At a glance" description="Counts of everything MeetingMind extracted. Open any section from the menu to review the items and their evidence." />

      <div className="card relative overflow-hidden p-6">
        <Sparkle className="absolute top-5 right-6 text-blush-200" size={20} />
        <div className="eyebrow mb-2">In one breath</div>
        <p className="max-w-3xl text-[17px] leading-relaxed text-ink">
          {(report.summary.executive.find((x) => x.grounding === "supported") ?? report.summary.executive[0])?.text ??
            "No summary could be produced."}
        </p>
        <button onClick={() => navigate("/results/summary")} className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-violet-600 hover:text-violet-700">
          Read the executive summary <ArrowRight className="h-4 w-4" />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Action items" value={s.action_items} hint={`${s.unassigned_action_items} unassigned`} icon={<ListChecks className="h-4 w-4 text-violet-500" />} />
        <Stat label="Decisions" value={s.decisions} hint={plural(report.decisions.filter((d) => d.status === "tentative").length, "tentative")} icon={<Gavel className="h-4 w-4 text-violet-500" />} />
        <Stat label="Risks & blockers" value={s.risks + s.blockers} hint={plural(s.blockers, "blocker")} icon={<ShieldAlert className="h-4 w-4 text-blush-600" />} />
        <Stat label="Open questions" value={s.open_questions} icon={<HelpCircle className="h-4 w-4 text-blush-600" />} />
        <Stat label="Speakers" value={s.speaker_count} hint={s.has_speaker_labels ? "from speaker labels" : "no labels detected"} icon={<Users className="h-4 w-4 text-muted" />} />
        <Stat label="Words" value={s.word_count.toLocaleString()} hint={`${s.sentence_count} sentences · ${s.estimated_reading_minutes} min read`} icon={<MessagesSquare className="h-4 w-4 text-muted" />} />
        <Stat label="Duration" value={s.duration ?? "—"} hint={s.has_timestamps ? "from timestamps" : "no timestamps"} icon={<Clock className="h-4 w-4 text-muted" />} />
        <Stat label="Needs review" value={s.items_needing_review} hint="flagged for a human check" icon={<Flag className="h-4 w-4 text-amber-600" />} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <div className="card p-5">
          <div className="mb-1 font-medium text-ink">Share of words by speaker</div>
          <p className="mb-3 text-xs text-muted">Percentage of all spoken words in the transcript.</p>
          {speakers.length ? <TalkShareChart people={speakers} /> : <p className="text-sm text-muted">No speaker labels were detected.</p>}
        </div>
        <div className="card p-5">
          <div className="mb-3 font-medium text-ink">Analysis details</div>
          <dl className="space-y-2.5 text-sm">
            <Row label="Summary method">
              <Badge tone="violet">{report.summary.method}</Badge>
            </Row>
            <Row label="Summarizer">{report.models.summarizer}</Row>
            <Row label="Embeddings">{report.models.embeddings}</Row>
            <Row label="Linguistics & NER">{report.models.spacy}</Row>
            <Row label="Keywords">{report.models.keywords}</Row>
            <Row label="Processing time">{(totalMs / 1000).toFixed(1)} s</Row>
          </dl>
          {report.warnings.length > 0 && (
            <div className="mt-4 space-y-1.5 rounded-xl bg-amber-50 p-3 text-xs leading-relaxed text-amber-600">
              {report.warnings.map((w) => (
                <p key={w} className="flex gap-1.5">
                  <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" /> {w}
                </p>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="shrink-0 text-muted">{label}</dt>
      <dd className="min-w-0 text-right break-words text-ink-soft">{children}</dd>
    </div>
  );
}
