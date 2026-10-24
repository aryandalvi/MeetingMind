import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Ban, CalendarClock, CheckCircle2, CircleDashed, Flag, Gavel, HelpCircle, ShieldAlert, Signpost } from "lucide-react";
import type { AnalysisReport, Decision, Priority } from "../types";
import { daysFrom, formatDate, relativeLabel } from "../lib/format";
import { Badge, cx, EmptyState, SectionHeader, SignalBadge } from "../components/ui";
import { EvidenceList } from "../components/Evidence";

function Filters<T extends string>({ options, value, onChange }: { options: { key: T; label: string; count: number }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter">
      {options.map((o) => (
        <button
          key={o.key}
          onClick={() => onChange(o.key)}
          aria-pressed={value === o.key}
          className={cx(
            "rounded-full border px-3 py-1 text-xs transition",
            value === o.key ? "border-lavender-300 bg-lavender-100 font-medium text-ink" : "border-line bg-wash-1 text-muted hover:text-ink",
          )}
        >
          {o.label} <span className="text-faint">{o.count}</span>
        </button>
      ))}
    </div>
  );
}

function ReviewNote({ reasons }: { reasons: string[] }) {
  if (!reasons.length) return null;
  return (
    <div className="mt-2 flex items-start gap-1.5 rounded-lg border border-amber-600/25 bg-amber-50 px-2.5 py-1.5 text-xs text-amber-600">
      <Flag className="mt-px h-3.5 w-3.5 shrink-0" />
      <span>{reasons.join(" ")}</span>
    </div>
  );
}

const DECISION_STYLE: Record<Decision["status"], { tone: "sage" | "amber" | "rose"; icon: ReactNode; label: string }> = {
  confirmed: { tone: "sage", icon: <CheckCircle2 className="h-3 w-3" />, label: "Confirmed" },
  tentative: { tone: "amber", icon: <CircleDashed className="h-3 w-3" />, label: "Tentative" },
  rejected: { tone: "rose", icon: <Ban className="h-3 w-3" />, label: "Rejected" },
};

export function Decisions({ report }: { report: AnalysisReport }) {
  const [filter, setFilter] = useState<"all" | Decision["status"]>("all");
  const items = report.decisions.filter((d) => filter === "all" || d.status === filter);
  const count = (s: Decision["status"]) => report.decisions.filter((d) => d.status === s).length;
  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Decisions"
        title="What was settled"
        description="Explicit decisions, approvals and agreements. Suggestions, hypotheticals and open questions are deliberately excluded."
        actions={
          <Filters
            value={filter}
            onChange={setFilter}
            options={[
              { key: "all", label: "All", count: report.decisions.length },
              { key: "confirmed", label: "Confirmed", count: count("confirmed") },
              { key: "tentative", label: "Tentative", count: count("tentative") },
              { key: "rejected", label: "Rejected", count: count("rejected") },
            ]}
          />
        }
      />
      {items.length === 0 ? (
        <EmptyState icon={<Gavel className="h-5 w-5" />} title="No decisions here">
          No sentence clearly stated a decision{filter !== "all" ? " with this status" : ""}.
        </EmptyState>
      ) : (
        items.map((d) => {
          const st = DECISION_STYLE[d.status];
          return (
            <article key={d.id} className="card p-5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={st.tone}>
                  {st.icon} {st.label}
                </Badge>
                {d.kind !== "decision" && <Badge tone="violet">{d.kind}</Badge>}
                {d.is_inferred && <Badge title="Inferred from a proposal followed by agreement, not stated as a decision.">inferred</Badge>}
                <SignalBadge signal={d.signal} />
                {d.speaker && <span className="ml-auto text-xs text-muted">raised by {d.speaker}</span>}
              </div>
              <p className="mt-3 text-[15.5px] font-medium text-ink">{d.text}</p>
              <ReviewNote reasons={d.review_reasons} />
              <div className="mt-3">
                <EvidenceList evidence={d.evidence} defaultOpen />
              </div>
            </article>
          );
        })
      )}
    </div>
  );
}

