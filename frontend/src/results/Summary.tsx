import { useNavigate } from "react-router-dom";
import { Clock, Info } from "lucide-react";
import type { AnalysisReport } from "../types";
import { Badge, EmptyState, SectionHeader } from "../components/ui";
import { EvidenceList } from "../components/Evidence";

export function ExecutiveSummary({ report }: { report: AnalysisReport }) {
  const sm = report.summary;
  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Executive summary"
        title="What happened"
        description={
          sm.method === "abstractive"
            ? "Written by a dialogue summarization model, then checked against the transcript. Each sentence links to the lines that support it."
            : "Extractive summary: the most central sentences of the meeting, quoted as spoken."
        }
      />
      <div className="card p-6">
        <ul className="space-y-4">
          {sm.executive.map((s, i) => (
            <li key={i} className="flex gap-3">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-400" />
              <div className="flex-1">
                <p className="text-[15.5px] leading-relaxed text-ink">
                  {s.text}
                  {s.grounding === "weak" && (
                    <Badge tone="amber" className="ml-2 align-middle" title="Low similarity to any transcript sentence — verify before relying on it.">
                      weakly supported
                    </Badge>
                  )}
                </p>
                <div className="mt-1.5">
                  <EvidenceList evidence={s.evidence} label="Supported by" />
                </div>
              </div>
            </li>
          ))}
        </ul>
        <div className="mt-5 flex items-start gap-2 rounded-xl bg-mist p-3 text-xs leading-relaxed text-muted">
          <Info className="mt-px h-3.5 w-3.5 shrink-0" />
          <span>
            AI-generated summaries can merge or misattribute details.
            {sm.removed_unsupported > 0 && ` ${sm.removed_unsupported} generated sentence(s) mentioning names or numbers absent from the transcript were removed.`}{" "}
            Check the evidence before sharing.
          </span>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="card p-5">
          <div className="eyebrow mb-2">Decisions</div>
          <p className="text-sm leading-relaxed text-ink-soft">{sm.decision_summary}</p>
        </div>
        <div className="card p-5">
          <div className="eyebrow mb-2">Follow-ups</div>
          <p className="text-sm leading-relaxed text-ink-soft">{sm.follow_up_summary}</p>
        </div>
      </div>

      {sm.detailed.length > 0 && (
        <div className="card p-6">
          <h3 className="mb-4 font-medium text-ink">Detailed summary by topic</h3>
          <div className="space-y-5">
            {sm.detailed.map((sec) => (
              <div key={sec.topic_id}>
                <div className="mb-1.5 text-[13px] font-semibold text-violet-700">{sec.title}</div>
                <div className="space-y-2">
                  {sec.sentences.map((s, i) => (
                    <div key={i}>
                      <p className="text-sm leading-relaxed text-ink-soft">{s.text}</p>
                      <EvidenceList evidence={s.evidence} label="Source" />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function Topics({ report }: { report: AnalysisReport }) {
  const navigate = useNavigate();
  if (!report.topics.length) return <EmptyState title="No topics found" />;
  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Discussion topics"
        title="How the conversation moved"
        description="Segments found where the meaning of consecutive sentences shifts (and at agenda phrases like “moving on to…”), labelled with their keyphrases."
      />
      <ol className="relative space-y-4 border-l border-lavender-200 pl-6">
        {report.topics.map((t, i) => (
          <li key={t.id} className="relative">
            <span className="display absolute top-4 -left-[37px] grid h-7 w-7 place-items-center rounded-full border border-lavender-200 bg-surface text-sm text-violet-600">
              {i + 1}
            </span>
            <div className="card p-5">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-[17px] font-semibold text-ink">{t.title}</h3>
                {t.start_timestamp && (
                  <span className="inline-flex items-center gap-1 text-xs text-faint">
                    <Clock className="h-3 w-3" /> {t.start_timestamp}
                    {t.end_timestamp && t.end_timestamp !== t.start_timestamp && `–${t.end_timestamp}`}
                  </span>
                )}
                <span className="text-xs text-faint">· {t.sentence_ids.length} sentences</span>
              </div>
              {t.summary && <p className="mt-2 text-sm leading-relaxed text-ink-soft">{t.summary}</p>}
              {t.key_points.length > 0 && (
                <div className="mt-3">
                  <div className="mb-1.5 text-xs font-medium text-muted">Key points</div>
                  <ul className="space-y-1.5">
                    {t.key_points.map((kp) => (
                      <li key={kp.text}>
                        <button
                          onClick={() => navigate(`/results/evidence?s=${kp.evidence[0]?.sentence_id}`)}
                          className="w-full rounded-lg bg-lavender-50/60 px-3 py-1.5 text-left text-[13px] text-ink-soft hover:bg-lavender-50"
                        >
                          {kp.evidence[0]?.speaker && <span className="mr-1.5 text-[11px] font-semibold text-violet-600">{kp.evidence[0].speaker}</span>}
                          {kp.text}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {t.keywords.map((k) => (
                  <Badge key={k} tone="blush">
                    {k}
                  </Badge>
                ))}
                {t.speakers.map((sp) => (
                  <Badge key={sp}>{sp}</Badge>
                ))}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
