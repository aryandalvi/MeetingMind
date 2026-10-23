"""Topic segmentation (TextTiling-style with sentence embeddings) and topic labelling."""
from __future__ import annotations

import re
from typing import Sequence

import numpy as np

from ..schemas import KeyPoint, Topic
from .common import Embedder, clean_sentence, evidence_for
from .keywords import extract_keywords
from .preprocessing import ParsedTranscript, SentenceRec

TRANSITION = re.compile(
    r"(?i)^(?:ok(?:ay)?|so|alright|all right|right|great|good|now)?[,.]?\s*(?:let's (?:move on|talk about|turn to|switch to|"
    r"go to|discuss|look at|get to|jump to)|moving on|next (?:item|topic|up|on the agenda)|the next (?:item|topic|thing)|"
    r"on to (?:the )?next|turning to|agenda item|item \d|topic \d|last (?:item|topic|thing)|finally,|"
    r"switching gears|let's get into|let's start with|first (?:item|topic|up)|the (?:first|second|third|last) (?:item|topic))"
)


def _centrality(vecs: np.ndarray) -> np.ndarray:
    """TextRank-style centrality over a cosine-similarity graph (power iteration)."""
    n = len(vecs)
    if n == 0:
        return np.zeros(0)
    if n == 1:
        return np.ones(1)
    sim = np.clip(vecs @ vecs.T, 0, None)
    np.fill_diagonal(sim, 0)
    row = sim.sum(axis=1, keepdims=True)
    row[row == 0] = 1
    m = sim / row
    scores = np.ones(n) / n
    for _ in range(50):
        new = 0.15 / n + 0.85 * m.T @ scores
        if np.abs(new - scores).sum() < 1e-6:
            break
        scores = new
    return scores


def segment(sentences: Sequence[SentenceRec], embedder: Embedder, min_size: int = 6, max_topics: int = 8) -> list[list[SentenceRec]]:
    n = len(sentences)
    if n < min_size * 2:
        return [list(sentences)]
    vecs = embedder.encode([s.text for s in sentences])
    w = 3
    gaps = []
    for i in range(1, n):
        left = vecs[max(0, i - w) : i].mean(axis=0)
        right = vecs[i : min(n, i + w)].mean(axis=0)
        denom = (np.linalg.norm(left) * np.linalg.norm(right)) or 1.0
        gaps.append(float(left @ right / denom))
    gaps = np.array(gaps)
    # depth score: how much lower a gap is than the peaks on each side
    depth = np.zeros_like(gaps)
    for i in range(len(gaps)):
        lpeak = max(gaps[max(0, i - 6) : i + 1])
        rpeak = max(gaps[i : i + 7])
        depth[i] = (lpeak - gaps[i]) + (rpeak - gaps[i])
    threshold = depth.mean() + 1.0 * depth.std()
    transitions = set()
    for i, s in enumerate(sentences[1:]):
        if TRANSITION.match(s.text) or TRANSITION.match(re.sub(r"^[^.?!]{0,40}[.?!]\s+", "", s.text)):
            depth[i] += 2.0  # explicit agenda transitions are the strongest boundary signal
            transitions.add(i)
    target = min(max_topics, max(1, n // 12, len(transitions) + 1))
    order = np.argsort(-depth)
    boundaries: list[int] = []
    for idx in order:
        if len(boundaries) >= target - 1:
            break
        if depth[idx] < threshold and idx not in transitions:
            continue
        b = int(idx) + 1  # boundary before sentence b
        if all(abs(b - x) >= min_size for x in boundaries) and min_size <= b <= n - min_size:
            boundaries.append(b)
    boundaries.sort()
    segments, start = [], 0
    for b in boundaries + [n]:
        segments.append(list(sentences[start:b]))
        start = b
    return segments


def build_topics(t: ParsedTranscript, embedder: Embedder, has_parser: bool) -> list[Topic]:
    content = [s for s in t.sentences if len(s.text.split()) >= 3]
    if not content:
        content = list(t.sentences)
    segments = segment(content, embedder)
    topics: list[Topic] = []
    used_titles: set[str] = set()
    for i, seg in enumerate(segments, start=1):
        texts = [s.text for s in seg]
        chunks = []
        if has_parser:
            for s in seg:
                try:
                    chunks.extend(nc.text for nc in s.span.noun_chunks)
                except (ValueError, AttributeError):
                    pass
        kws = extract_keywords(texts, embedder, t.speakers, chunks, top_n=5, diversity=0.6)
        keywords = [k.phrase for k in kws]
        fresh = [k for k in keywords if k.lower() not in used_titles]
        title = next((k for k in fresh if len(k.split()) >= 2), None) or (fresh[0] if fresh else f"Discussion part {i}")
        used_titles.add(title.lower())
        title = title[:1].upper() + title[1:]
        vecs = embedder.encode(texts)
        cent = _centrality(vecs)
        n_points = 2 if len(seg) < 12 else 3
        top = sorted(np.argsort(-cent)[:n_points])
        key_points = [KeyPoint(text=clean_sentence(seg[j].text), evidence=evidence_for([seg[j]])) for j in top]
        speakers = list(dict.fromkeys(s.speaker for s in seg if s.speaker))
        topics.append(
            Topic(
                id=f"T{i}",
                title=title,
                keywords=keywords,
                key_points=key_points,
                speakers=speakers,
                sentence_ids=[s.id for s in seg],
                start_timestamp=next((s.timestamp for s in seg if s.timestamp), None),
                end_timestamp=next((s.timestamp for s in reversed(seg) if s.timestamp), None),
            )
        )
    return topics
