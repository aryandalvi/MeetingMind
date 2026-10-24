import { useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, FileUp, Info, Quote, RotateCcw, Sparkles, Wand2, X } from "lucide-react";
import { api } from "../api/client";
import { useWorkspace } from "../state/workspace";
import { SAMPLE } from "../lib/sample";
import { plural, wordCount } from "../lib/format";
import { Badge, Button, cx, Sparkle, Waveform } from "../components/ui";
import { ConfirmDialog } from "../components/ConfirmDialog";

const MIN_WORDS = 15;
const MAX_CHARS = 300_000;
const ACCEPT = ".txt,.md,.vtt,.srt,.docx,.pdf";

// A small illustrative line of dialogue, tagged the way MeetingMind would tag it — shown as a
// "ghost" preview inside the empty editor so the blank box demonstrates the product instead of
// just sitting there. Mirrors the tag language used on the real Transcript evidence page.
type Kind = "risk" | "action" | "decision";
const TAG_STYLE: Record<Kind, { label: string; text: string; mark: string }> = {
  risk: { label: "Risk", text: "text-blush-600", mark: "decoration-blush-400" },
  action: { label: "Action", text: "text-violet-400", mark: "decoration-violet-400" },
  decision: { label: "Decision", text: "text-sage-600", mark: "decoration-sage-600" },
};
const GHOST_LINES: { speaker: string; parts: { text: string; tag?: Kind }[] }[] = [
  { speaker: "Priya", parts: [{ text: "Okay, let's get started. The main thing today is the launch." }] },
  { speaker: "Marcus", parts: [{ text: "QA found three critical bugs, so " }, { text: "I'm worried about March 10", tag: "risk" }, { text: "." }] },
  { speaker: "Priya", parts: [{ text: "Marcus, can you " }, { text: "fix the checkout crash by Thursday", tag: "action" }, { text: "?" }] },
  { speaker: "Marcus", parts: [{ text: "Sure, " }, { text: "I'll have it done by Thursday", tag: "action" }, { text: "." }] },
  { speaker: "Priya", parts: [{ text: "Alright, " }, { text: "let's move the launch to March 17", tag: "decision" }, { text: "." }] },
];

function GhostPreview() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden px-5 py-4">
      <p className="font-mono text-[13px] leading-relaxed text-faint/80">
        {GHOST_LINES.map((line, i) => (
          <span key={i} className="block">
            <span className="text-violet-400/70">{line.speaker}: </span>
            {line.parts.map((p, j) =>
              p.tag ? (
                <span key={j} className={cx("underline decoration-2 underline-offset-4", TAG_STYLE[p.tag].text, TAG_STYLE[p.tag].mark)}>
                  {p.text}
                </span>
              ) : (
                <span key={j}>{p.text}</span>
              ),
            )}
          </span>
        ))}
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 font-mono text-[11px] text-faint">
        <span className="inline-flex items-center gap-1 text-faint/80">
          <Sparkle size={11} className="text-violet-400" /> this is a preview — start typing or paste your own
        </span>
        {(Object.keys(TAG_STYLE) as Kind[]).map((k) => (
          <span key={k} className={cx("inline-flex items-center gap-1", TAG_STYLE[k].text)}>
            <span className="h-1.5 w-1.5 rounded-full bg-current" /> {TAG_STYLE[k].label}
          </span>
        ))}
      </div>
    </div>
  );
}

function PageGlow() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-[linear-gradient(var(--color-grid-line)_1px,transparent_1px),linear-gradient(90deg,var(--color-grid-line)_1px,transparent_1px)] bg-[size:44px_44px] [mask-image:radial-gradient(60%_50%_at_30%_0%,black,transparent)]" />
      <div className="absolute -top-16 right-[8%] h-72 w-72 rounded-full bg-violet-500/10 blur-3xl" />
      <div className="absolute top-[40%] -left-20 h-64 w-64 rounded-full bg-lime-400/10 blur-3xl" />
    </div>
  );
}

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
    <div className="relative mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
      <PageGlow />
      <div className="fade-up mb-8 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="eyebrow mb-1.5 flex items-center gap-2">
            <Sparkles className="h-3 w-3" /> New analysis
          </div>
          <h1 className="display text-[34px] leading-tight sm:text-[44px]">
            What was the <span className="text-gradient">meeting</span> about?
          </h1>
          <p className="mt-1 text-sm text-muted">Paste a transcript or upload a file. Nothing is saved — the text is only used for this analysis.</p>
        </div>
        <div className="flex items-center gap-3">
          <Waveform bars={10} height={20} className="hidden sm:inline-flex" />
          <Button variant="secondary" icon={<Quote className="h-4 w-4" />} onClick={() => setDraft({ ...SAMPLE, file: null })}>
            Load sample transcript
          </Button>
        </div>
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
              "card relative flex flex-col items-center overflow-hidden border-dashed px-5 py-7 text-center transition",
              dragging ? "border-violet-500 bg-lavender-50 shadow-[var(--shadow-lift)]" : "border-line-strong hover:border-lavender-300",
            )}
          >
            {dragging && <span className="absolute inset-3 animate-ping rounded-xl border-2 border-violet-400/60" />}
            <div className="relative mb-3 grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-violet-400 to-violet-800 text-white shadow-[var(--shadow-glow)]">
              <FileUp className="h-5 w-5" />
              <Sparkle className="sparkle-twinkle absolute -top-1.5 -right-1.5 text-lime-400" size={11} />
            </div>
            <div className="text-sm font-medium text-ink">Drop a file here</div>
            <div className="mt-1 font-mono text-[11px] text-faint">TXT · DOCX · PDF · VTT · SRT — 10 MB</div>
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

          <div className="rounded-2xl border border-lavender-200 bg-lavender-50 p-4 text-xs leading-relaxed text-ink-soft">
            <div className="mb-1 flex items-center gap-1.5 font-mono text-[11px] tracking-[0.08em] text-violet-300 uppercase">
              <Info className="h-3.5 w-3.5" /> Best results
            </div>
            Use one line per speaker turn, like <code className="rounded bg-wash-3 px-1 font-mono text-lime-400">Priya: I'll send it Friday.</code> Timestamps such as{" "}
            <code className="rounded bg-wash-3 px-1 font-mono text-lime-400">[00:12:03]</code> are fine. Without speaker labels, owners can only come from names in the text.
          </div>
        </aside>

        <section className="card relative flex min-h-[560px] flex-col overflow-hidden focus-within:border-lavender-300 focus-within:shadow-[var(--shadow-lift)]">
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
          <div className="relative min-h-[420px] flex-1">
            <label htmlFor="transcript" className="sr-only">
              Transcript — paste text with speaker labels like “Priya: I'll send it Friday.”
            </label>
            <textarea
              id="transcript"
              value={draft.transcript}
              onChange={(e) => setDraft({ transcript: e.target.value })}
              className="absolute inset-0 h-full w-full resize-none bg-transparent px-5 py-4 font-mono text-[13px] leading-relaxed text-ink-soft focus:outline-none"
              spellCheck={false}
            />
            {!draft.transcript && <GhostPreview />}
          </div>
          <div className="relative flex flex-col gap-3 border-t border-line px-5 py-3.5 sm:flex-row sm:items-center">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11.5px] text-muted">
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
            <p className="relative flex items-center gap-1.5 px-5 pb-3.5 text-xs text-rose-600">
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
