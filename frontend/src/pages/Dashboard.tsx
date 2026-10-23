import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  FileText,
  Gavel,
  HelpCircle,
  KeyRound,
  ListChecks,
  Lock,
  Quote,
  ShieldAlert,
  Sparkles,
  Tags,
  Upload,
  Users,
  Wand2,
} from "lucide-react";
import { useWorkspace } from "../state/workspace";
import { SAMPLE } from "../lib/sample";
import { Badge, Button, Sparkle } from "../components/ui";

const FEATURES = [
  { icon: FileText, title: "Executive & detailed summaries", text: "Hierarchical summarization with a grounding check against the transcript." },
  { icon: ListChecks, title: "Action items", text: "Tasks, owners and deadlines from commitments, requests and replies." },
  { icon: Gavel, title: "Decisions", text: "Confirmed, tentative and rejected — told apart from suggestions." },
  { icon: CalendarClock, title: "Deadlines", text: "Relative dates resolved from the meeting date; ambiguity flagged." },
  { icon: ShieldAlert, title: "Risks & blockers", text: "Concerns and dependencies, each with supporting quotes." },
  { icon: HelpCircle, title: "Open questions", text: "Questions nobody answered, or that were deferred." },
  { icon: Users, title: "People & entities", text: "Speakers, talk share, organisations, dates and places." },
  { icon: Tags, title: "Topics & keywords", text: "Discussion segments with keyphrases and key points." },
];

function PreviewStack() {
  return (
    <div className="relative mx-auto w-full max-w-md lg:mx-0">
      <Sparkle className="sparkle-twinkle absolute -top-4 left-6 text-blush-400" size={18} />
      <Sparkle className="sparkle-twinkle absolute top-24 -right-3 text-violet-400 [animation-delay:1.2s]" size={14} />
      <Sparkle className="sparkle-twinkle absolute bottom-6 -left-4 text-lavender-300 [animation-delay:2.1s]" size={16} />
      <div className="card relative rotate-[-1.5deg] p-5">
        <div className="mb-2 flex items-center gap-2">
          <Badge tone="sage">
            <CheckCircle2 className="h-3 w-3" /> confirmed
          </Badge>
          <span className="text-xs text-faint">Decision</span>
        </div>
        <p className="text-[15px] font-medium text-ink">Move the launch to March 17.</p>
        <p className="mt-2 border-l-2 border-lavender-300 pl-2.5 text-xs text-muted italic">“Alright, we decided to move the launch to March 17.” — Priya</p>
      </div>
      <div className="card relative mt-[-10px] ml-8 rotate-[1.2deg] p-5">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs text-faint">Action item</span>
          <Badge tone="violet">Thu, Mar 5</Badge>
        </div>
        <p className="text-[15px] font-medium text-ink">Fix the checkout crash</p>
        <div className="mt-3 flex items-center gap-2 text-xs text-muted">
          <span className="grid h-6 w-6 place-items-center rounded-full bg-blush-100 text-[10px] font-semibold text-blush-600">MC</span>
          Marcus Chen · self-commitment
        </div>
      </div>
      <div className="card relative mt-[-8px] mr-10 rotate-[-0.6deg] p-5">
        <div className="mb-2 flex items-center gap-2">
          <Badge tone="rose">blocker</Badge>
          <span className="text-xs text-faint">Risk</span>
        </div>
        <p className="text-[14px] text-ink-soft">Blocked until PayFlow releases SDK 4.2.</p>
      </div>
      <p className="mt-3 text-center text-[11px] text-faint">Example output from the sample transcript</p>
    </div>
  );
}

