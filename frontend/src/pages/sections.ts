import {
  CalendarClock,
  FileText,
  Gavel,
  HelpCircle,
  LayoutDashboard,
  ListChecks,
  Quote,
  ShieldAlert,
  Signpost,
  Tags,
  Users,
  Waypoints,
} from "lucide-react";
import type { AnalysisReport } from "../types";

export type SectionDef = { key: string; label: string; icon: typeof FileText; count?: (r: AnalysisReport) => number };

// Kept separate from Results.tsx so the sidebar can list sections without loading the lazy results chunk.
export const SECTIONS: SectionDef[] = [
  { key: "overview", label: "Overview", icon: LayoutDashboard },
  { key: "summary", label: "Executive summary", icon: FileText },
  { key: "topics", label: "Discussion topics", icon: Waypoints, count: (r) => r.topics.length },
  { key: "decisions", label: "Decisions", icon: Gavel, count: (r) => r.decisions.length },
  { key: "actions", label: "Action items", icon: ListChecks, count: (r) => r.action_items.length },
  { key: "deadlines", label: "Deadlines", icon: CalendarClock, count: (r) => r.deadlines.length },
  { key: "risks", label: "Risks & blockers", icon: ShieldAlert, count: (r) => r.risks.length },
  { key: "questions", label: "Unresolved questions", icon: HelpCircle, count: (r) => r.questions.length },
  { key: "people", label: "People & entities", icon: Users, count: (r) => r.entities.length },
  { key: "keywords", label: "Keywords", icon: Tags, count: (r) => r.keywords.length },
  { key: "evidence", label: "Transcript evidence", icon: Quote, count: (r) => r.sentences.length },
  { key: "next", label: "Recommended next steps", icon: Signpost, count: (r) => r.next_steps.length },
];

export const sectionPath = (key: string) => (key === "overview" ? "/results" : `/results/${key}`);
