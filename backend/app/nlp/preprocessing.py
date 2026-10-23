"""Transcript parsing: speaker labels, timestamps, utterances and sentence segmentation."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Optional

TS = r"(?:\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?"

# "[00:01:23] Priya Sharma: text", "Priya (00:12): text", "00:12 - Priya: text", "**Priya:** text"
SPEAKER_LINE = re.compile(
    rf"^\s*(?:[\[(]?(?P<ts1>{TS})[\])]?\s*[-–—|]?\s*)?"
    rf"(?P<speaker>[A-Za-z][\w.'\- ]{{0,40}}?)\s*"
    rf"(?:[\[(](?P<ts2>{TS})[\])])?\s*[:：]\s*(?P<text>.*)$"
)
# Otter.ai / Teams style: speaker name and timestamp on their own line, text below.
SPEAKER_HEADER = re.compile(rf"^\s*(?P<speaker>[A-Z][\w.'\- ]{{0,40}}?)\s+(?P<ts>{TS})\s*$")
VTT_ARROW = re.compile(rf"^\s*(?P<start>{TS})\s*-->\s*(?P<end>{TS})")
VTT_VOICE = re.compile(r"^<v\s+(?P<speaker>[^>]+)>(?P<text>.*?)(?:</v>)?$")
LEADING_TS = re.compile(rf"^\s*[\[(]?{TS}[\])]?\s*[-–—|]?\s*")

NON_SPEAKER_LABELS = {
    "note", "notes", "agenda", "action", "action item", "action items", "actions", "decision",
    "decisions", "summary", "date", "time", "attendees", "participants", "present", "absent",
    "subject", "re", "todo", "to do", "update", "updates", "meeting", "title", "location",
    "minutes", "transcript", "topic", "item", "next steps", "ps", "fyi", "cc", "from", "to",
    "objective", "goal", "goals", "duration", "recording", "host", "chair", "followup",
    "follow up", "follow-up", "risk", "risks", "blocker", "blockers", "question", "questions",
    "answer", "warning", "important", "reminder", "deadline", "status", "project", "team",
    "http", "https", "webvtt", "kind", "language",
}
NAME_PARTICLES = {"de", "van", "von", "da", "del", "der", "al", "bin", "la", "le", "di", "du", "st."}
HEADER_DATE_LABELS = {"date", "meeting date"}
# "Label: value" lines that describe the meeting rather than being spoken content.
METADATA_LABELS = {
    "meeting", "meeting title", "title", "subject", "date", "meeting date", "time", "attendees", "participants",
    "present", "absent", "location", "duration", "recording", "host", "chair", "transcript", "agenda",
}


@dataclass
class UtteranceRec:
    id: str
    speaker: Optional[str]
    timestamp: Optional[str]
    text: str
    sentence_ids: list[str] = field(default_factory=list)


@dataclass
class SentenceRec:
    id: str
    index: int
    utterance_id: str
    utterance_index: int
    speaker: Optional[str]
    timestamp: Optional[str]
    text: str
    span: Any = None  # spaCy Span (has tokens, ents, POS when a parser is available)


@dataclass
class ParsedTranscript:
    utterances: list[UtteranceRec]
    sentences: list[SentenceRec]
    speakers: list[str]
    has_speaker_labels: bool
    has_timestamps: bool
    header_date_text: Optional[str] = None
    metadata: dict[str, str] = field(default_factory=dict)
    attendees: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def sentence(self, sid: str) -> SentenceRec:
        return self._by_id[sid]

    def __post_init__(self) -> None:
        self._by_id = {s.id: s for s in self.sentences}


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = (
        text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
        .replace(" ", " ").replace("​", "").replace("﻿", "").replace("…", "...")
    )
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def _clean_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip(" *_#>-\t")).strip()


def is_plausible_speaker(label: str) -> bool:
    label = _clean_label(label)
    if not label or len(label) > 40:
        return False
    if label.lower() in NON_SPEAKER_LABELS:
        return False
    words = label.split()
    if len(words) > 4:
        return False
    if re.fullmatch(r"(?i)(speaker|participant|person|guest|user)\s*[\w]{1,3}", label):
        return True
    for w in words:
        if w.lower() in NAME_PARTICLES:
            continue
        if not (w[0].isupper() or w[0].isdigit()):
            return False
        if any(ch.isdigit() for ch in w) and not w.isdigit():
            return False
    return not words[0][0].isdigit()


def _strip_markup(line: str) -> str:
    return re.sub(r"\*\*|__", "", line).strip()


def _split_lines(raw: str) -> tuple[list[tuple[Optional[str], Optional[str], str]], dict[str, str]]:
    """Return a list of (speaker, timestamp, text) line records and header metadata."""
    records: list[tuple[Optional[str], Optional[str], str]] = []
    metadata: dict[str, str] = {}
    pending_ts: Optional[str] = None
    header_speaker: Optional[tuple[str, str]] = None
    lines = raw.split("\n")
    for i, line in enumerate(lines):
        stripped = _strip_markup(line)
        if not stripped:
            continue
        if stripped.upper().startswith("WEBVTT") or re.fullmatch(r"NOTE( .*)?", stripped):
            continue
        # SRT index line followed by a timestamp arrow.
        if stripped.isdigit() and i + 1 < len(lines) and VTT_ARROW.match(lines[i + 1]):
            continue
        arrow = VTT_ARROW.match(stripped)
        if arrow:
            pending_ts = arrow.group("start").split(".")[0].split(",")[0]
            continue
        voice = VTT_VOICE.match(stripped)
        if voice:
            records.append((_clean_label(voice.group("speaker")), pending_ts, voice.group("text").strip()))
            pending_ts = None
            continue
        header = SPEAKER_HEADER.match(stripped)
        if header and is_plausible_speaker(header.group("speaker")):
            header_speaker = (_clean_label(header.group("speaker")), header.group("ts"))
            continue
        m = SPEAKER_LINE.match(stripped)
        if m:
            label = _clean_label(m.group("speaker"))
            if label.lower() in METADATA_LABELS and m.group("text").strip():
                metadata.setdefault(label.lower(), m.group("text").strip())
                continue
            if is_plausible_speaker(label) and m.group("text").strip():
                ts = m.group("ts1") or m.group("ts2") or pending_ts
                records.append((label, ts, m.group("text").strip()))
                pending_ts, header_speaker = None, None
                continue
        text = LEADING_TS.sub("", stripped) if not header_speaker else stripped
        if header_speaker:
            records.append((header_speaker[0], header_speaker[1], text))
            header_speaker = (header_speaker[0], None)  # following lines continue the same turn
        else:
            records.append((None, pending_ts, text))
        pending_ts = None
    return records, metadata


def _canonical_speakers(records: list[tuple[Optional[str], Optional[str], str]]) -> dict[str, str]:
    """Map case variants of a label ("PRIYA", "priya") onto one canonical speaker name."""
    labels = [r[0] for r in records if r[0]]
    canonical: dict[str, str] = {}
    full_names = sorted({l for l in labels}, key=lambda l: -len(l))
    for label in labels:
        if label in canonical:
            continue
        key = label.lower()
        match = next((f for f in full_names if f.lower() == key), label)
        # "PRIYA" vs "Priya" -> prefer title-cased variant.
        if match.isupper() and len(match) > 3:
            match = match.title()
        canonical[label] = match
    return canonical


def parse_transcript(raw: str, nlp: Any) -> ParsedTranscript:
    text = normalize_text(raw)
    records, metadata = _split_lines(text)
    canonical = _canonical_speakers(records)

    # Merge consecutive lines into utterances: same speaker, or unlabelled continuation lines.
    merged: list[list] = []
    for speaker, ts, line_text in records:
        speaker = canonical.get(speaker, speaker) if speaker else None
        if merged and speaker is None and merged[-1][0] is not None and ts is None:
            merged[-1][2] += " " + line_text
            continue
        if merged and speaker is not None and merged[-1][0] == speaker and ts is None:
            merged[-1][2] += " " + line_text
            continue
        merged.append([speaker, ts, line_text])

    utterances: list[UtteranceRec] = []
    for i, (speaker, ts, utt_text) in enumerate(merged):
        utt_text = re.sub(r"\s+", " ", utt_text).strip()
        if utt_text:
            utterances.append(UtteranceRec(id=f"u{len(utterances) + 1}", speaker=speaker, timestamp=ts, text=utt_text))

    sentences: list[SentenceRec] = []
    docs = nlp.pipe([u.text for u in utterances], batch_size=64)
    for u_index, (utt, doc) in enumerate(zip(utterances, docs)):
        for sent in doc.sents:
            s_text = sent.text.strip()
            if not s_text or not re.search(r"[A-Za-z0-9]", s_text):
                continue
            sid = f"s{len(sentences) + 1}"
            sentences.append(
                SentenceRec(
                    id=sid,
                    index=len(sentences),
                    utterance_id=utt.id,
                    utterance_index=u_index,
                    speaker=utt.speaker,
                    timestamp=utt.timestamp,
                    text=s_text,
                    span=sent,
                )
            )
            utt.sentence_ids.append(sid)

    speakers: list[str] = []
    for u in utterances:
        if u.speaker and u.speaker not in speakers:
            speakers.append(u.speaker)
    labelled = sum(1 for u in utterances if u.speaker)
    warnings: list[str] = []
    has_labels = bool(speakers) and labelled >= max(1, len(utterances) // 3)
    if not has_labels:
        warnings.append(
            "No consistent speaker labels detected (expected 'Name: text'). Owners can only be found "
            "when people are named in the text."
        )
    return ParsedTranscript(
        utterances=utterances,
        sentences=sentences,
        speakers=speakers,
        has_speaker_labels=has_labels,
        has_timestamps=any(u.timestamp for u in utterances),
        header_date_text=next((metadata[k] for k in HEADER_DATE_LABELS if k in metadata), None),
        metadata=metadata,
        attendees=_attendees(metadata),
        warnings=warnings,
    )


def _attendees(metadata: dict[str, str]) -> list[str]:
    raw = metadata.get("attendees") or metadata.get("participants") or metadata.get("present") or ""
    names = [n.strip(" .;") for n in re.split(r",|;|\band\b|&", raw)]
    return [re.sub(r"\s*\(.*?\)", "", n) for n in names if n and is_plausible_speaker(re.sub(r"\s*\(.*?\)", "", n))]


def timestamp_to_seconds(ts: Optional[str]) -> Optional[int]:
    if not ts:
        return None
    parts = re.split(r"[.,]", ts)[0].split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    seconds = 0
    for n in nums:
        seconds = seconds * 60 + n
    return seconds


def format_duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"
