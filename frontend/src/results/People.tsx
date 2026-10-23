import { useMemo } from "react";
import { Mic, Tags } from "lucide-react";
import type { AnalysisReport } from "../types";
import { Badge, EmptyState, SectionHeader } from "../components/ui";
import { EvidenceList } from "../components/Evidence";
import { KeywordChart, TalkShareChart } from "./charts";

function initials(name: string) {
  return name
    .replace(/^(dr|mr|mrs|ms|prof|nurse)\.?\s+/i, "")
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

export function PeopleEntities({ report }: { report: AnalysisReport }) {
  const speakers = report.people.filter((p) => p.is_speaker);
  const mentioned = report.people.filter((p) => !p.is_speaker);
  const groups = useMemo(() => {
    const g = new Map<string, typeof report.entities>();
    for (const e of report.entities) {
      if (e.label === "PERSON") continue;
      const key = e.label_description || e.label;
      g.set(key, [...(g.get(key) ?? []), e]);
    }
    return [...g.entries()];
  }, [report]);

  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="People & entities"
        title="Who and what was mentioned"
        description="Speakers come from transcript labels; organisations, places, dates and other entities come from spaCy named-entity recognition (the small English model can mislabel some names)."
      />
      {speakers.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <div className="card divide-y divide-line">
            {speakers.map((p) => (
              <div key={p.name} className="flex items-center gap-3 p-4">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-blush-100 text-sm font-semibold text-blush-600">{initials(p.name)}</span>
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-ink">{p.name}</div>
                  <div className="text-xs text-muted">
                    {p.utterances} turns · {p.words.toLocaleString()} words · {p.talk_share}% of the conversation
                  </div>
                </div>
                <Badge tone={p.action_items ? "violet" : "gray"}>{p.action_items} action items</Badge>
              </div>
            ))}
          </div>
          <div className="card p-5">
            <div className="mb-3 flex items-center gap-2 font-medium text-ink">
              <Mic className="h-4 w-4 text-violet-500" /> Share of words
            </div>
            <TalkShareChart people={speakers} />
          </div>
        </div>
      )}
      {mentioned.length > 0 && (
        <div className="card p-5">
          <div className="mb-2 text-sm font-medium text-ink">People mentioned but not speaking</div>
          <div className="flex flex-wrap gap-2">
            {mentioned.map((p) => (
              <Badge key={p.name} tone="blush">
                {p.name} · {p.mentions}×
              </Badge>
            ))}
          </div>
        </div>
      )}
      {groups.length === 0 ? (
        <EmptyState title="No other named entities found" />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {groups.map(([label, ents]) => (
            <div key={label} className="card p-5">
              <div className="eyebrow mb-3">{label}</div>
              <ul className="space-y-3">
                {ents.map((e) => (
                  <li key={e.text}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-ink">{e.text}</span>
                      <span className="text-xs text-faint">{e.count}×</span>
                    </div>
                    <EvidenceList evidence={e.evidence} label="Mentions" />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function Keywords({ report }: { report: AnalysisReport }) {
  if (!report.keywords.length)
    return <EmptyState icon={<Tags className="h-5 w-5" />} title="No keywords extracted">The transcript may be too short.</EmptyState>;
  const max = Math.max(...report.keywords.map((k) => k.mentions));
  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Keywords"
        title="The vocabulary of the meeting"
        description="Candidates from YAKE and spaCy noun phrases, re-ranked KeyBERT-style by embedding similarity to the whole meeting, with Maximal Marginal Relevance for variety."
      />
      <div className="card flex flex-wrap items-baseline gap-2.5 p-6">
        {report.keywords.map((k) => {
          const weight = 0.4 + 0.6 * (1 - (k.rank - 1) / report.keywords.length);
          return (
            <span
              key={k.phrase}
              className="rounded-full border border-lavender-200 bg-lavender-50 px-3 py-1 text-violet-700"
              style={{ fontSize: `${12 + weight * 8}px` }}
              title={`Rank ${k.rank} · ${k.mentions} mention(s)`}
            >
              {k.phrase}
            </span>
          );
        })}
      </div>
      <div className="card p-5">
        <div className="mb-1 font-medium text-ink">Mentions of the top keyphrases</div>
        <p className="mb-3 text-xs text-muted">Exact occurrences in the transcript (most frequent: {max}).</p>
        <KeywordChart keywords={report.keywords} />
      </div>
    </div>
  );
}
