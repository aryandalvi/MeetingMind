import { useEffect, useRef, useState } from "react";
import { Braces, ChevronDown, Download, FileText, FileType2, Sheet } from "lucide-react";
import { api } from "../api/client";
import type { AnalysisReport, ExportFormat } from "../types";
import { Button } from "./ui";

const OPTIONS: { format: ExportFormat; label: string; hint: string; icon: typeof Braces }[] = [
  { format: "pdf", label: "PDF meeting minutes", hint: "Formatted minutes to share", icon: FileType2 },
  { format: "markdown", label: "Markdown report", hint: "Full report with evidence", icon: FileText },
  { format: "csv", label: "CSV action items", hint: "For spreadsheets & trackers", icon: Sheet },
  { format: "json", label: "JSON", hint: "Complete structured data", icon: Braces },
];

export function ExportMenu({ report }: { report: AnalysisReport }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  async function run(format: ExportFormat) {
    setBusy(format);
    setError(null);
    try {
      await api.exportReport(format, report);
      setOpen(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="relative" ref={ref}>
      <Button icon={<Download className="h-4 w-4" />} onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open}>
        Export
        <ChevronDown className="h-4 w-4 opacity-80" />
      </Button>
      {open && (
        <div role="menu" className="absolute right-0 z-30 mt-2 w-72 rounded-2xl border border-line-strong bg-surface-2/95 p-1.5 shadow-[var(--shadow-lift)] backdrop-blur-xl">
          {OPTIONS.map(({ format, label, hint, icon: Icon }) => (
            <button
              key={format}
              role="menuitem"
              onClick={() => run(format)}
              disabled={busy !== null}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition hover:bg-wash-2 disabled:opacity-60"
            >
              <span className="grid h-8 w-8 place-items-center rounded-lg border border-lavender-200 bg-lavender-50 text-violet-400">
                <Icon className="h-4 w-4" />
              </span>
              <span className="flex-1">
                <span className="block text-sm font-medium text-ink">{busy === format ? "Preparing…" : label}</span>
                <span className="block text-xs text-muted">{hint}</span>
              </span>
            </button>
          ))}
          <p className="px-3 pt-1.5 pb-1 font-mono text-[10.5px] text-faint">Exports include your latest edits.</p>
          {error && <p className="px-3 pb-2 text-xs text-rose-600">{error}</p>}
        </div>
      )}
    </div>
  );
}
