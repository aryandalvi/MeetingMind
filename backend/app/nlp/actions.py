"""Action item extraction.

Combines (1) linguistic patterns over the cleaned sentence and its spaCy parse, which find the
commitment cue, the owner reference and the task phrase, with (2) a semantic nearest-prototype
score from sentence embeddings, which confirms or vetoes weak pattern matches. Owners are only
taken from the transcript (speaker of a self-commitment, a named person, or the person who
accepts a request); otherwise the item is marked Unassigned.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from ..schemas import ActionItem, Deadline
from .common import (
    RECAP,
    Embedder,
    NameResolver,
    PrototypeScorer,
    clean_sentence,
    evidence_for,
    sentences_of,
)
from .deadlines import DeadlineMatch, best_deadline
from .preprocessing import ParsedTranscript, SentenceRec

ACTION_PROTOTYPES = [
    "I will send the updated report to the client by Friday.",
    "I'll take care of booking the venue.",
    "Can you review the pull request before tomorrow?",
    "Sarah will prepare the slides for the board meeting.",
    "Action item: John to follow up with the vendor about pricing.",
    "Someone needs to update the documentation.",
    "Please schedule a follow-up meeting with the design team.",
    "Let me check with legal and get back to you.",
    "Could you share the budget spreadsheet with everyone?",
    "We need to fix the login bug before the release.",
    "I'm going to draft the proposal this week.",
    "Mike is responsible for testing the payment integration.",
]
NON_ACTION_PROTOTYPES = [
    "I think the design looks really good.",
    "We discussed the budget during the last meeting.",
    "That was a great presentation, thanks everyone.",
    "What do you think about the new logo?",
    "I already sent the report yesterday.",
    "The numbers went up by ten percent last quarter.",
    "I'm not sure that is a good idea.",
    "Let's get started with the agenda.",
    "It would be nice if things were simpler.",
    "We decided to go with the blue color scheme.",
    "Can everyone hear me okay?",
    "I'll be honest, I didn't expect that.",
]

TEAM_WORDS = (
    r"(?:marketing|sales|legal|finance|design|engineering|qa|ops|devops|support|hr|product|security|"
    r"it|data|analytics|research|ux|ui|backend|frontend|mobile|infra|infrastructure|platform|"
    r"leadership|management|procurement|compliance|operations|accounting|content|growth)"
)
TEAM_RE = re.compile(rf"^(?:the\s+)?(?:{TEAM_WORDS}(?:\s+team)?|[A-Z][\w-]+\s+team)$", re.IGNORECASE)

SELF_CUES = [
    (r"(?:will|'ll|shall|am going to|'m going to|am gonna|'m gonna|promise to|commit to|"
     r"am planning to|'m planning to|plan to|intend to|will make sure to|'ll make sure to|"
     r"will make sure|'ll make sure|volunteer to|will be sure to|'ll be sure to)", 3),
    (r"(?:can|could|need to|have to|should|must|got to|'ve got to|ought to)", 2),
    (r"(?:will try to|'ll try to|will try and|'ll try and|might|may|hope to|want to)", 1),
]
OTHER_CUES = [
    (r"(?:will|'ll|is going to|are going to|is gonna|are gonna|shall|is responsible for|are responsible for|"
     r"is in charge of|are in charge of|will own|to|is assigned to|was assigned to|"
     r"will be responsible for)", 3),
    (r"(?:needs to|need to|has to|have to|should|must|can|could)", 2),
    (r"(?:might|may|will try to|wants to)", 1),
]

HEDGES = re.compile(r"\b(maybe|probably|perhaps|i think|i guess|might|try to|try and|hopefully|if i can|if possible)\b", re.I)
PAST_REPORT = re.compile(
    r"^(?:i|we|he|she|they|[A-Z][a-z]+)\s+(?:already\s+|just\s+|also\s+)?(?:sent|did|finished|completed|fixed|shared|"
    r"updated|talked|met|had|was|were|wrote|reviewed|created|called|emailed|spoke|merged|deployed|tested|"
    r"looked|checked|went|made|got)\b",
    re.I,
)
NEGATED = re.compile(
    r"\b(won't|will not|wouldn't|don't need to|do not need to|no need to|not going to|never|can't|cannot|"
    r"shouldn't|should not|doesn't need to|isn't going to)\b",
    re.I,
)
HYPOTHETICAL = re.compile(
    r"\b(if we were to|hypothetically|in theory|suppose|imagine|would be nice|it'd be great if|in an ideal world|"
    r"if only|we could always)\b",
    re.I,
)
# Offers that explicitly withhold commitment.
NOT_A_PROMISE = re.compile(r"(?i)\b(no promises|can't promise|cannot promise|not sure i can|no guarantees?)\b")
PROCESS_TASKS = re.compile(
    r"^(?:share (?:my|the) screen|get started|start(?: the meeting)?|begin|kick (?:it |things )?off|move on|"
    r"wrap (?:it |this |things )?up|go over|talk about|recap|summari[sz]e|repeat|hear|see you|jump|"
    r"be (?:honest|quick|brief|right back|back|there|out|off|away|on vacation|on leave|late|available)|"
    r"keep (?:it|this) (?:short|brief)|hand (?:it )?over|pass (?:it )?(?:over|on)|say|admit|tell you|bet|"
    r"take a (?:step back|look at this together|quick break|break)|stop sharing|mute|unmute|"
    r"go with|stick with|use|choose|pick(?! up)|adopt|keep|move forward with|proceed with|"
    r"think about it|see|wait and see|leave (?:it|that|this)|continue|circle back later|"
    r"tentatively|plan (?:for|on)|aim for|target|figure (?:that|this|it) out|take (?:that|this|it) offline|park|"
    r"meet(?: again| up)?|reconvene|regroup|sync(?: up)?|catch up|"
    r"have (?:a|another) (?:quick )?(?:follow-up|follow up|sync|call|meeting|check-in|catch-up)|"
    r"discuss|talk|go around|introduce|welcome|thank)\b",
    re.I,
)
# Words that carry no task content of their own: "do that", "have it ready", "take care of it then".
VAGUE_FILLER = {
    "that", "it", "this", "those", "these", "them", "the", "same", "one", "too", "as", "well", "then", "later",
    "now", "today", "first", "right", "away", "for", "you", "to", "me", "us", "again", "also", "just",
}
GENERIC_TASK_WORDS = {
    "do", "handle", "take", "care", "of", "have", "get", "send", "finish", "deal", "with", "sort", "own", "grab",
    "check", "look", "at", "into", "cover", "book", "figure", "out", "offline", "ready", "done", "sorted", "over",
    "up", "on", "make", "happen", "work", "it's", "that's",
}
PRONOUN_START = re.compile(r"^([\w']+(?:\s+(?:up|out|on|off|over))?)\s+(?:it|that|this)\b", re.I)
# Split "The crash is on our side, and I'll fix it" into clauses so later commitments are found.
CLAUSE_SPLIT = re.compile(
    r"(?:,|;)\s*(?:and|but|so|then)?\s*(?=(?:i|we|let me|let's|i'll|i will|i'm going to|i can)\b)|"
    r"\s+(?:and|but|so)\s+(?=(?:i'll|i will|i'm going to|i can|let me)\b)",
    re.I,
)
ACCEPT_CUES = re.compile(
    r"^(?:sure|yes|yeah|yep|yup|ok(?:ay)?|absolutely|definitely|of course|no problem|will do|on it|i'm on it|"
    r"sounds good|got it|happy to|i can|i'll|i will|i can do (?:that|it)|i'll do it|i'll take it|consider it done|"
    r"can do|alright|fine|certainly|me|i've got it|i got it|leave it with me)\b",
    re.I,
)
# Acceptance words that answer a request ("Sure, ...", "Yes, I'll ..."), excluding a bare "I'll".
STRICT_ACCEPT = re.compile(
    r"^(?:sure|yes|yeah|yep|yup|ok(?:ay)?|absolutely|definitely|of course|no problem|will do|on it|happy to|"
    r"can do|alright|certainly|me)\b",
    re.I,
)


def _more_specific(current: Optional[DeadlineMatch], new: Optional[DeadlineMatch]) -> Optional[DeadlineMatch]:
    """Keep the existing deadline unless the new one is a resolved, day-level date and the old one is not."""
    if current is None:
        return new
    if new is None:
        return current
    if new.normalized_date and new.granularity == "day" and (current.granularity != "day" or not current.normalized_date):
        return new
    return current


REFUSE_CUES = re.compile(r"^(?:no\b|nope|i can't|i cannot|not me|i won't|unfortunately|sorry,? i)", re.I)
HIGH_PRIORITY = re.compile(r"\b(urgent|urgently|critical|asap|as soon as possible|immediately|top priority|blocker|blocking|highest priority|right away)\b", re.I)
LOW_PRIORITY = re.compile(r"\b(nice to have|when you get a chance|no rush|low priority|eventually|if you have time|whenever)\b", re.I)


@dataclass
class _Candidate:
    sentence: SentenceRec
    cleaned: str
    task: str
    owner_kind: str  # self | named | addressed | someone | collective | none
    owner_ref: Optional[str]
    strength: int
    hedged: bool = False
    vague: bool = False
    margin: float = 0.0
    extra_evidence: list = field(default_factory=list)
    owner: str = "Unassigned"
    owner_source: str = "unassigned"
    deadline: Optional[DeadlineMatch] = None
    reasons: list = field(default_factory=list)
    inferred: bool = False
    _index: int = -1


def _first_token_is_verb(span, text: str) -> bool:
    """True if the task starts with a verb. Without a parser we accept (rules stay permissive)."""
    if span is None or not span.doc.has_annotation("TAG"):
        return True
    first = text.split()[0].lower().strip(",.") if text.split() else ""
    for tok in span:
        if tok.text.lower() == first:
            return tok.pos_ in {"VERB", "AUX"} or tok.tag_ in {"VB", "VBP"}
    return True


def _is_proper_noun(span, word: str) -> bool:
    if span is None or not span.doc.has_annotation("TAG"):
        return False
    for tok in span:
        if tok.text == word:
            return tok.pos_ == "PROPN"
    return False


class ActionExtractor:
    def __init__(
        self,
        transcript: ParsedTranscript,
        embedder: Embedder,
        resolver: NameResolver,
        meeting_date: Optional[date],
        person_entities: set[str],
    ):
        self.t = transcript
        self.embedder = embedder
        self.resolver = resolver
        self.meeting_date = meeting_date
        self.person_entities = person_entities
        self.scorer = PrototypeScorer(embedder, ACTION_PROTOTYPES, NON_ACTION_PROTOTYPES)
        names = resolver.known_name_pattern()
        self.name_alt = rf"(?:{names}|[A-Z][a-z]+(?:\s[A-Z][a-z]+)?)" if names else r"[A-Z][a-z]+(?:\s[A-Z][a-z]+)?"

    # ------------------------------------------------------------------ owner names
    def _owner_name(self, ref: str, span) -> Optional[str]:
        ref = ref.strip().strip(",")
        if " and " in ref:
            parts = [self._owner_name(p, span) for p in ref.split(" and ")]
            return " & ".join(parts) if all(parts) else None
        resolved = self.resolver.resolve(ref)
        if resolved:
            return resolved
        if TEAM_RE.match(ref):
            return ref[4:].strip().title() if ref.lower().startswith("the ") else ref.strip().title()
        if ref in self.person_entities or _is_proper_noun(span, ref.split()[0]):
            if ref.lower() in {"i", "we", "you", "it", "this", "that", "there", "everyone", "everybody", "someone", "nobody"}:
                return None
            return ref
        return None

    # ------------------------------------------------------------------ pattern matching
    def _match(self, s: SentenceRec) -> Optional[_Candidate]:
        cleaned = clean_sentence(s.text)
        if len(cleaned.split()) < 3 or RECAP.match(cleaned):
            return None
        c = self._match_text(s, cleaned)
        if c is not None:
            return c
        parts = CLAUSE_SPLIT.split(cleaned)
        if re.match(r"(?i)^(?:if|unless|in case)\b", parts[0]):
            return None  # "If X happens, we'll do Y" is a contingency (handled as a tentative decision)
        for i in range(1, len(parts)):
            clause = parts[i].strip()
            if not clause:
                continue
            c = self._match_text(s, clause[:1].upper() + clause[1:], allow_imperative=False)
            if c is None:
                continue
            antecedent = self._antecedent(s, " ".join(parts[:i]))
            if antecedent and PRONOUN_START.match(c.task):
                c.task = PRONOUN_START.sub(lambda m: f"{m.group(1)} {antecedent}", c.task, count=1)
            return c
        return None

    @staticmethod
    def _antecedent(s: SentenceRec, before: str) -> Optional[str]:
        """First non-pronoun noun phrase in the earlier clause ("The checkout crash ...")."""
        span = s.span
        if span is None or not span.doc.has_annotation("DEP"):
            return None
        for nc in span.noun_chunks:
            if nc.root.pos_ == "PRON" or nc.text not in before:
                continue
            text = nc.text
            if nc[0].pos_ != "PROPN":
                text = text[:1].lower() + text[1:]
            return text
        return None

    def _match_text(self, s: SentenceRec, text: str, allow_imperative: bool = True) -> Optional[_Candidate]:
        cleaned = text
        if len(text.split()) < 3:
            return None
        if PAST_REPORT.match(text) or HYPOTHETICAL.search(text) or NOT_A_PROMISE.search(text):
            return None
        if re.match(r"(?i)^(?:if|unless|in case)\b[^,]{3,80},", text):
            return None  # contingency plans are handled as tentative decisions
        span = s.span
        hedged = bool(HEDGES.search(text))
        text_nohedge = re.sub(r"^(?:i think|i guess|maybe|probably|perhaps|hopefully)[,]?\s+", "", text, flags=re.I)
        N = self.name_alt

        def cand(task, kind, ref, strength):
            return _Candidate(s, cleaned, task.strip(), kind, ref, strength, hedged=hedged)

        # Explicit action-item labels: "Action item: Priya to send the deck"
        m = re.match(r"(?i)^(?:action items?|action|ai|todo|to-do|follow[- ]up|task|next steps?)\s*[:\-–]\s*(?P<task>.+)", text)
        if m:
            inner = m.group("task")
            m2 = re.match(rf"^(?P<who>{N}(?:\s+and\s+{N})?)\s+(?:to|will|should|needs to)\s+(?P<task>.+)", inner)
            if m2 and self._owner_name(m2.group("who"), span):
                return cand(m2.group("task"), "named", m2.group("who"), 3)
            m3 = re.search(rf"(?:\((?:owner:?\s*)?(?P<who>{N})\)|[-–—]\s*(?P<who2>{N})\s*$)", inner)
            if m3:
                who = m3.group("who") or m3.group("who2")
                return cand(inner[: m3.start()], "named", who, 3)
            return cand(inner, "none", None, 3)

        # Negation only matters near the commitment cue ("I won't send it"), not in a later clause.
        head = " ".join(text_nohedge.split(",")[0].split()[:6])
        if NEGATED.search(head) and not re.search(r"(?i)\bmake sure\b", text):
            return None

        # Self commitments: "I'll send...", "Let me check with legal..."
        for cue, strength in SELF_CUES:
            m = re.match(rf"(?i)^i\s*{cue}\s+(?:also\s+|then\s+|just\s+|go ahead and\s+|definitely\s+|quickly\s+)*(?P<task>.+)", text_nohedge)
            if m:
                task = m.group("task")
                if re.match(r"(?i)^be\s+\w+ing\b", task):  # "I'll be sending the invite"
                    task = task.split(None, 1)[1]
                return cand(task, "self", None, strength)
        m = re.match(r"(?i)^let me\s+(?P<task>.+)", text_nohedge)
        if m:
            return cand(m.group("task"), "self", None, 3)
        m = re.match(r"(?i)^i(?:'m| am) (?:on it|taking (?:that|this|it)|handling (?:that|this|it))", text_nohedge)
        if m:
            return cand("that", "self", None, 3)
        m = re.match(r"(?i)^i(?:'m| am) (?:taking|handling|owning|working on|taking care of)\s+(?P<task>.+)", text_nohedge)
        if m:
            return cand(m.group("task"), "self", None, 2)

        # Requests: "Priya, can you ...", "Could you please ...", "Can someone ..."
        m = re.match(
            rf"(?i:^(?:(?P<voc>{N}),\s*)?(?:can|could|would|will)\s+(?P<who>you(?: guys| two| all)?|someone|somebody|anyone|anybody|one of you|{N})"
            rf"(?:\s+(?:please|maybe|also|quickly|just|possibly))*\s+(?P<task>.+?)\??$)",
            text,
        )
        if m:
            who = m.group("who")
            voc = m.group("voc")
            if who.lower() in {"someone", "somebody", "anyone", "anybody", "one of you"}:
                return cand(m.group("task"), "someone", None, 2)
            if who.lower().startswith("you"):
                if voc and self._owner_name(voc, span):
                    return cand(m.group("task"), "addressed", voc, 3)
                return cand(m.group("task"), "addressed", None, 2)
            if self._owner_name(who, span):
                return cand(m.group("task"), "named", who, 3)
        m = re.match(rf"^(?:(?P<voc>{N}),\s*)?(?i:please)\s+(?P<task>.+)", text)
        if m:
            if m.group("voc") and self._owner_name(m.group("voc"), span):
                return cand(m.group("task"), "addressed", m.group("voc"), 3)
            return cand(m.group("task"), "addressed", None, 2)
        m = re.match(rf"^(?P<voc>{N}),\s*(?i:you)\s*(?i:'ll|will|need to|should|can|have to|are going to|'re going to)\s+(?P<task>.+)", text)
        if m and self._owner_name(m.group("voc"), span):
            return cand(m.group("task"), "addressed", m.group("voc"), 3)
        m = re.match(r"(?i)^who(?:'s| is)? (?:can|will|wants to|is going to|could|would like to|volunteers to|going to)\s+(?P<task>.+?)\?*$", text)
        if m:
            return cand(m.group("task"), "someone", None, 2)
        m = re.match(r"(?i)^who(?:'s| is| are)\s+(?P<verb>\w+ing)\b\s*(?P<rest>.*?)\?*$", text)
        if m and m.group("verb").lower() not in {"going", "doing", "coming", "joining", "speaking", "talking", "missing"}:
            # "Who's picking up the date range picker?" -> "pick up the date range picker"
            verb = m.group("verb")
            lemma = next((tok.lemma_ for tok in (span or []) if tok.text == verb and tok.lemma_), None)
            return cand(f"{lemma or verb} {m.group('rest')}", "someone", None, 2)
        m = re.match(r"(?i)^(?:someone|somebody|one of us)\s+(?:needs to|should|has to|must|will need to|ought to)\s+(?P<task>.+)", text)
        if m:
            return cand(m.group("task"), "someone", None, 2)
        m = re.match(r"(?i)^we(?:'ll| will)? need (?:someone|somebody) to\s+(?P<task>.+)", text)
        if m:
            return cand(m.group("task"), "someone", None, 2)
        m = re.match(rf"^(?P<voc>{N}),\s*(?P<task>[a-z].+)", text)
        if m and self._owner_name(m.group("voc"), span) and _first_token_is_verb(span, m.group("task")) and not text.endswith("?"):
            return cand(m.group("task"), "addressed", m.group("voc"), 3)

        # Assignments: "Assign the bug to Marcus", "Marcus is assigned the bug"
        m = re.match(rf"(?i:^(?:let's |we'll |i'll |i will |we will )?(?:assign|give|hand)\s+)(?P<task>.+?)\s+(?i:to)\s+(?P<who>{N})\.?$", text)
        if m and self._owner_name(m.group("who"), span):
            return cand(m.group("task"), "named", m.group("who"), 3)

        # Named commitments: "Marcus will fix...", "Elena to contact the vendor"
        for cue, strength in OTHER_CUES:
            m = re.match(rf"^(?P<who>(?:[Tt]he\s+)?{N}(?:\s+and\s+{N})?(?:\s+team)?)\s*(?P<cue>(?i:{cue}))\s+(?:also\s+|then\s+|go ahead and\s+)*(?P<task>.+)", text_nohedge)
            if m:
                if not self._owner_name(m.group("who"), span):
                    continue
                # Minutes style "Elena to contact the vendor" needs a verb after "to".
                if m.group("cue").lower() == "to" and not _first_token_is_verb(span, m.group("task")):
                    continue
                return cand(m.group("task"), "named", m.group("who"), strength)

        # Collective: "We need to...", "Let's schedule..."
        m = re.match(r"(?i)^we(?:'ll| will|'re going to| are going to| need to| have to| should| must|'ve got to| got to| ought to)\s+(?:also\s+|then\s+)?(?P<task>.+)", text_nohedge)
        if m:
            if hedged and re.match(r"(?i)^we\s+should", text_nohedge):
                return None  # "I think we should move the date" is a suggestion, not a commitment
            if re.match(r"(?i)^we\s+(?:should|could|might|may)\s+(?:consider|think about|look into whether|explore)", text_nohedge):
                return None
            strong = re.match(r"(?i)^we(?:'ll| will|'re going to| are going to)", text_nohedge)
            return cand(m.group("task"), "collective", None, 2 if not strong else 1)
        m = re.match(r"(?i)^let's\s+(?:also\s+|make sure (?:we|to)\s+)?(?P<task>.+)", text_nohedge)
        if m:
            return cand(m.group("task"), "collective", None, 1)

        # Bare imperative ("Send the minutes to everyone.")
        if allow_imperative and span is not None and span.doc.has_annotation("DEP") and not text.endswith("?"):
            skip = {"so", "and", "okay", "ok", "also", "then", "please", "thanks", "thank", "you", "great", "good",
                    "perfect", "right", "alright", "well", "now", "sure"}
            first = next((t for t in span if not t.is_punct and t.lower_ not in skip), None)
            if first is not None and first.tag_ in {"VB", "VBP"} and first.dep_ == "ROOT" and not any(t.dep_ == "nsubj" for t in first.children):
                return cand(text, "none", None, 1)
        return None

    # ------------------------------------------------------------------ cleanup
    def _clean_task(self, c: _Candidate) -> str:
        task = c.task.strip()
        if c.deadline:
            task = re.sub(re.escape(c.deadline.text), "", task, flags=re.I)
        task = re.sub(r"(?i)\b(?:please|for me|for us|if you can|if possible|if you could|as well|too|real quick|quickly)\b", "", task)
        task = re.sub(r"(?i)[,;]?\s*(?:right|okay|ok|yeah|thanks|thank you|alright)\s*[?.!]*\s*$", "", task)
        task = re.sub(r"(?i)^(?:go ahead and|try to|try and|make sure to|be sure to|also|then|just)\s+", "", task)
        task = re.sub(r"\s+([,.;:!?])", r"\1", task)
        task = re.sub(r"\s{2,}", " ", task).strip(" ,;:-.?!")
        requester = c.sentence.speaker
        if c.owner_kind in {"addressed", "someone", "named"} and requester:
            task = re.sub(r"\bme\b", requester, task)
            task = re.sub(r"\bmy\b", f"{requester}'s", task)
        if c.owner_kind == "self" and c.sentence.speaker:
            task = re.sub(r"\bmy\b", f"{c.sentence.speaker}'s", task)
        return task[:1].upper() + task[1:] if task else task

    def _is_vague(self, task: str, deadline: Optional[DeadlineMatch] = None) -> bool:
        """True when the task only points back at something said earlier ("do that", "book it then")."""
        stripped = re.sub(re.escape(deadline.text), "", task, flags=re.I) if deadline else task
        stripped = re.sub(r"(?i)\b(?:for|by|before) (?:the |our )?next (?:meeting|call|sync|session)\b", "", stripped)
        stripped = re.sub(r"(?i)\b(by|before|until)\b.*$", "", stripped)
        # Judge only the first clause: "do it, I have the template already" -> "do it".
        stripped = re.split(r"(?i),\s+|\s+(?:because|since|as)\s+", stripped)[0]
        stripped = re.sub(r"\s+(?:to|for|with|over to)\s+[A-Z][\w-]*\s*$", "", stripped.strip(" .,!?"))
        words = [w.lower() for w in re.findall(r"[\w']+", stripped)]
        content = [w for w in words if w not in VAGUE_FILLER]
        return len(content) <= 1 or all(w in GENERIC_TASK_WORDS for w in content)

    # ------------------------------------------------------------------ main
    def extract(self) -> list[ActionItem]:
        cands: list[_Candidate] = []
        for s in self.t.sentences:
            c = self._match(s)
            if c is None:
                continue
            c.deadline = best_deadline(c.sentence.text, self.meeting_date)
            c.vague = self._is_vague(c.task, c.deadline)
            if not c.vague and PROCESS_TASKS.match(c.task.strip()):
                continue
            cands.append(c)

        margins = self.scorer.margins([c.cleaned for c in cands])
        semantic = self.embedder.semantic
        kept: list[_Candidate] = []
        for c, margin in zip(cands, margins):
            c.margin = float(margin) if semantic else 0.0
            if c.vague:
                kept.append(c)
                continue
            if c.strength >= 3:
                if c.margin < -0.15:
                    c.reasons.append("Wording matches a commitment pattern but reads semantically unlike a task.")
                kept.append(c)
            elif c.strength == 2 and c.margin > -0.06:
                kept.append(c)
            elif c.strength == 1 and c.margin > (0.06 if semantic else 1.0):
                kept.append(c)
        return self._finalise(kept)

    def _related(self, a: _Candidate, b: _Candidate) -> bool:
        if not self.embedder.semantic:
            return False
        return float(self.embedder.similarity([a.task], [b.task])[0][0]) > 0.45

    def _resolve_owner(self, c: _Candidate) -> None:
        s = c.sentence
        if c.owner_kind == "self":
            if s.speaker:
                c.owner, c.owner_source = s.speaker, "self_commitment"
            else:
                c.reasons.append("Self-commitment ('I') but the speaker is not labelled.")
            return
        if c.owner_kind in {"named", "addressed"} and c.owner_ref:
            name = self._owner_name(c.owner_ref, s.span)
            if name:
                c.owner = name
                c.owner_source = "explicit_name" if c.owner_kind == "named" else "addressed_request"
                return
        if c.owner_kind in {"addressed", "someone"}:
            for utt in self.t.utterances[s.utterance_index + 1 : s.utterance_index + 3]:
                if not utt.speaker or utt.speaker == s.speaker:
                    continue
                reply = clean_sentence(utt.text)
                first = re.split(r"(?<=[.!?])\s", utt.text.strip())[0]
                if REFUSE_CUES.match(first):
                    c.reasons.append(f"{utt.speaker} appears to decline the request.")
                    break
                if ACCEPT_CUES.match(first) or ACCEPT_CUES.match(reply):
                    c.owner, c.owner_source, c.inferred = utt.speaker, "inferred_from_reply", True
                    reply_sents = sentences_of(self.t, utt)[:2]
                    c.extra_evidence.extend(reply_sents)
                    if not c.deadline:
                        for rs in reply_sents:
                            d = best_deadline(rs.text, self.meeting_date)
                            if d:
                                c.deadline = d
                                break
                    c.reasons.append(f"Owner inferred from {utt.speaker}'s reply.")
                    return
                break
            if c.owner_kind == "addressed":
                c.reasons.append("Request addressed to 'you' but the addressee is not clear.")
            else:
                c.reasons.append("Request for a volunteer; nobody clearly accepted it.")
        elif c.owner_kind == "collective":
            c.reasons.append("Collective commitment ('we'/'let's'); no individual owner was named.")
        elif c.owner_kind == "named" and c.owner_ref:
            c.reasons.append(f"'{c.owner_ref}' could not be matched to a known participant.")
        else:
            c.reasons.append("No owner mentioned.")

    def _finalise(self, cands: list[_Candidate]) -> list[ActionItem]:
        items: list[_Candidate] = []
        for c in cands:
            if c.vague:
                # "Sure, I'll do that by Thursday" -> attach to the request it answers.
                target = next(
                    (
                        p for p in reversed(items)
                        if 0 < c.sentence.utterance_index - p.sentence.utterance_index <= 2
                        and p.sentence.speaker != c.sentence.speaker
                    ),
                    None,
                )
                # "Great, please do that before Monday" -> the request refers to an offer just made.
                follow_up_request = c.owner_kind in {"addressed", "none"} and target is not None
                if target is not None and ((c.owner_kind == "self" and c.sentence.speaker) or follow_up_request):
                    if target.owner == "Unassigned" and c.owner_kind == "self":
                        target.owner, target.owner_source, target.inferred = c.sentence.speaker, "inferred_from_reply", True
                        target.reasons = [r for r in target.reasons if "addressee" not in r and "volunteer" not in r and "No owner" not in r]
                        target.reasons.append(f"Owner inferred from {c.sentence.speaker}'s reply.")
                    if c.sentence not in target.extra_evidence:
                        target.extra_evidence.append(c.sentence)
                    target.deadline = _more_specific(target.deadline, c.deadline)
                continue
            if c.owner_kind == "self" and c.sentence.speaker:
                # "Hannah, can you get the deposit approved?" / "Yes, I'll ask Victor for approval tomorrow."
                target = next(
                    (
                        p for p in reversed(items)
                        if p.owner_kind in {"addressed", "named", "someone"}
                        and 0 < c.sentence.utterance_index - p.sentence.utterance_index <= 2
                        and p.sentence.speaker != c.sentence.speaker
                        and p.owner in (c.sentence.speaker, "Unassigned")
                    ),
                    None,
                )
                if target is not None and (STRICT_ACCEPT.match(c.sentence.text) or self._related(target, c)):
                    if target.owner == "Unassigned":
                        target.owner, target.owner_source, target.inferred = c.sentence.speaker, "inferred_from_reply", True
                        target.reasons = [r for r in target.reasons if "volunteer" not in r and "addressee" not in r]
                        target.reasons.append(f"Owner inferred from {c.sentence.speaker}'s reply.")
                    if c.sentence not in target.extra_evidence:
                        target.extra_evidence.append(c.sentence)
                    target.deadline = _more_specific(target.deadline, c.deadline)
                    continue
            if c.owner_kind == "none" and items and items[-1].sentence.utterance_id == c.sentence.utterance_id \
                    and items[-1].owner_kind in {"addressed", "named"}:
                # "Derek, set up a call with their CTO. Bring Lucia." -> one task with two steps.
                items[-1].extra_evidence.append(c.sentence)
                items[-1].deadline = _more_specific(items[-1].deadline, c.deadline)
                continue
            self._resolve_owner(c)
            items.append(c)

        # Merge near-duplicates (same task restated later in the meeting).
        results: list[_Candidate] = []
        tasks = [self._clean_task(c) for c in items]
        vecs = self.embedder.encode(tasks) if tasks else None
        for i, c in enumerate(items):
            dup = None
            for j in range(len(results)):
                k = results[j]._index
                sim = float(vecs[i] @ vecs[k])
                same_owner = c.owner == results[j].owner or "Unassigned" in (c.owner, results[j].owner)
                if sim >= (0.86 if self.embedder.semantic else 0.8) and same_owner:
                    dup = j
                    break
            if dup is None:
                c._index = i
                results.append(c)
            else:
                keep = results[dup]
                keep.extra_evidence.append(c.sentence)
                if c.strength > keep.strength or (c.strength == keep.strength and keep.hedged and not c.hedged):
                    keep._index, keep.strength, keep.hedged = i, c.strength, c.hedged  # use the clearer wording
                if keep.owner == "Unassigned" and c.owner != "Unassigned":
                    keep.owner, keep.owner_source = c.owner, c.owner_source
                    keep.reasons = [r for r in keep.reasons if "owner" not in r.lower() and "addressee" not in r]
                if not keep.deadline and c.deadline:
                    keep.deadline = c.deadline

        out: list[ActionItem] = []
        for n, c in enumerate(results, start=1):
            aid = f"A{n}"
            description = tasks[c._index]
            if not description:
                continue
            reasons = list(dict.fromkeys(c.reasons))
            if c.hedged:
                reasons.append("Tentative wording (e.g. 'maybe', 'try to').")
            deadline = None
            if c.deadline:
                d = c.deadline
                deadline = Deadline(
                    id=f"D-{aid}",
                    text=d.text,
                    normalized_date=d.normalized_date,
                    date_type=d.date_type,
                    granularity=d.granularity,
                    is_ambiguous=d.is_ambiguous,
                    note=d.note,
                    related_action_id=aid,
                    evidence=evidence_for([c.sentence] + [e for e in c.extra_evidence if d.text in e.text]),
                )
                if d.is_ambiguous:
                    reasons.append(f"Deadline '{d.text}' is ambiguous or not a specific day.")
            score = c.strength + (c.margin * 5 if self.embedder.semantic else 0)
            signal = "strong" if score >= 3.2 else "moderate" if score >= 2.0 else "weak"
            if signal == "weak":
                reasons.append("Weak extraction signal.")
            text_for_priority = " ".join([c.sentence.text] + [e.text for e in c.extra_evidence])
            priority = "medium"
            if HIGH_PRIORITY.search(text_for_priority) or (
                deadline and deadline.normalized_date and self.meeting_date
                and deadline.normalized_date - self.meeting_date <= timedelta(days=2)
            ):
                priority = "high"
            elif LOW_PRIORITY.search(text_for_priority):
                priority = "low"
            out.append(
                ActionItem(
                    id=aid,
                    description=description,
                    owner=c.owner,
                    owner_source=c.owner_source,
                    deadline=deadline,
                    priority=priority,
                    is_inferred=c.inferred,
                    needs_review=bool(reasons) or c.owner == "Unassigned",
                    review_reasons=reasons,
                    signal=signal,
                    evidence=evidence_for([c.sentence] + c.extra_evidence),
                )
            )
        return out
