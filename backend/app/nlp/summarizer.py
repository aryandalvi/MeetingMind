"""Executive / detailed summaries.

Abstractive mode: each topic segment is converted to dialogue text, split into chunks that fit
the model's input window, summarised, and (if needed) the chunk summaries are summarised again
(hierarchical / map-reduce summarization). The executive summary is a summary of the topic
summaries. Every generated sentence is then checked against the transcript: sentences that
mention names or numbers absent from the source are removed, and each kept sentence is linked
to its most similar transcript sentences as evidence.

Extractive mode (fallback or by configuration): the most central sentences of each topic,
ranked with a TextRank-style graph over sentence embeddings.
"""
from __future__ import annotations

import re
from typing import Callable, Optional, Sequence

import numpy as np

from ..schemas import ActionItem, Decision, DetailedSummarySection, KeyPoint, Risk, Summary, SummarySentence, Topic
from .common import RECAP, Embedder, clean_sentence, evidence_for, is_question
from .preprocessing import ParsedTranscript, SentenceRec
from .topics import TRANSITION, _centrality

COMMON_CAPITALISED = {
    "the", "we", "they", "he", "she", "it", "this", "that", "there", "a", "an", "in", "on", "at", "for", "and",
    "but", "so", "if", "i", "their", "his", "her", "its", "our", "team", "everyone", "they'll", "they're",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february",
    "march", "april", "may", "june", "july", "august", "september", "october", "november", "december",
    "after", "before", "next", "then", "also", "both", "all", "some", "one", "two", "three", "as", "to",
}
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")
CHUNK_TOKENS = 850


def _dialogue(sentences: Sequence[SentenceRec]) -> list[str]:
    """Group consecutive sentences into 'Speaker: text' turns (the format SAMSum models expect)."""
    turns: list[list] = []
    for s in sentences:
        if turns and turns[-1][0] == s.speaker:
            turns[-1][1].append(s.text)
        else:
            turns.append([s.speaker, [s.text]])
    return [f"{sp}: {' '.join(txt)}" if sp else " ".join(txt) for sp, txt in turns]


def _chunks(lines: list[str], count_tokens: Callable[[str], int], limit: int = CHUNK_TOKENS) -> list[str]:
    chunks, current, size = [], [], 0
    for line in lines:
        n = count_tokens(line) + 1
        if n > limit:  # one very long turn: split it by sentences
            parts = SENT_SPLIT.split(line)
            for p in parts:
                pn = count_tokens(p) + 1
                if size + pn > limit and current:
                    chunks.append("\n".join(current))
                    current, size = [], 0
                current.append(p)
                size += pn
            continue
        if size + n > limit and current:
            chunks.append("\n".join(current))
            current, size = [], 0
        current.append(line)
        size += n
    if current:
        chunks.append("\n".join(current))
    return chunks


