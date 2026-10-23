"""End-to-end analysis pipeline.

`analyze()` runs every stage in order and reports real progress through an optional callback
(used by the streaming API endpoint). Model failures degrade to documented fallbacks and are
reported in `report.warnings` and `report.models.fallbacks`.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from ..schemas import AnalysisReport, AnalyzeRequest, Deadline, MeetingInfo, ModelInfo, Sentence, Stats, Utterance
from .actions import ActionExtractor
from .common import RECAP, Embedder, NameResolver, clean_sentence, evidence_for
from .deadlines import DEADLINE_CONTEXT, find_deadlines, parse_header_date
from .decisions import DecisionExtractor
from .entities import extract_entities, people_stats
from .keywords import extract_keywords
from .models import ModelRegistry, ModelUnavailableError, get_registry
from .next_steps import recommend
from .preprocessing import format_duration, parse_transcript, timestamp_to_seconds
from .questions import QuestionExtractor
from .risks import RiskExtractor
from .summarizer import SummaryBuilder
from .topics import build_topics

log = logging.getLogger("meetingmind.pipeline")

STAGES: list[tuple[str, str]] = [
    ("models", "Loading NLP models"),
    ("preprocess", "Parsing speakers and sentences"),
    ("entities", "Recognising people, organisations and dates"),
    ("topics", "Segmenting topics and extracting keywords"),
    ("actions", "Extracting action items, owners and deadlines"),
    ("decisions", "Detecting decisions"),
    ("risks", "Detecting risks and blockers"),
    ("questions", "Finding unresolved questions"),
    ("summary", "Summarising the meeting"),
    ("next_steps", "Recommending next steps"),
    ("finalize", "Assembling the report"),
]
STAGE_LABELS = dict(STAGES)

ProgressFn = Callable[[dict], None]


class TranscriptValidationError(ValueError):
    pass


def validate_transcript(text: str, min_words: int, max_chars: int) -> None:
    if not text or not text.strip():
        raise TranscriptValidationError("The transcript is empty.")
    if len(text) > max_chars:
        raise TranscriptValidationError(
            f"The transcript is too long ({len(text):,} characters; the limit is {max_chars:,})."
        )
    words = len(text.split())
    if words < min_words:
        raise TranscriptValidationError(
            f"The transcript is too short to analyse ({words} words; at least {min_words} are needed)."
        )
    letters = sum(ch.isalpha() for ch in text)
    if letters < 0.4 * len(text.replace(" ", "").replace("\n", "")):
        raise TranscriptValidationError("The text does not look like a transcript (too few letters).")


class _Stages:
    def __init__(self, progress: Optional[ProgressFn]):
        self.progress = progress
        self.timings: dict[str, float] = {}
        self._start = 0.0
        self._current: Optional[str] = None

    def emit(self, **event):
        if self.progress:
            try:
                self.progress(event)
            except Exception:  # progress reporting must never break the analysis
                log.exception("progress callback failed")

    def start(self, key: str, detail: Optional[str] = None):
        self._current, self._start = key, time.perf_counter()
        self.emit(type="stage", stage=key, label=STAGE_LABELS[key], status="started", detail=detail)

    def detail(self, detail: str):
        if self._current:
            self.emit(type="stage", stage=self._current, label=STAGE_LABELS[self._current], status="progress", detail=detail)

    def done(self, detail: Optional[str] = None):
        key = self._current
        ms = round((time.perf_counter() - self._start) * 1000, 1)
        self.timings[key] = ms
        self.emit(type="stage", stage=key, label=STAGE_LABELS[key], status="completed", detail=detail, elapsed_ms=ms)
        self._current = None

    def fail(self, message: str):
        if self._current:
            self.emit(type="stage", stage=self._current, label=STAGE_LABELS[self._current], status="failed", detail=message)


def _load_models(registry: ModelRegistry, stages: _Stages, warnings: list[str], fallbacks: list[str]):
    import spacy

    nlp = None
    if registry.state("spacy") != "ready":
        stages.detail(f"Loading spaCy model '{registry.name('spacy')}'")
    try:
        nlp = registry.get("spacy")
    except ModelUnavailableError as exc:
        nlp = spacy.blank("en")
        nlp.add_pipe("sentencizer")
        fallbacks.append("spaCy model unavailable: rule-based sentence splitting, no NER or parsing.")
        warnings.append(f"spaCy model could not be loaded ({exc}); entity recognition is disabled and extraction is less accurate.")

    if registry.state("embeddings") != "ready":
        stages.detail(f"Loading sentence-embedding model '{registry.name('embeddings')}' (downloads ~90 MB on first run)")
    try:
        embedder = Embedder(registry.get("embeddings"))
    except ModelUnavailableError as exc:
        embedder = Embedder(None)
        fallbacks.append("Sentence-Transformers unavailable: hashed n-gram vectors used for similarity.")
        warnings.append(f"Embedding model could not be loaded ({exc}); semantic checks are disabled and results rely on rules only.")

    summarizer = None
    state = registry.state("summarizer")
    if state == "disabled":
        fallbacks.append("Abstractive summarizer disabled by configuration: extractive summaries used.")
    else:
        if state != "ready":
            stages.detail(f"Loading summarization model '{registry.name('summarizer')}' (downloads ~1.2 GB on first run)")
        try:
            summarizer = registry.get("summarizer")
        except ModelUnavailableError as exc:
            fallbacks.append("Abstractive summarizer unavailable: extractive summaries used.")
            warnings.append(f"Summarization model could not be loaded ({exc}); an extractive summary was produced instead.")
    return nlp, embedder, summarizer


def analyze(
    request: AnalyzeRequest,
    registry: Optional[ModelRegistry] = None,
    progress: Optional[ProgressFn] = None,
) -> AnalysisReport:
    registry = registry or get_registry()
    settings = registry.settings
    validate_transcript(request.transcript, settings.min_transcript_words, settings.max_transcript_chars)
    stages = _Stages(progress)
    warnings: list[str] = []
    fallbacks: list[str] = []
    try:
        return _run(request, registry, stages, warnings, fallbacks)
    except Exception as exc:
        stages.fail(f"{type(exc).__name__}: {exc}")
        raise


def _run(request, registry, stages, warnings, fallbacks) -> AnalysisReport:
    stages.start("models")
    nlp, embedder, summarizer = _load_models(registry, stages, warnings, fallbacks)
    has_parser = nlp.has_pipe("parser") or nlp.has_pipe("tagger")
    has_ner = nlp.has_pipe("ner")
    stages.done()

    stages.start("preprocess")
    t = parse_transcript(request.transcript, nlp)
    warnings.extend(t.warnings)
    if not t.sentences:
        raise TranscriptValidationError("No sentences could be found in the transcript.")
    meeting_date = request.meeting_date
    if meeting_date is None:
        meeting_date = parse_header_date(t.header_date_text)
        if meeting_date:
            warnings.append(f"Meeting date taken from the transcript header ({meeting_date.isoformat()}).")
        else:
            warnings.append("No meeting date given: relative deadlines such as 'next Friday' were not converted to dates.")
    stages.done(f"{len(t.utterances)} turns, {len(t.sentences)} sentences, {len(t.speakers)} speakers")

    stages.start("entities")
    entities = extract_entities(t, has_ner)
    person_entities = {e.text for e in entities if e.label == "PERSON"}
    resolver = NameResolver(t, sorted(person_entities | set(t.attendees)))
    stages.done(f"{len(entities)} entities")

    stages.start("topics")
    topics = build_topics(t, embedder, has_parser)
    chunks = []
    if has_parser:
        for s in t.sentences:
            try:
                chunks.extend(nc.text for nc in s.span.noun_chunks)
            except (ValueError, AttributeError):
                pass
    keywords = extract_keywords([s.text for s in t.sentences], embedder, t.speakers, chunks, top_n=15)
    stages.done(f"{len(topics)} topics, {len(keywords)} keywords")

    stages.start("actions")
    actions = ActionExtractor(t, embedder, resolver, meeting_date, person_entities).extract()
    stages.done(f"{len(actions)} action items")

    stages.start("decisions")
    decisions = DecisionExtractor(t, embedder).extract()
    stages.done(f"{len(decisions)} decisions")

    stages.start("risks")
    risks = RiskExtractor(t, embedder).extract()
    stages.done(f"{len(risks)} risks/blockers")

    stages.start("questions")
    questions = QuestionExtractor(t, embedder).extract()
    stages.done(f"{len(questions)} open questions")

    stages.start("summary", "abstractive" if summarizer else "extractive")
    builder = SummaryBuilder(t, embedder, summarizer, progress=stages.detail)
    summary = builder.build(topics, decisions, actions, risks)
    if summary.removed_unsupported:
        warnings.append(
            f"{summary.removed_unsupported} generated summary sentence(s) were removed because they were not supported by the transcript."
        )
    stages.done(summary.method)

    stages.start("next_steps")
    next_steps = recommend(t, actions, decisions, risks, questions, meeting_date)
    stages.done(f"{len(next_steps)} recommendations")

    stages.start("finalize")
    deadlines = _collect_deadlines(t, actions, meeting_date)
    people = people_stats(t, entities)
    for p in people:
        p.action_items = sum(1 for a in actions if p.name in a.owner.split(" & "))
    seconds = [timestamp_to_seconds(u.timestamp) for u in t.utterances if u.timestamp]
    seconds = [s for s in seconds if s is not None]
    duration = format_duration(max(seconds) - min(seconds)) if len(seconds) >= 2 and max(seconds) > min(seconds) else None
    word_count = len(request.transcript.split())
    stats = Stats(
        word_count=word_count,
        sentence_count=len(t.sentences),
        utterance_count=len(t.utterances),
        speaker_count=len(t.speakers),
        has_speaker_labels=t.has_speaker_labels,
        has_timestamps=t.has_timestamps,
        duration=duration,
        estimated_reading_minutes=round(word_count / 230, 1),
        action_items=len(actions),
        unassigned_action_items=sum(1 for a in actions if a.owner == "Unassigned"),
        decisions=len(decisions),
        risks=sum(1 for r in risks if r.kind == "risk"),
        blockers=sum(1 for r in risks if r.kind == "blocker"),
        open_questions=len(questions),
        items_needing_review=sum(1 for a in actions if a.needs_review)
        + sum(1 for d in decisions if d.needs_review)
        + sum(1 for r in risks if r.needs_review),
    )
    report = AnalysisReport(
        report_id=uuid.uuid4().hex[:12],
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        meeting=MeetingInfo(title=request.title, date=meeting_date, context=request.context),
        stats=stats,
        summary=summary,
        topics=topics,
        decisions=decisions,
        action_items=actions,
        deadlines=deadlines,
        risks=risks,
        questions=questions,
        entities=entities,
        people=people,
        keywords=keywords,
        next_steps=next_steps,
        utterances=[Utterance(id=u.id, speaker=u.speaker, timestamp=u.timestamp, text=u.text, sentence_ids=u.sentence_ids) for u in t.utterances],
        sentences=[Sentence(id=s.id, utterance_id=s.utterance_id, speaker=s.speaker, timestamp=s.timestamp, text=s.text) for s in t.sentences],
        warnings=list(dict.fromkeys(warnings)),
        models=ModelInfo(
            summarizer=registry.name("summarizer") if summarizer else "extractive (TextRank over sentence embeddings)",
            embeddings=registry.name("embeddings") if embedder.semantic else "hashed n-gram vectors (fallback)",
            spacy=registry.name("spacy") if has_ner else "spaCy blank 'en' + sentencizer (fallback)",
            fallbacks=fallbacks,
        ),
        timings_ms=stages.timings,
    )
    stages.done()
    report.timings_ms = stages.timings
    log.info(
        "Analysed transcript: %d words, %d sentences, %d actions, %d decisions in %.0f ms",
        word_count, len(t.sentences), len(actions), len(decisions), sum(stages.timings.values()),
    )
    return report


def _collect_deadlines(t, actions, meeting_date):
    """Deadlines attached to action items plus other dated commitments (launches, releases, due dates)."""
    out = [a.deadline for a in actions if a.deadline]
    covered = {e.sentence_id for d in out for e in d.evidence}
    n = 0
    for s in t.sentences:
        if s.id in covered or not DEADLINE_CONTEXT.search(s.text) or RECAP.match(clean_sentence(s.text)):
            continue
        for m in find_deadlines(s.text, meeting_date):
            if m.date_type == "vague" or (meeting_date and m.normalized_date and m.normalized_date < meeting_date):
                continue
            if not m.has_preposition and not DEADLINE_CONTEXT.search(s.text[max(0, m.start - 40) : m.start]):
                continue
            n += 1
            out.append(
                Deadline(
                    id=f"D{n}",
                    text=m.text,
                    normalized_date=m.normalized_date,
                    date_type=m.date_type,
                    granularity=m.granularity,
                    is_ambiguous=m.is_ambiguous,
                    note=m.note,
                    evidence=evidence_for([s]),
                )
            )
    return sorted(out, key=lambda d: (d.normalized_date is None, d.normalized_date or meeting_date or datetime.max.date()))
