"""Helpers shared by the extraction modules."""
from __future__ import annotations

import re
from typing import Iterable, Optional, Sequence

import numpy as np
# Imported eagerly so its native dependencies load on the main thread, not a request worker.
import sklearn.feature_extraction.text  # noqa: F401

from ..schemas import Evidence
from .preprocessing import ParsedTranscript, SentenceRec

FILLER_PREFIX = re.compile(
    r"^(?:(?:ok(?:ay)?|so|and|also|alright|all right|right|great|cool|sure|yes|yeah|yep|well|um+|uh+|"
    r"hmm+|oh|perfect|good|fine|anyway|actually|basically|then|now|thanks|thank you|got it|"
    r"sounds good|in that case|one more thing|last thing|finally|lastly)\b[,.!]?\s*)+",
    re.IGNORECASE,
)
WS = re.compile(r"\s+")
# Recap / summary statements restate earlier items; extractors skip them to avoid duplicates.
RECAP = re.compile(
    r"(?i)^(?:ok(?:ay)?|so|alright|right)?[,.]?\s*(?:to (?:recap|summari[sz]e|sum up|wrap up)|recap|in summary|"
    r"summing up|quick recap|just to recap|so to recap|to confirm everything)\b"
)
ANAPHORIC = re.compile(
    r"(?i)^(?:that|this|it)(?:'s| is| was| sounds| seems| would be)?\s+(?:a|an|the)?\s*(?:real|big|huge|serious|"
    r"major|valid|good|fair|definite|potential)?\s*(?:risk|concern|problem|issue|point|question|worry)\b"
)


def clean_sentence(text: str) -> str:
    """Strip conversational filler at the start and tidy whitespace. Keeps the meaning intact."""
    stripped = FILLER_PREFIX.sub("", text).strip()
    if len(stripped.split()) < 3:  # don't strip a sentence down to nothing
        stripped = text.strip()
    stripped = WS.sub(" ", stripped)
    return stripped[:1].upper() + stripped[1:] if stripped else stripped


def is_question(text: str) -> bool:
    t = text.strip()
    if t.endswith("?"):
        return True
    return bool(
        re.match(
            r"(?i)^(who|what|when|where|why|how|which|is|are|do|does|did|can|could|would|will|should|"
            r"shall|have|has)\b.*\b(or not|right)$",
            t,
        )
    )


def evidence_for(sentences: Iterable[SentenceRec]) -> list[Evidence]:
    seen: set[str] = set()
    out: list[Evidence] = []
    for s in sentences:
        if s.id in seen:
            continue
        seen.add(s.id)
        out.append(Evidence(sentence_id=s.id, speaker=s.speaker, timestamp=s.timestamp, text=s.text))
    return out


class Embedder:
    """Sentence embeddings from Sentence-Transformers, with a deterministic fallback.

    When the transformer model is unavailable, a hashed TF-IDF style bag-of-ngrams vector is used.
    It keeps topic segmentation and de-duplication working, but similarity to the semantic
    prototypes is much weaker, so `semantic` is False and callers lower its weight.
    """

    def __init__(self, model=None):
        self.model = model
        self.semantic = model is not None
        self._cache: dict[str, np.ndarray] = {}
        if model is None:
            from sklearn.feature_extraction.text import HashingVectorizer

            self._hv = HashingVectorizer(
                n_features=2**14, ngram_range=(1, 2), stop_words="english", norm="l2", alternate_sign=False
            )

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if missing:
            if self.model is not None:
                vecs = self.model.encode(
                    list(missing), batch_size=64, normalize_embeddings=True, show_progress_bar=False
                )
            else:
                vecs = self._hv.transform(list(missing)).toarray()
            for t, v in zip(missing, vecs):
                self._cache[t] = np.asarray(v, dtype=np.float32)
        if not texts:
            return np.zeros((0, 1), dtype=np.float32)
        return np.vstack([self._cache[t] for t in texts])

    def similarity(self, a: Sequence[str], b: Sequence[str]) -> np.ndarray:
        return self.encode(a) @ self.encode(b).T


class PrototypeScorer:
    """Nearest-prototype semantic scorer: compares sentences with short hand-written examples
    of each class and returns the margin between positive and negative similarity."""

    def __init__(self, embedder: Embedder, positives: list[str], negatives: list[str]):
        self.embedder = embedder
        self.positives = positives
        self.negatives = negatives

    def margins(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros(0)
        pos = self.embedder.similarity(texts, self.positives).max(axis=1)
        neg = self.embedder.similarity(texts, self.negatives).max(axis=1)
        return pos - neg

    def positive_similarity(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros(0)
        return self.embedder.similarity(texts, self.positives).max(axis=1)


class NameResolver:
    """Resolves names mentioned in text to speakers (e.g. "Priya" -> "Priya Sharma")."""

    def __init__(self, transcript: ParsedTranscript, extra_people: Iterable[str] = ()):
        self.speakers = list(transcript.speakers)
        self.people = list(dict.fromkeys(list(self.speakers) + [p for p in extra_people if p]))
        self._index: dict[str, str] = {}
        first_name_counts: dict[str, int] = {}
        for p in self.people:
            first = p.split()[0].lower()
            first_name_counts[first] = first_name_counts.get(first, 0) + 1
        for p in self.people:
            self._index[p.lower()] = p
            parts = p.split()
            if len(parts) > 1 and first_name_counts.get(parts[0].lower()) == 1:
                self._index.setdefault(parts[0].lower(), p)
            if len(parts) > 1:
                self._index.setdefault(parts[-1].lower(), p)

    def resolve(self, name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        key = name.strip().strip(",.").lower()
        key = re.sub(r"^(?:mr|mrs|ms|dr|prof)\.?\s+", "", key)
        return self._index.get(key)

    def known_name_pattern(self) -> Optional[str]:
        keys = sorted(self._index, key=len, reverse=True)
        if not keys:
            return None
        return "|".join(re.escape(k) for k in keys)


def signal_from(score: float, strong: float, moderate: float) -> str:
    if score >= strong:
        return "strong"
    if score >= moderate:
        return "moderate"
    return "weak"


def next_turns(transcript: ParsedTranscript, sentence: SentenceRec, max_utterances: int = 3) -> list:
    """Utterances following the one containing `sentence` (used to find replies/answers)."""
    start = sentence.utterance_index + 1
    return transcript.utterances[start : start + max_utterances]


def sentences_of(transcript: ParsedTranscript, utterance) -> list[SentenceRec]:
    return [transcript.sentence(sid) for sid in utterance.sentence_ids]
