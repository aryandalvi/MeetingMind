import { useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowRight, Clock, Cpu, Flag, Gavel, HelpCircle, ListChecks, MessagesSquare, ShieldAlert, Sparkles, Users } from "lucide-react";
import type { AnalysisReport, Person } from "../types";
import { plural } from "../lib/format";
import { Badge, Button, SectionHeader, Stat, Waveform } from "../components/ui";

const SPEAKER_BARS = ["from-violet-500 to-violet-300", "from-lime-400 to-sage-600", "from-blush-600 to-blush-400", "from-sage-600 to-lime-400", "from-violet-800 to-violet-400"];

function SpeakerAirtime({ people }: { people: Person[] }) {
  const sorted = [...people].sort((a, b) => b.talk_share - a.talk_share);
  return (
    <ul className="space-y-3.5">
      {sorted.map((p, i) => (
        <li key={p.name} title={`${p.words} words, ${p.utterances} turns`}>
          <div className="mb-1.5 flex items-baseline justify-between gap-3 text-[13px]">
            <span className="flex min-w-0 items-center gap-2">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full border border-line-strong bg-wash-2 font-mono text-[10px] text-ink-soft">
                {p.name.slice(0, 2).toUpperCase()}
              </span>
              <span className="truncate font-medium text-ink">{p.name}</span>
              <span className="hidden font-mono text-[11px] text-faint sm:inline">{p.utterances} turns</span>
            </span>
            <span className="font-mono text-[12px] text-ink-soft tabular-nums">{p.talk_share}%</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-wash-2">
            <div className={`h-full rounded-full bg-gradient-to-r ${SPEAKER_BARS[i % SPEAKER_BARS.length]}`} style={{ width: `${Math.max(2, p.talk_share)}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function Overview({ report }: { report: AnalysisReport }) {
  const s = report.stats;
  const navigate = useNavigate();
  const speakers = report.people.filter((p) => p.is_speaker);
  const totalMs = Object.values(report.timings_ms).reduce((a, b) => a + b, 0);
  const headline = report.summary.executive.find((x) => x.grounding === "supported") ?? report.summary.executive[0];
  const assigned = s.action_items ? (s.action_items - s.unassigned_action_items) / s.action_items : 0;
  const confirmed = report.decisions.filter((d) => d.status === "confirmed").length;

  return (
    <div className="space-y-6">
      <SectionHeader eyebrow="Overview" title="At a glance" description="Counts of everything MeetingMind extracted. Open any tile to review the items and their evidence." />

      <div className="relative overflow-hidden rounded-2xl border border-lavender-200 bg-surface/70 p-6 shadow-[var(--shadow-soft)] backdrop-blur-xl sm:p-7">
        <div aria-hidden="true" className="pointer-events-none absolute -top-24 -right-24 h-64 w-64 rounded-full bg-violet-500/20 blur-3xl" />
        <div aria-hidden="true" className="pointer-events-none absolute -bottom-28 left-1/3 h-56 w-56 rounded-full bg-lime-400/10 blur-3xl" />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-start">
          <div className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-violet-400 to-violet-800 text-white shadow-[var(--shadow-glow)]">
            <Sparkles className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="eyebrow mb-2 flex flex-wrap items-center gap-x-2">
              In one breath <span className="text-faint">·</span> <span className="text-muted">{report.summary.method}</span>
            </div>
            <p className="display text-[21px] leading-snug font-semibold tracking-[-0.02em] sm:text-[24px]">{headline?.text ?? "No summary could be produced."}</p>
            {headline?.evidence[0] && (
              <p className="mt-3 font-mono text-[11.5px] text-muted">
                ✓ grounded in {headline.evidence[0].speaker ?? "the transcript"}
                {headline.evidence[0].timestamp && ` @ ${headline.evidence[0].timestamp}`}
              </p>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-4 sm:flex-col sm:items-end">
            <Waveform bars={14} height={28} className="hidden sm:inline-flex" />
            <Button size="sm" onClick={() => navigate("/results/summary")}>
              Executive summary <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          label="Action items"
          value={s.action_items}
          hint={`${s.unassigned_action_items} unassigned`}
          icon={<ListChecks className="h-3.5 w-3.5 text-violet-400" />}
          accent="violet"
          meter={assigned}
          onClick={() => navigate("/results/actions")}
        />
        <Stat
          label="Decisions"
          value={s.decisions}
          hint={`${confirmed} confirmed · ${plural(report.decisions.filter((d) => d.status === "tentative").length, "tentative")}`}
          icon={<Gavel className="h-3.5 w-3.5 text-lime-400" />}
          accent="lime"
          meter={s.decisions ? confirmed / s.decisions : 0}
          onClick={() => navigate("/results/decisions")}
        />
        <Stat
          label="Risks & blockers"
          value={s.risks + s.blockers}
          hint={plural(s.blockers, "blocker")}
          icon={<ShieldAlert className="h-3.5 w-3.5 text-rose-600" />}
          accent="rose"
          onClick={() => navigate("/results/risks")}
        />
        <Stat
          label="Open questions"
          value={s.open_questions}
          hint="unresolved in the meeting"
          icon={<HelpCircle className="h-3.5 w-3.5 text-amber-600" />}
          accent="amber"
          onClick={() => navigate("/results/questions")}
        />
        <Stat label="Speakers" value={s.speaker_count} hint={s.has_speaker_labels ? "from speaker labels" : "no labels detected"} icon={<Users className="h-3.5 w-3.5 text-muted" />} />
        <Stat
          label="Words"
          value={s.word_count.toLocaleString()}
          hint={`${s.sentence_count} sentences · ${s.estimated_reading_minutes} min read`}
          icon={<MessagesSquare className="h-3.5 w-3.5 text-muted" />}
        />
        <Stat label="Duration" value={s.duration ?? "—"} hint={s.has_timestamps ? "from timestamps" : "no timestamps"} icon={<Clock className="h-3.5 w-3.5 text-muted" />} />
        <Stat label="Needs review" value={s.items_needing_review} hint="flagged for a human check" icon={<Flag className="h-3.5 w-3.5 text-amber-600" />} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <div className="card p-5 sm:p-6">
          <div className="mb-1 flex items-center justify-between gap-3">
            <div className="display text-[17px] font-semibold tracking-[-0.01em]">Speaker airtime</div>
            {speakers.length > 0 && <Badge tone="violet">{plural(speakers.length, "voice")}</Badge>}
          </div>
          <p className="mb-5 text-xs text-muted">Share of all spoken words in the transcript.</p>
          {speakers.length ? <SpeakerAirtime people={speakers} /> : <p className="text-sm text-muted">No speaker labels were detected.</p>}
        </div>
        <div className="card p-5 sm:p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="display text-[17px] font-semibold tracking-[-0.01em]">Engine telemetry</div>
            <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-lime-400">
              <span className="live-dot" /> {(totalMs / 1000).toFixed(1)} s
            </span>
          </div>
          <dl className="space-y-3 text-[13px]">
            <Row label="Summary method">
              <Badge tone="violet">{report.summary.method}</Badge>
            </Row>
            <Row label="Summarizer">{report.models.summarizer}</Row>
            <Row label="Embeddings">{report.models.embeddings}</Row>
            <Row label="Linguistics & NER">{report.models.spacy}</Row>
            <Row label="Keywords">{report.models.keywords}</Row>
          </dl>
          <div className="mt-4 flex items-center gap-2 border-t border-line pt-3 font-mono text-[11px] text-faint">
            <Cpu className="h-3.5 w-3.5" /> runs locally · no third-party AI APIs
          </div>
          {report.warnings.length > 0 && (
            <div className="mt-4 space-y-1.5 rounded-xl border border-amber-600/25 bg-amber-50 p-3 text-xs leading-relaxed text-amber-600">
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
      <dd className="min-w-0 text-right font-mono text-[12px] break-words text-ink-soft">{children}</dd>
    </div>
  );
}