export function Dashboard() {
  const navigate = useNavigate();
  const { setDraft, report } = useWorkspace();

  function loadSample() {
    setDraft({ ...SAMPLE, file: null });
    navigate("/new");
  }

  return (
    <div>
      <section className="relative overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_55%_at_75%_20%,var(--color-lavender-100),transparent_70%),radial-gradient(40%_40%_at_10%_90%,var(--color-blush-50),transparent_70%)]"
        />
        <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[1.1fr_1fr] lg:py-24">
          <div>
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-line bg-surface/80 px-3 py-1 text-xs text-muted shadow-[var(--shadow-soft)]">
              <Sparkles className="h-3.5 w-3.5 text-violet-500" /> Meeting intelligence, evidence first
            </div>
            <h1 className="display text-[44px] leading-[1.05] sm:text-[64px]">
              Your meetings,
              <br />
              <em className="text-violet-600">made meaningful.</em>
            </h1>
            <p className="mt-5 max-w-xl text-[16.5px] leading-relaxed text-muted">
              Paste a transcript or upload a file. MeetingMind finds the decisions, action items, owners, deadlines,
              risks and open questions — and shows you the exact lines each one came from.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button size="lg" icon={<Wand2 className="h-4 w-4" />} onClick={() => navigate("/new")}>
                New analysis
              </Button>
              <Button size="lg" variant="secondary" icon={<Quote className="h-4 w-4" />} onClick={loadSample}>
                Try the sample transcript
              </Button>
              {report && (
                <Button size="lg" variant="ghost" onClick={() => navigate("/results")}>
                  Back to “{report.meeting.title}” <ArrowRight className="h-4 w-4" />
                </Button>
              )}
            </div>
            <div className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted">
              <span className="inline-flex items-center gap-1.5">
                <Upload className="h-3.5 w-3.5" /> TXT, DOCX, PDF, VTT
              </span>
              <span className="inline-flex items-center gap-1.5">
                <KeyRound className="h-3.5 w-3.5" /> No account, no API keys
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Lock className="h-3.5 w-3.5" /> Nothing is stored
              </span>
            </div>
          </div>
          <PreviewStack />
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-6">
        <div className="eyebrow mb-2">What you get</div>
        <h2 className="display mb-8 text-[34px]">Twelve views of one conversation</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <div key={title} className="card group p-5 transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)]">
              <div className="mb-4 grid h-10 w-10 place-items-center rounded-xl bg-lavender-50 text-violet-600 transition group-hover:bg-violet-600 group-hover:text-white">
                <Icon className="h-5 w-5" />
              </div>
              <div className="font-medium text-ink">{title}</div>
              <p className="mt-1 text-sm leading-relaxed text-muted">{text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-4 px-4 pb-20 sm:px-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="card p-6 sm:p-8">
          <div className="eyebrow mb-2">How it works</div>
          <ol className="mt-4 space-y-5">
            {[
              ["Add a transcript", "Paste text with speaker labels (“Name: …”) or upload a TXT, DOCX, PDF or caption file. Set the meeting date so “next Friday” becomes a real date."],
              ["Local NLP pipeline", "spaCy parses sentences and entities, Sentence-Transformers compares meaning, YAKE finds keyphrases, and a DistilBART dialogue model writes summaries."],
              ["Review, edit, export", "Every item links to its transcript evidence. Fix owners, dates and statuses, then download PDF minutes, Markdown, CSV or JSON."],
            ].map(([title, text], i) => (
              <li key={title} className="flex gap-4">
                <span className="display grid h-9 w-9 shrink-0 place-items-center rounded-full bg-blush-50 text-lg text-blush-600">{i + 1}</span>
                <div>
                  <div className="font-medium text-ink">{title}</div>
                  <p className="mt-0.5 text-sm leading-relaxed text-muted">{text}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
        <div className="card relative overflow-hidden p-6 sm:p-8">
          <Sparkle className="absolute top-6 right-6 text-blush-200" size={22} />
          <div className="mb-4 grid h-10 w-10 place-items-center rounded-xl bg-sage-50 text-sage-600">
            <Lock className="h-5 w-5" />
          </div>
          <div className="font-medium text-ink">Privacy by design</div>
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-muted">
            <li>• Models run on the MeetingMind server you start — no paid or third-party AI APIs.</li>
            <li>• No database, accounts or meeting history. Uploads are deleted right after text extraction.</li>
            <li>• Transcript text is not written to logs.</li>
            <li>• Reports exist only in this tab; download them before starting a new analysis.</li>
          </ul>
          <p className="mt-4 text-xs leading-relaxed text-faint">
            Limitation: whoever runs the backend could change it to log data, and the first run downloads models from
            Hugging Face (model files only — no transcript is sent).
          </p>
        </div>
      </section>
    </div>
  );
}
