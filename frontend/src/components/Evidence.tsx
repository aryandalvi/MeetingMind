import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Quote } from "lucide-react";
import type { Evidence } from "../types";
import { cx } from "./ui";

/** Transcript quotes that support an extracted item, with a jump to the full transcript. */
export function EvidenceList({ evidence, defaultOpen = false, label = "Evidence" }: { evidence: Evidence[]; defaultOpen?: boolean; label?: string }) {
  const [open, setOpen] = useState(defaultOpen);
  const navigate = useNavigate();
  if (!evidence.length) {
    return <div className="text-xs text-faint italic">No transcript evidence (added manually).</div>;
  }
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1 font-mono text-[11.5px] font-medium text-violet-400 hover:text-violet-300"
        aria-expanded={open}
      >
        <Quote className="h-3.5 w-3.5" />
        {label} ({evidence.length})
        <ChevronDown className={cx("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <ul className="mt-2 space-y-1.5">
          {evidence.map((e) => (
            <li key={e.sentence_id}>
              <button
                type="button"
                onClick={() => navigate(`/results/evidence?s=${e.sentence_id}`)}
                className="group w-full rounded-xl border-l-2 border-lime-400/50 bg-wash-1 px-3 py-2 text-left text-[13px] leading-relaxed text-ink-soft transition hover:border-lime-400 hover:bg-wash-2"
                title="Show in transcript"
              >
                <span className="mr-1.5 font-mono text-[11px] font-medium text-lime-400">
                  {e.timestamp && <span className="mr-1 font-normal text-faint">{e.timestamp}</span>}
                  {e.speaker ?? "Transcript"}
                </span>
                “{e.text}”
                <span className="ml-1.5 text-[11px] text-faint opacity-0 transition group-hover:opacity-100">view in transcript →</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