class SummaryBuilder:
    def __init__(
        self,
        transcript: ParsedTranscript,
        embedder: Embedder,
        model=None,
        progress: Optional[Callable[[str], None]] = None,
    ):
        self.t = transcript
        self.embedder = embedder
        self.model = model
        self.progress = progress or (lambda msg: None)
        self.removed = 0
        self.salient: set[str] = set()
        self.actions: Sequence[ActionItem] = ()
        self._vocab = self._source_vocab()

    def _source_vocab(self) -> set[str]:
        words: set[str] = set()
        for s in self.t.sentences:
            words.update(w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]+|\d+(?:[.,]\d+)?", s.text))
        for sp in self.t.speakers:
            words.update(w.lower() for w in sp.split())
        return words

    # ------------------------------------------------------------------ grounding
    def _unsupported_tokens(self, sentence: str) -> list[str]:
        missing = []
        for tok in re.findall(r"\b[A-Z][a-zA-Z'-]+\b|\b\d+(?:[.,]\d+)?\b", sentence):
            base = re.sub(r"'s$", "", tok).lower()
            if base in COMMON_CAPITALISED:
                continue
            if base not in self._vocab:
                missing.append(tok)
        return missing

    def _salient(self, sentence: str) -> set[str]:
        return {
            re.sub(r"'s$", "", tok).lower()
            for tok in re.findall(r"\b[A-Z][a-zA-Z'-]+\b|\b\d+(?:[.,]\d+)?\b", sentence)
            if re.sub(r"'s$", "", tok).lower() not in COMMON_CAPITALISED
        }

    def _co_occur(self, salient: set[str], source: Sequence[SentenceRec], window: int = 1) -> bool:
        """True if every pair of names/numbers appears within `window` sentences of each other.
        Catches conflations such as "Android 9 was moved to March 17" built from two unrelated lines."""
        if len(salient) < 2:
            return True
        token_sets = [
            {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]+|\d+(?:[.,]\d+)?", s.text)}
            | {p.lower() for p in (s.speaker or "").split()}
            for s in source
        ]
        positions = {tok: [i for i, ts in enumerate(token_sets) if tok in ts] for tok in salient}
        tokens = sorted(salient)
        for a_i, a in enumerate(tokens):
            for b in tokens[a_i + 1 :]:
                if not any(abs(i - j) <= window for i in positions[a] for j in positions[b]):
                    return False
        return True

    def _commitment_supported(self, sentence: str) -> bool:
        """A generated "Cara will write the announcement" must match an extracted action item owned by Cara."""
        m = re.search(r"\b([A-Z][a-z]+)(?: [A-Z][a-z]+)? (?:will|is going to|'ll|has to|needs to|is to|agreed to|promised to)\b", sentence)
        if not m or m.group(1).lower() in COMMON_CAPITALISED or not self.embedder.semantic:
            return True
        name = m.group(1).lower()
        owned = [a for a in self.actions if name in a.owner.lower().split() or name in a.owner.lower().replace("&", " ").split()]
        if not owned:
            return False
        sims = self.embedder.similarity([sentence], [a.description for a in owned])[0]
        return float(sims.max()) > 0.35

    def _ground(self, text: str, source: Sequence[SentenceRec]) -> list[SummarySentence]:
        out: list[SummarySentence] = []
        sentences = [x.strip() for x in SENT_SPLIT.split(text.strip()) if len(x.strip().split()) >= 3]
        if not sentences or not source:
            return out
        sims = self.embedder.similarity(sentences, [s.text for s in source])
        for i, sent in enumerate(sentences):
            if self._unsupported_tokens(sent):
                self.removed += 1
                continue
            row = sims[i]
            best = np.argsort(-row)[:2]
            top = float(row[best[0]])
            if self.embedder.semantic and top < 0.25:
                self.removed += 1
                continue
            grounding = "supported" if (top >= 0.4 or not self.embedder.semantic) else "weak"
            if not self._co_occur(self._salient(sent), source) or not self._commitment_supported(sent):
                grounding = "weak"
            ev = [source[j] for j in best if row[j] >= max(0.25, top - 0.15)] or [source[best[0]]]
            sent = re.sub(r"\s+([.,!?])", r"\1", sent)
            out.append(SummarySentence(text=sent, evidence=evidence_for(ev), grounding=grounding))
        return out

    # ------------------------------------------------------------------ abstractive
    def _summarize_lines(self, lines: list[str], max_len: int, min_len: int) -> str:
        chunks = _chunks(lines, self.model.count_tokens)
        summaries = self.model.summarize(chunks, max_length=max_len, min_length=min_len)
        # Reduce step: keep summarising until the combined text fits in a single chunk.
        while len(summaries) > 1:
            joined = " ".join(summaries)
            if self.model.count_tokens(joined) <= max_len * 1.6:
                return joined
            regrouped = _chunks(summaries, self.model.count_tokens)
            summaries = self.model.summarize(regrouped, max_length=max_len, min_length=min_len)
        return summaries[0] if summaries else ""

    def _extractive(self, sentences: Sequence[SentenceRec], k: int) -> list[SummarySentence]:
        content = [
            s for s in sentences
            if len(s.text.split()) >= 6 and not is_question(s.text) and not TRANSITION.match(s.text) and not RECAP.match(s.text)
        ] or [s for s in sentences if len(s.text.split()) >= 3] or list(sentences)
        if not content:
            return []
        cent = _centrality(self.embedder.encode([s.text for s in content]))
        # Sentences that carry a decision, risk or commitment are more summary-worthy.
        boost = np.array([1.6 if s.id in self.salient else 1.0 for s in content])
        cent = cent * boost
        top = sorted(np.argsort(-cent)[:k])
        return [
            SummarySentence(
                text=(f"{content[j].speaker}: " if content[j].speaker else "") + clean_sentence(content[j].text),
                evidence=evidence_for([content[j]]),
            )
            for j in top
        ]

    def build(
        self, topics: list[Topic], decisions: list[Decision], actions: list[ActionItem], risks: Sequence[Risk] = ()
    ) -> Summary:
        by_id = {s.id: s for s in self.t.sentences}
        self.salient = {e.sentence_id for item in [*decisions, *risks] for e in item.evidence[:1]}
        self.actions = actions
        detailed: list[DetailedSummarySection] = []
        method = "abstractive" if self.model is not None else "extractive"
        topic_texts: list[str] = []
        for n, topic in enumerate(topics, start=1):
            sents = [by_id[sid] for sid in topic.sentence_ids if sid in by_id]
            if self.model is not None:
                self.progress(f"Summarising topic {n} of {len(topics)}")
                text = self._summarize_lines(_dialogue(sents), max_len=110, min_len=20)
                grounded = self._ground(text, sents)
                if not grounded:  # everything was filtered: fall back to central sentences
                    grounded = self._extractive(sents, 2)
                topic_texts.append(" ".join(g.text for g in grounded))
            else:
                grounded = self._extractive(sents, 2 if len(sents) < 15 else 3)
            topic.summary = " ".join(g.text for g in grounded)
            detailed.append(DetailedSummarySection(topic_id=topic.id, title=topic.title, sentences=grounded))

        if self.model is not None:
            self.progress("Writing executive summary")
            if len(topics) == 1:
                source_lines = _dialogue(self.t.sentences)
            else:
                source_lines = topic_texts
            executive_text = self._summarize_lines(source_lines, max_len=90, min_len=25)
            executive = self._ground(executive_text, self.t.sentences)
            if not executive:
                executive = self._extractive(self.t.sentences, 3)
        else:
            executive = self._extractive(self.t.sentences, min(4, max(2, len(self.t.sentences) // 12)))

        points: list[KeyPoint] = [kp for topic in topics for kp in topic.key_points]
        return Summary(
            method=method,
            executive=executive,
            detailed=detailed,
            discussion_points=points,
            decision_summary=_decision_summary(decisions),
            follow_up_summary=_follow_up_summary(actions),
            removed_unsupported=self.removed,
        )


def _decision_summary(decisions: list[Decision]) -> str:
    if not decisions:
        return "No explicit decisions were detected in the transcript."
    counts = {k: sum(1 for d in decisions if d.status == k) for k in ("confirmed", "tentative", "rejected")}
    parts = [f"{v} {k}" for k, v in counts.items() if v]
    lead = f"{len(decisions)} decision{'s' if len(decisions) != 1 else ''} detected ({', '.join(parts)})."
    confirmed = [d.text for d in decisions if d.status == "confirmed"][:3]
    if confirmed:
        lead += " Key confirmed: " + " ".join(confirmed)
    return lead


def _follow_up_summary(actions: list[ActionItem]) -> str:
    if not actions:
        return "No action items were detected in the transcript."
    owners = sorted({a.owner for a in actions if a.owner != "Unassigned"})
    unassigned = sum(1 for a in actions if a.owner == "Unassigned")
    dated = sum(1 for a in actions if a.deadline and a.deadline.normalized_date)
    text = f"{len(actions)} action item{'s' if len(actions) != 1 else ''} identified"
    text += f", owned by {', '.join(owners)}" if owners else ""
    text += f". {unassigned} unassigned" if unassigned else ". All have owners"
    text += f"; {dated} with a resolved deadline."
    return text
