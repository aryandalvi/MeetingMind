import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Search } from "lucide-react";
import type { AnalysisReport } from "../types";
import { cx, SectionHeader } from "../components/ui";

type Kind = "action" | "decision" | "risk" | "question" | "summary";
const KIND_STYLE: Record<Kind, { label: string; cls: string; mark: string }> = {
  action: { label: "Action", cls: "bg-lavender-100 text-violet-300", mark: "decoration-violet-400" },
  decision: { label: "Decision", cls: "bg-sage-50 text-sage-600", mark: "decoration-sage-600" },
  risk: { label: "Risk", cls: "bg-blush-100 text-blush-600", mark: "decoration-blush-400" },
  question: { label: "Question", cls: "bg-amber-50 text-amber-600", mark: "decoration-amber-600" },
  summary: { label: "Summary", cls: "bg-wash-2 text-muted border border-line", mark: "decoration-faint" },
};

/** The full transcript, with every sentence that supports an extracted item tagged. */
export function TranscriptEvidence({ report }: { report: AnalysisReport }) {
  const [params] = useSearchParams();
  const focus = params.get("s");
  const [query, setQuery] = useState("");
  const [only, setOnly] = useState<"all" | Kind>("all");

  const tags = useMemo(() => {
    const m = new Map<string, { kind: Kind; id: string }[]>();
    const add = (kind: Kind, id: string, sids: string[]) =>
      sids.forEach((sid) => m.set(sid, [...(m.get(sid) ?? []).filter((t) => t.id !== id), { kind, id }]));
    report.action_items.forEach((a) => add("action", a.id, a.evidence.map((e) => e.sentence_id)));
    report.decisions.forEach((d) => add("decision", d.id, d.evidence.map((e) => e.sentence_id)));
    report.risks.forEach((r) => add("risk", r.id, r.evidence.map((e) => e.sentence_id)));
    report.questions.forEach((q) => add("question", q.id, q.evidence.map((e) => e.sentence_id)));
    report.summary.executive.forEach((s, i) => add("summary", `S${i + 1}`, s.evidence.map((e) => e.sentence_id)));
    return m;
  }, [report]);

  const sentences = useMemo(() => new Map(report.sentences.map((s) => [s.id, s])), [report]);

  useEffect(() => {
    if (!focus) return;
    const el = document.getElementById(`sent-${focus}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.remove("hl-pulse");
      void el.offsetWidth;
      el.classList.add("hl-pulse");
    }
  }, [focus]);

  const q = query.trim().toLowerCase();
  const counts = (k: Kind) => [...tags.values()].filter((t) => t.some((x) => x.kind === k)).length;

  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Transcript evidence"
        title="Every claim, traced to its source"
        description="The transcript as MeetingMind parsed it. Underlined sentences support an extracted item; the tags say which. Click “Evidence” anywhere in the report to jump here."
      />
      <div className="card flex flex-col gap-3 p-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-faint" />
          <input className="field h-9 pl-9" placeholder="Search the transcript" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search transcript" />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {(["all", "action", "decision", "risk", "question", "summary"] as const).map((k) => (
            <button
              key={k}
              onClick={() => setOnly(k)}
              aria-pressed={only === k}
              className={cx("rounded-full border px-3 py-1 text-xs transition", only === k ? "border-lavender-300 bg-lavender-100 font-medium text-ink" : "border-line text-muted hover:text-ink")}
            >
              {k === "all" ? "Everything" : KIND_STYLE[k].label} {k !== "all" && <span className="text-faint">{counts(k)}</span>}
            </button>
          ))}
        </div>
      </div>

      <div className="card divide-y divide-line">
        {report.utterances.map((u) => {
          const sents = u.sentence_ids.map((id) => sentences.get(id)).filter(Boolean) as typeof report.sentences;
          const matches = sents.filter((s) => (!q || s.text.toLowerCase().includes(q)) && (only === "all" || tags.get(s.id)?.some((t) => t.kind === only)));
          if ((q || only !== "all") && matches.length === 0) return null;
          return (
            <div key={u.id} className="grid gap-1 px-5 py-3.5 sm:grid-cols-[150px_1fr] sm:gap-4">
              <div className="text-[13px]">
                <div className="font-semibold text-ink">{u.speaker ?? "—"}</div>
                {u.timestamp && <div className="font-mono text-[11px] text-lime-400/80 tabular-nums">{u.timestamp}</div>}
              </div>
              <p className="text-[14px] leading-7 text-ink-soft">
                {sents.map((s) => {
                  const t = tags.get(s.id) ?? [];
                  const shown = only === "all" ? t : t.filter((x) => x.kind === only);
                  const dim = (q && !s.text.toLowerCase().includes(q)) || (only !== "all" && shown.length === 0);
                  return (
                    <span key={s.id} id={`sent-${s.id}`} className={cx("scroll-mt-32 rounded px-0.5", dim && "opacity-40")}>
                      <span className={cx(shown.length > 0 && "underline decoration-2 underline-offset-4", shown[0] && KIND_STYLE[shown[0].kind].mark)}>{s.text}</span>
                      {shown.map((x) => (
                        <span key={x.id} className={cx("ml-1 inline-block rounded px-1 align-[2px] text-[10px] leading-4 font-semibold", KIND_STYLE[x.kind].cls)}>
                          {x.id}
                        </span>
                      ))}{" "}
                    </span>
                  );
                })}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
