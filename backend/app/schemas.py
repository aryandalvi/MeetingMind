"""Pydantic models that define the MeetingMind API contract.

The same models are used for the analysis response and for the (possibly user-edited)
report that the frontend sends back to the export endpoints.
"""
from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# "signal" is a coarse, rule-plus-similarity strength label. It is NOT a probability.
Signal = Literal["strong", "moderate", "weak"]


class AnalyzeRequest(BaseModel):
    transcript: str = Field(..., description="Raw meeting transcript text.")
    title: str = Field("Untitled meeting", max_length=200)
    meeting_date: Optional[dt.date] = Field(
        None, description="ISO date of the meeting; used to normalise relative deadlines."
    )
    context: Optional[str] = Field(None, max_length=1000, description="Optional project/team context.")

    @field_validator("transcript")
    @classmethod
    def _strip(cls, v: str) -> str:
        if v is None or not v.strip():
            raise ValueError("Transcript is empty.")
        return v

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return v.strip() or "Untitled meeting"


class Evidence(BaseModel):
    sentence_id: str
    speaker: Optional[str] = None
    timestamp: Optional[str] = None
    text: str


class Utterance(BaseModel):
    id: str
    speaker: Optional[str] = None
    timestamp: Optional[str] = None
    text: str
    sentence_ids: list[str] = []


class Sentence(BaseModel):
    id: str
    utterance_id: str
    speaker: Optional[str] = None
    timestamp: Optional[str] = None
    text: str


class Deadline(BaseModel):
    id: str = ""
    text: str = Field(..., description="Deadline phrase exactly as found (or typed by the user).")
    normalized_date: Optional[dt.date] = Field(None, description="Resolved calendar date, if one could be resolved.")
    date_type: Literal["explicit", "relative", "vague", "user"] = "explicit"
    granularity: Literal["day", "week", "month", "quarter", "unknown"] = "day"
    is_ambiguous: bool = False
    note: Optional[str] = None
    related_action_id: Optional[str] = None
    evidence: list[Evidence] = []


class ActionItem(BaseModel):
    id: str
    description: str
    owner: str = "Unassigned"
    owner_source: Literal[
        "explicit_name", "self_commitment", "addressed_request", "inferred_from_reply", "unassigned", "user"
    ] = "unassigned"
    deadline: Optional[Deadline] = None
    status: Literal["open", "in_progress", "done", "blocked"] = "open"
    priority: Literal["high", "medium", "low"] = "medium"
    is_inferred: bool = False
    needs_review: bool = False
    review_reasons: list[str] = []
    signal: Signal = "moderate"
    evidence: list[Evidence] = []
    edited: bool = False


class Decision(BaseModel):
    id: str
    text: str
    status: Literal["confirmed", "tentative", "rejected"]
    kind: Literal["decision", "agreement", "approval"] = "decision"
    speaker: Optional[str] = None
    is_inferred: bool = False
    needs_review: bool = False
    review_reasons: list[str] = []
    signal: Signal = "moderate"
    evidence: list[Evidence] = []


class Risk(BaseModel):
    id: str
    text: str
    kind: Literal["risk", "blocker"]
    severity: Literal["high", "medium", "low"] = "medium"
    speaker: Optional[str] = None
    needs_review: bool = False
    review_reasons: list[str] = []
    signal: Signal = "moderate"
    evidence: list[Evidence] = []


class Question(BaseModel):
    id: str
    text: str
    asked_by: Optional[str] = None
    status: Literal["unanswered", "deferred", "open_issue"]
    note: Optional[str] = None
    evidence: list[Evidence] = []
    response_evidence: list[Evidence] = []


class Entity(BaseModel):
    text: str
    label: str
    label_description: str = ""
    count: int = 1
    source: Literal["ner", "speaker_label", "ner+speaker_label"] = "ner"
    evidence: list[Evidence] = []


class Person(BaseModel):
    name: str
    is_speaker: bool
    utterances: int = 0
    words: int = 0
    talk_share: float = 0.0
    mentions: int = 0
    action_items: int = 0


class Keyword(BaseModel):
    phrase: str
    rank: int
    mentions: int


class KeyPoint(BaseModel):
    text: str
    evidence: list[Evidence] = []


class Topic(BaseModel):
    id: str
    title: str
    keywords: list[str] = []
    summary: str = ""
    key_points: list[KeyPoint] = []
    speakers: list[str] = []
    sentence_ids: list[str] = []
    start_timestamp: Optional[str] = None
    end_timestamp: Optional[str] = None


class SummarySentence(BaseModel):
    text: str
    evidence: list[Evidence] = []
    grounding: Literal["supported", "weak"] = "supported"


class DetailedSummarySection(BaseModel):
    topic_id: str
    title: str
    sentences: list[SummarySentence] = []


class Summary(BaseModel):
    method: Literal["abstractive", "extractive"]
    executive: list[SummarySentence] = []
    detailed: list[DetailedSummarySection] = []
    discussion_points: list[KeyPoint] = []
    decision_summary: str = ""
    follow_up_summary: str = ""
    removed_unsupported: int = Field(0, description="Generated sentences dropped by the grounding check.")


class NextStep(BaseModel):
    id: str
    text: str
    rationale: str
    priority: Literal["high", "medium", "low"] = "medium"
    category: str = "general"
    related_ids: list[str] = []
    evidence: list[Evidence] = []


class MeetingInfo(BaseModel):
    title: str
    date: Optional[dt.date] = None
    context: Optional[str] = None


class Stats(BaseModel):
    word_count: int
    sentence_count: int
    utterance_count: int
    speaker_count: int
    has_speaker_labels: bool
    has_timestamps: bool
    duration: Optional[str] = None
    estimated_reading_minutes: float
    action_items: int = 0
    unassigned_action_items: int = 0
    decisions: int = 0
    risks: int = 0
    blockers: int = 0
    open_questions: int = 0
    items_needing_review: int = 0


class ModelInfo(BaseModel):
    summarizer: str
    embeddings: str
    spacy: str
    keywords: str = "YAKE + embedding MMR re-ranking"
    fallbacks: list[str] = []


class AnalysisReport(BaseModel):
    schema_version: str = "1.0"
    report_id: str
    generated_at: str
    edited_at: Optional[str] = None
    meeting: MeetingInfo
    stats: Stats
    summary: Summary
    topics: list[Topic] = []
    decisions: list[Decision] = []
    action_items: list[ActionItem] = []
    deadlines: list[Deadline] = []
    risks: list[Risk] = []
    questions: list[Question] = []
    entities: list[Entity] = []
    people: list[Person] = []
    keywords: list[Keyword] = []
    next_steps: list[NextStep] = []
    utterances: list[Utterance] = []
    sentences: list[Sentence] = []
    warnings: list[str] = []
    models: ModelInfo
    timings_ms: dict[str, float] = {}


class ExtractResponse(BaseModel):
    filename: str
    file_type: str
    text: str
    word_count: int
    char_count: int
    pages: Optional[int] = None
    warnings: list[str] = []


class ModelStatus(BaseModel):
    name: str
    role: str
    state: Literal["not_loaded", "loading", "ready", "failed", "disabled"]
    error: Optional[str] = None
    load_seconds: Optional[float] = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    summary_mode: str
    models: list[ModelStatus]