export function Deadlines({ report }: { report: AnalysisReport }) {
  const navigate = useNavigate();
  const base = report.meeting.date;
  const actions = new Map(report.action_items.map((a) => [a.id, a]));
  if (!report.deadlines.length)
    return (
      <div className="space-y-5">
        <SectionHeader eyebrow="Deadlines" title="Dates that matter" />
        <EmptyState icon={<CalendarClock className="h-5 w-5" />} title="No deadlines mentioned">MeetingMind never invents dates; none were stated.</EmptyState>
      </div>
    );
  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Deadlines"
        title="Dates that matter"
        description={
          base
            ? `Relative expressions were resolved against the meeting date (${formatDate(base)}). Ambiguous or approximate dates are flagged.`
            : "No meeting date was given, so relative expressions were left unresolved."
        }
      />
      <div className="card divide-y divide-line">
        {report.deadlines.map((d, i) => {
          const action = d.related_action_id ? actions.get(d.related_action_id) : undefined;
          return (
            <div key={`${d.id}-${i}`} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start">
              <div className="w-36 shrink-0">
                {d.normalized_date ? (
                  <>
                    <div className="font-semibold text-ink">{formatDate(d.normalized_date, { weekday: "short" })}</div>
                    <div className="text-xs text-faint">{relativeLabel(daysFrom(base, d.normalized_date))}</div>
                  </>
                ) : (
                  <div className="font-medium text-amber-600">Unresolved</div>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm text-ink">“{d.text}”</span>
                  <Badge tone={d.date_type === "explicit" ? "violet" : d.date_type === "user" ? "blush" : "gray"}>{d.date_type}</Badge>
                  {d.granularity !== "day" && <Badge>{d.granularity}-level</Badge>}
                  {d.is_ambiguous && (
                    <Badge tone="amber">
                      <AlertTriangle className="h-3 w-3" /> review
                    </Badge>
                  )}
                </div>
                {action && (
                  <button onClick={() => navigate("/results/actions")} className="mt-1 text-left text-sm text-violet-600 hover:underline">
                    {action.id} · {action.description} — {action.owner}
                  </button>
                )}
                {d.note && <p className="mt-1 text-xs text-muted">{d.note}</p>}
                {d.evidence.length > 0 && (
                  <div className="mt-2">
                    <EvidenceList evidence={d.evidence} />
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const SEVERITY_TONE: Record<Priority, "rose" | "amber" | "gray"> = { high: "rose", medium: "amber", low: "gray" };

export function Risks({ report }: { report: AnalysisReport }) {
  const [filter, setFilter] = useState<"all" | "risk" | "blocker">("all");
  const items = report.risks.filter((r) => filter === "all" || r.kind === filter);
  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Risks & blockers"
        title="What could go wrong"
        description="Concerns, problems and dependencies raised in the meeting. Severity is a heuristic from the wording (e.g. “critical”, “launch”, “security”)."
        actions={
          <Filters
            value={filter}
            onChange={setFilter}
            options={[
              { key: "all", label: "All", count: report.risks.length },
              { key: "blocker", label: "Blockers", count: report.risks.filter((r) => r.kind === "blocker").length },
              { key: "risk", label: "Risks", count: report.risks.filter((r) => r.kind === "risk").length },
            ]}
          />
        }
      />
      {items.length === 0 ? (
        <EmptyState icon={<ShieldAlert className="h-5 w-5" />} title="Nothing flagged">No risk or blocker statements were detected.</EmptyState>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((r) => (
            <article key={r.id} className={cx("card p-5", r.kind === "blocker" && "border-l-4 border-l-blush-400")}>
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={r.kind === "blocker" ? "blush" : "violet"}>{r.kind}</Badge>
                <Badge tone={SEVERITY_TONE[r.severity]}>{r.severity} severity</Badge>
                <SignalBadge signal={r.signal} />
              </div>
              <p className="mt-3 text-[15px] leading-relaxed text-ink">{r.text}</p>
              {r.speaker && <p className="mt-1 text-xs text-muted">— {r.speaker}</p>}
              <ReviewNote reasons={r.review_reasons} />
              <div className="mt-3">
                <EvidenceList evidence={r.evidence} />
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

const Q_LABEL = { unanswered: "No answer given", deferred: "Deferred", open_issue: "Open issue" } as const;

export function Questions({ report }: { report: AnalysisReport }) {
  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Unresolved questions"
        title="Still open"
        description="Questions nobody answered, answers that were deferred (“I'll get back to you”), and issues explicitly left open. Answered questions are not listed."
      />
      {report.questions.length === 0 ? (
        <EmptyState icon={<HelpCircle className="h-5 w-5" />} title="No open questions">Every substantive question appears to have been answered.</EmptyState>
      ) : (
        report.questions.map((q) => (
          <article key={q.id} className="card p-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={q.status === "unanswered" ? "rose" : q.status === "deferred" ? "amber" : "violet"}>{Q_LABEL[q.status]}</Badge>
              {q.asked_by && <span className="text-xs text-muted">asked by {q.asked_by}</span>}
            </div>
            <p className="mt-3 text-[15.5px] font-medium text-ink">{q.text}</p>
            {q.note && <p className="mt-1 text-xs text-muted">{q.note}</p>}
            <div className="mt-3 space-y-2">
              <EvidenceList evidence={q.evidence} />
              {q.response_evidence.length > 0 && <EvidenceList evidence={q.response_evidence} label="Replies" />}
            </div>
          </article>
        ))
      )}
    </div>
  );
}

export function NextSteps({ report }: { report: AnalysisReport }) {
  const navigate = useNavigate();
  const sectionFor = (id: string) =>
    id.startsWith("DEC") ? "decisions" : id.startsWith("A") ? "actions" : id.startsWith("R") ? "risks" : id.startsWith("Q") ? "questions" : "overview";
  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Recommended next steps"
        title="Where to go from here"
        description="Suggestions generated by MeetingMind from the extracted items (they were not said in the meeting). Each one explains why it is recommended."
      />
      {report.next_steps.length === 0 ? (
        <EmptyState icon={<Signpost className="h-5 w-5" />} title="Nothing to recommend">All items have owners and dates, and nothing was left open.</EmptyState>
      ) : (
        <div className="card divide-y divide-line">
          {report.next_steps.map((n) => (
            <div key={n.id} className="flex gap-4 p-4">
              <Badge tone={SEVERITY_TONE[n.priority]} className="mt-0.5 h-fit">
                {n.priority}
              </Badge>
              <div className="min-w-0 flex-1">
                <p className="text-[15px] font-medium text-ink">{n.text}</p>
                <p className="mt-0.5 text-sm text-muted">{n.rationale}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {n.related_ids.slice(0, 6).map((id) => (
                    <button key={id} onClick={() => navigate(`/results/${sectionFor(id)}`)} className="rounded-md bg-lavender-50 px-1.5 py-0.5 text-[11px] font-medium text-violet-700 hover:bg-lavender-100">
                      {id}
                    </button>
                  ))}
                  {n.evidence.length > 0 && <EvidenceList evidence={n.evidence} label="Based on" />}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
