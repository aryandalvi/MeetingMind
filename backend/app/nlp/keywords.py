"""Keyphrase extraction: YAKE candidates + spaCy noun chunks, re-ranked KeyBERT-style with
sentence-embedding similarity to the document and Maximal Marginal Relevance (MMR) for diversity."""
from __future__ import annotations

import re
from typing import Sequence

import numpy as np

from ..schemas import Keyword
from .common import Embedder

CONVERSATIONAL = {
    "okay", "yeah", "thanks", "thank", "think", "guys", "sure", "right", "good", "great", "lot", "thing", "things",
    "kind", "sort", "stuff", "today", "everyone", "meeting", "question", "point", "way", "bit", "time", "let",
    "going", "gonna", "know", "mean", "really", "actually", "basically", "just", "like", "maybe", "need", "want",
    "sounds", "perfect", "yes", "hey", "hi", "um", "uh", "fine", "also", "next", "last", "week", "call", "talk",
    "real", "risk", "concern", "issue", "problem", "everything", "anyone", "someone", "nothing", "something",
}


def _clean_doc(texts: Sequence[str]) -> str:
    joined = " ".join(texts)
    joined = re.sub(r"(?i)\b(um+|uh+|you know|i mean|kind of|sort of)\b", " ", joined)
    return re.sub(r"\s+", " ", joined)


DATE_WORDS = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february", "march",
    "april", "may", "june", "july", "august", "september", "october", "november", "december", "tomorrow",
    "yesterday", "tonight", "morning", "afternoon", "evening", "weeks", "months", "days", "year", "today",
}


def _valid(phrase: str, speakers_lower: set[str]) -> bool:
    words = phrase.lower().split()
    if not words or len(phrase) < 3 or len(words) > 4:
        return False
    if words[0] in DATE_WORDS or words[-1] in DATE_WORDS or (len(words) == 1 and words[0] in DATE_WORDS):
        return False
    if all(w in CONVERSATIONAL for w in words) or words[0] in CONVERSATIONAL and len(words) == 1:
        return False
    if phrase.lower() in speakers_lower or any(w in speakers_lower for w in words) and len(words) == 1:
        return False
    if re.fullmatch(r"[\d\s.,:%$-]+", phrase):
        return False
    return True


def extract_keywords(
    sentences: Sequence[str],
    embedder: Embedder,
    speakers: Sequence[str] = (),
    noun_chunks: Sequence[str] = (),
    top_n: int = 15,
    diversity: float = 0.55,
) -> list[Keyword]:
    doc = _clean_doc(sentences)
    if len(doc.split()) < 5:
        return []
    speakers_lower = {s.lower() for s in speakers} | {part.lower() for s in speakers for part in s.split()}
    chunk_text = " | ".join(c.lower() for c in noun_chunks)
    candidates: dict[str, float] = {}
    try:
        import yake

        kw = yake.KeywordExtractor(lan="en", n=3, dedupLim=0.8, top=80)
        for phrase, score in kw.extract_keywords(doc):
            if not _valid(phrase, speakers_lower):
                continue
            # With a parser available, keep only noun-phrase candidates ("payment flow", not "Elena contacts").
            if noun_chunks and not re.search(r"(?:^|[\s|])" + re.escape(phrase.lower()) + r"(?:$|[\s|])", chunk_text):
                continue
            candidates.setdefault(phrase.strip(), score)
    except Exception:  # YAKE missing -> noun chunks only
        pass
    for chunk in noun_chunks:
        chunk = re.sub(r"^(?:the|a|an|our|my|your|their|this|that|these|those|some|any)\s+", "", chunk.strip(), flags=re.I)
        if _valid(chunk, speakers_lower) and len(chunk.split()) >= 2:
            candidates.setdefault(chunk, 1.0)
    if not candidates:
        return []

    phrases = list(candidates)
    lower_doc = doc.lower()
    mentions = np.array([len(re.findall(r"\b" + re.escape(p.lower()) + r"\b", lower_doc)) for p in phrases])
    phrase_vecs = embedder.encode(phrases)
    doc_vec = embedder.encode([" ".join(sentences)[:5000]])[0]
    relevance = phrase_vecs @ doc_vec
    # Combine semantic relevance with YAKE (lower YAKE score = better) and frequency.
    yake_rank = np.array([candidates[p] for p in phrases])
    yake_norm = 1 - (np.argsort(np.argsort(yake_rank)) / max(1, len(phrases) - 1))
    freq = np.log1p(mentions) / max(1.0, np.log1p(mentions.max()))
    w_sem = 0.5 if embedder.semantic else 0.0
    multiword = np.array([min(len(p.split()), 3) - 1 for p in phrases]) * 0.04  # prefer specific phrases
    score = w_sem * relevance + 0.3 * yake_norm + 0.2 * freq + multiword
    score = np.where(mentions == 0, score - 0.5, score)

    # MMR selection for diversity.
    selected: list[int] = []
    remaining = list(np.argsort(-score))
    while remaining and len(selected) < top_n:
        if not selected:
            selected.append(remaining.pop(0))
            continue
        sims = phrase_vecs[remaining] @ phrase_vecs[selected].T
        mmr = (1 - diversity) * score[remaining] - diversity * sims.max(axis=1)
        best = int(np.argmax(mmr))
        idx = remaining.pop(best)
        # Skip near-duplicates / substrings of chosen phrases.
        p = phrases[idx].lower()
        if any(p in phrases[j].lower() or phrases[j].lower() in p for j in selected):
            continue
        selected.append(idx)

    return [Keyword(phrase=phrases[i], rank=r + 1, mentions=int(max(1, mentions[i]))) for r, i in enumerate(selected)]
