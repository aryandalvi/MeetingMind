import { useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, FileUp, Info, Quote, RotateCcw, Wand2, X } from "lucide-react";
import { api } from "../api/client";
import { useWorkspace } from "../state/workspace";
import { SAMPLE } from "../lib/sample";
import { plural, wordCount } from "../lib/format";
import { Badge, Button, cx } from "../components/ui";
import { ConfirmDialog } from "../components/ConfirmDialog";

const MIN_WORDS = 15;
const MAX_CHARS = 300_000;
const ACCEPT = ".txt,.md,.vtt,.srt,.docx,.pdf";

export function NewAnalysis() {
  const navigate = useNavigate();
  const { draft, setDraft, startJob, report } = useWorkspace();
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [confirmReplace, setConfirmReplace] = useState(false);
  const [touched, setTouched] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const words = wordCount(draft.transcript);
  const chars = draft.transcript.length;
  const speakerLines = (draft.transcript.match(/^\s*(?:\[?[\d:.]+\]?\s*)?[A-Z][\w.' -]{0,40}:\s+\S/gm) ?? []).length;
  const problem =
    !draft.transcript.trim()
      ? "Add a transcript to analyse."
      : words < MIN_WORDS
        ? `The transcript is too short (${words} words; at least ${MIN_WORDS} are needed).`
        : chars > MAX_CHARS
          ? `The transcript is too long (${chars.toLocaleString()} characters; the limit is ${MAX_CHARS.toLocaleString()}).`
          : null;

  async function handleFile(file: File) {
    setUploadError(null);
    setUploading(true);
    try {
      const res = await api.extract(file);
      setDraft({
        transcript: res.text,
        file: { filename: res.filename, file_type: res.file_type, pages: res.pages, warnings: res.warnings, word_count: res.word_count },
        title: draft.title || res.filename.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " "),
      });
    } catch (e) {
      setUploadError((e as Error).message);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  function analyze() {
    setTouched(true);
    if (problem) return;
    if (report) {
      setConfirmReplace(true);
      return;
    }
    go();
  }

  function go() {
    startJob({
      transcript: draft.transcript,
      title: draft.title.trim() || "Untitled meeting",
      meeting_date: draft.date || null,
      context: draft.context.trim() || null,
    });
    navigate("/processing");
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
      <div className="mb-8 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="eyebrow mb-1.5">New analysis</div>
          <h1 className="display text-[40px] leading-tight">What was the meeting about?</h1>
          <p className="mt-1 text-sm text-muted">Paste a transcript or upload a file. Nothing is saved — the text is only used for this analysis.</p>
        </div>
        <Button variant="secondary" icon={<Quote className="h-4 w-4" />} onClick={() => setDraft({ ...SAMPLE, file: null })}>
          Load sample transcript
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <aside className="space-y-4">
          <div className="card space-y-4 p-5">
            <div>
              <label className="label" htmlFor="title">Meeting title</label>
              <input id="title" className="field" placeholder="e.g. Sprint 14 planning" value={draft.title} maxLength={200} onChange={(e) => setDraft({ title: e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="date">Meeting date</label>
              <input id="date" type="date" className="field" value={draft.date} onChange={(e) => setDraft({ date: e.target.value })} />
              <p className="mt-1.5 text-xs text-faint">Used to turn “next Friday” or “end of month” into calendar dates.</p>
            </div>
            <div>
              <label className="label" htmlFor="context">
                Project / team context <span className="font-normal text-faint">(optional)</span>
              </label>
              <textarea id="context" rows={3} maxLength={1000} className="field resize-none" placeholder="e.g. Mobile team, v2 launch" value={draft.context} onChange={(e) => setDraft({ context: e.target.value })} />
            </div>
          </div>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={cx(
              "card flex flex-col items-center border-dashed px-5 py-7 text-center transition",
              dragging ? "border-violet-400 bg-lavender-50" : "border-line-strong",
            )}
          >
            <div className="mb-3 grid h-11 w-11 place-items-center rounded-2xl bg-blush-50 text-blush-600">
              <FileUp className="h-5 w-5" />
            </div>
            <div className="text-sm font-medium text-ink">Drop a file here</div>
            <div className="mt-0.5 text-xs text-muted">TXT, DOCX, text-based PDF, VTT or SRT · up to 10 MB</div>
            <Button variant="secondary" size="sm" className="mt-4" loading={uploading} onClick={() => fileInput.current?.click()}>
              {uploading ? "Extracting text…" : "Choose file"}
            </Button>
            <input ref={fileInput} type="file" accept={ACCEPT} className="hidden" onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
            {uploadError && (
              <p className="mt-3 flex items-start gap-1.5 text-left text-xs text-rose-600">
                <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" /> {uploadError}
              </p>
            )}
          </div>

          <div className="rounded-2xl border border-line bg-lavender-50/60 p-4 text-xs leading-relaxed text-ink-soft">
            <div className="mb-1 flex items-center gap-1.5 font-medium text-violet-700">
              <Info className="h-3.5 w-3.5" /> Best results
            </div>
            Use one line per speaker turn, like <code className="rounded bg-surface px-1">Priya: I'll send it Friday.</code> Timestamps such as{" "}
            <code className="rounded bg-surface px-1">[00:12:03]</code> are fine. Without speaker labels, owners can only come from names in the text.
          </div>
        </aside>

        <section className="card flex min-h-[560px] flex-col">
          {draft.file && (
            <div className="flex flex-wrap items-center gap-2 border-b border-line px-5 py-3 text-sm">
              <Badge tone="violet">{draft.file.file_type.toUpperCase()}</Badge>
              <span className="font-medium text-ink">{draft.file.filename}</span>
              <span className="text-xs text-muted">
                {plural(draft.file.word_count, "word")} extracted{draft.file.pages ? ` from ${plural(draft.file.pages, "page")}` : ""} — review the preview below, you can edit it
              </span>
              <button className="ml-auto text-faint hover:text-ink" onClick={() => setDraft({ file: null })} aria-label="Dismiss file info">
                <X className="h-4 w-4" />
              </button>
              {draft.file.warnings.map((w) => (
                <p key={w} className="flex w-full items-start gap-1.5 text-xs text-amber-600">
                  <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" /> {w}
                </p>
              ))}
            </div>
          )}
          <label htmlFor="transcript" className="sr-only">Transcript</label>
          <textarea
            id="transcript"
            value={draft.transcript}
            onChange={(e) => setDraft({ transcript: e.target.value })}
            placeholder={"Priya: Okay, let's get started. The main thing today is the launch.\nMarcus: QA found three critical bugs, so I'm worried about March 10.\nPriya: Marcus, can you fix the checkout crash by Thursday?\nMarcus: Sure, I'll have it done by Thursday."}
            className="min-h-[420px] flex-1 resize-y rounded-t-2xl bg-transparent px-5 py-4 font-mono text-[13px] leading-relaxed text-ink placeholder:text-faint focus:outline-none"
            spellCheck={false}
          />
          <div className="flex flex-col gap-3 border-t border-line px-5 py-3.5 sm:flex-row sm:items-center">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
              <span>
                <b className="font-semibold text-ink">{words.toLocaleString()}</b> words
              </span>
              <span>{chars.toLocaleString()} characters</span>
              {words > 0 && <span>{speakerLines > 0 ? `${plural(speakerLines, "speaker line")} detected` : "No speaker labels detected"}</span>}
              {words > 4000 && <span className="text-amber-600">Long transcript — analysis may take a few minutes on CPU</span>}
            </div>
            <div className="flex gap-2 sm:ml-auto">
              <Button variant="ghost" icon={<RotateCcw className="h-4 w-4" />} disabled={!draft.transcript && !draft.title && !draft.context} onClick={() => setDraft({ transcript: "", title: "", context: "", file: null })}>
                Clear
              </Button>
              <Button icon={<Wand2 className="h-4 w-4" />} onClick={analyze} disabled={uploading}>
                Analyze meeting
              </Button>
            </div>
          </div>
          {touched && problem && (
            <p className="flex items-center gap-1.5 px-5 pb-3.5 text-xs text-rose-600">
              <AlertTriangle className="h-3.5 w-3.5" /> {problem}
            </p>
          )}
        </section>
      </div>

      <ConfirmDialog
        open={confirmReplace}
        title="Replace the current report?"
        confirmLabel="Analyze and replace"
        tone="primary"
        onCancel={() => setConfirmReplace(false)}
        onConfirm={() => {
          setConfirmReplace(false);
          go();
        }}
      >
        You already have a report for “{report?.meeting.title}”. It is not saved anywhere, so export it first if you need it, including your edits.
      </ConfirmDialog>
    </div>
  );
}
