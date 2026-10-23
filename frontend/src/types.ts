// Mirrors backend/app/schemas.py. Keep the two in sync.

export type Signal = "strong" | "moderate" | "weak";
export type Priority = "high" | "medium" | "low";
export type ActionStatus = "open" | "in_progress" | "done" | "blocked";
export type OwnerSource =
  | "explicit_name"
  | "self_commitment"
  | "addressed_request"
  | "inferred_from_reply"
  | "unassigned"
  | "user";

export interface Evidence {
  sentence_id: string;
  speaker: string | null;
  timestamp: string | null;
  text: string;
}

export interface Utterance {
  id: string;
  speaker: string | null;
  timestamp: string | null;
  text: string;
  sentence_ids: string[];
}

export interface Sentence {
  id: string;
  utterance_id: string;
  speaker: string | null;
  timestamp: string | null;
  text: string;
}

export interface Deadline {
  id?: string;
  text: string;
  normalized_date: string | null;
  date_type: "explicit" | "relative" | "vague" | "user";
  granularity: "day" | "week" | "month" | "quarter" | "unknown";
  is_ambiguous: boolean;
  note: string | null;
  related_action_id: string | null;
  evidence: Evidence[];
}

export interface ActionItem {
  id: string;
  description: string;
  owner: string;
  owner_source: OwnerSource;
  deadline: Deadline | null;
  status: ActionStatus;
  priority: Priority;
  is_inferred: boolean;
  needs_review: boolean;
  review_reasons: string[];
  signal: Signal;
  evidence: Evidence[];
  edited: boolean;
}

export interface Decision {
  id: string;
  text: string;
  status: "confirmed" | "tentative" | "rejected";
  kind: "decision" | "agreement" | "approval";
  speaker: string | null;
  is_inferred: boolean;
  needs_review: boolean;
  review_reasons: string[];
  signal: Signal;
  evidence: Evidence[];
}

export interface Risk {
  id: string;
  text: string;
  kind: "risk" | "blocker";
  severity: Priority;
  speaker: string | null;
  needs_review: boolean;
  review_reasons: string[];
  signal: Signal;
  evidence: Evidence[];
}

export interface Question {
  id: string;
  text: string;
  asked_by: string | null;
  status: "unanswered" | "deferred" | "open_issue";
  note: string | null;
  evidence: Evidence[];
  response_evidence: Evidence[];
}

export interface Entity {
  text: string;
  label: string;
  label_description: string;
  count: number;
  source: "ner" | "speaker_label" | "ner+speaker_label";
  evidence: Evidence[];
}

export interface Person {
  name: string;
  is_speaker: boolean;
  utterances: number;
  words: number;
  talk_share: number;
  mentions: number;
  action_items: number;
}

export interface Keyword {
  phrase: string;
  rank: number;
  mentions: number;
}

export interface KeyPoint {
  text: string;
  evidence: Evidence[];
}

export interface Topic {
  id: string;
  title: string;
  keywords: string[];
  summary: string;
  key_points: KeyPoint[];
  speakers: string[];
  sentence_ids: string[];
  start_timestamp: string | null;
  end_timestamp: string | null;
}

export interface SummarySentence {
  text: string;
  evidence: Evidence[];
  grounding: "supported" | "weak";
}

export interface Summary {
  method: "abstractive" | "extractive";
  executive: SummarySentence[];
  detailed: { topic_id: string; title: string; sentences: SummarySentence[] }[];
  discussion_points: KeyPoint[];
  decision_summary: string;
  follow_up_summary: string;
  removed_unsupported: number;
}

export interface NextStep {
  id: string;
  text: string;
  rationale: string;
  priority: Priority;
  category: string;
  related_ids: string[];
  evidence: Evidence[];
}

export interface Stats {
  word_count: number;
  sentence_count: number;
  utterance_count: number;
  speaker_count: number;
  has_speaker_labels: boolean;
  has_timestamps: boolean;
  duration: string | null;
  estimated_reading_minutes: number;
  action_items: number;
  unassigned_action_items: number;
  decisions: number;
  risks: number;
  blockers: number;
  open_questions: number;
  items_needing_review: number;
}

export interface AnalysisReport {
  schema_version: string;
  report_id: string;
  generated_at: string;
  edited_at: string | null;
  meeting: { title: string; date: string | null; context: string | null };
  stats: Stats;
  summary: Summary;
  topics: Topic[];
  decisions: Decision[];
  action_items: ActionItem[];
  deadlines: Deadline[];
  risks: Risk[];
  questions: Question[];
  entities: Entity[];
  people: Person[];
  keywords: Keyword[];
  next_steps: NextStep[];
  utterances: Utterance[];
  sentences: Sentence[];
  warnings: string[];
  models: { summarizer: string; embeddings: string; spacy: string; keywords: string; fallbacks: string[] };
  timings_ms: Record<string, number>;
}

export interface ExtractResponse {
  filename: string;
  file_type: string;
  text: string;
  word_count: number;
  char_count: number;
  pages: number | null;
  warnings: string[];
}

export interface ModelStatus {
  name: string;
  role: string;
  state: "not_loaded" | "loading" | "ready" | "failed" | "disabled";
  error: string | null;
  load_seconds: number | null;
}

export interface HealthResponse {
  status: "ok";
  version: string;
  summary_mode: string;
  models: ModelStatus[];
}

export interface AnalyzeRequest {
  transcript: string;
  title: string;
  meeting_date: string | null;
  context: string | null;
}

export type StageStatus = "pending" | "started" | "progress" | "completed" | "failed";

export type StreamEvent =
  | { type: "accepted"; stages: { key: string; label: string }[] }
  | { type: "queued"; message: string }
  | { type: "stage"; stage: string; label: string; status: Exclude<StageStatus, "pending">; detail?: string | null; elapsed_ms?: number }
  | { type: "result"; report: AnalysisReport }
  | { type: "error"; code: string; message: string };

export type ExportFormat = "json" | "csv" | "markdown" | "pdf";
