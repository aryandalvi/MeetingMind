"""Unresolved question detection.

A question is reported when it is substantive (not filler or a meeting-logistics question,
and not a request that the action extractor already handles) and no later turn answers it,
or the answer defers it ("I'll get back to you", "not sure yet"). Explicit open-issue
statements ("this is still unclear", "TBD") are reported too.
"""
from __future__ import annotations

import re

from ..schemas import Question
from .common import Embedder, clean_sentence, evidence_for, is_question, sentences_of
from .preprocessing import ParsedTranscript

# Meeting-logistics questions (matched as a prefix) and one-word fillers (matched as the whole sentence).
FILLER_Q = re.compile(
    r"(?i)^(?:you know|does that make sense|can (?:everyone|you(?: all)?|everybody) (?:hear|see) (?:me|my screen|that)|"
    r"is everyone here|are we ready|shall we (?:start|begin|get started)|should we (?:start|begin|get started)|"
    r"any (?:other )?questions|anything else|any(?:thing| other)? (?:updates?|comments?|thoughts)|how are you|"
    r"how's it going|how was your weekend|who's next|who wants to go (?:first|next)|can we move on|shall we move on|"
    r"is that (?:right|correct|ok)|isn't it|don't you think|what else|any blockers|any risks|where were we|"
    r"can you repeat that|could you repeat that|did i miss anything|is that clear|anyone else)\b"
    r"|^(?:right|ok(?:ay)?|makes sense|sounds? good|yeah|really|ready|sorry|what|huh|everyone good|all good|good|"
    r"clear|correct|agreed|got it)[\s,.!?]*$"
)
REQUEST_Q = re.compile(
    r"(?i)^(?:[A-Z][a-z]+,\s*)?(?:can|could|would|will) (?:you|someone|somebody|anyone)\b|^(?:who can|who will|who wants to)\b"
)
DEFERRAL = re.compile(
    r"(?i)\b(not sure|i'm not sure|don't know|do not know|no idea|unclear|need to check|have to check|let me check|"
    r"get back to you|find out|look into it|tbd|to be determined|to be decided|depends|we'll see|good question|"
    r"haven't decided|not decided|can't say|hard to say|no clue|take (?:it|this|that) offline|park (?:it|that|this)|"
    r"parking lot|revisit|later|next meeting|circle back|decide (?:that|this|it|on (?:that|this|it))? ?(?:later|next|another time)|"
    r"(?:ask|check with) (?:the |our )?\w+ first|figure (?:that|this|it) out|hold off|put (?:that|this|it) on hold|"
    r"at the (?:next |ops |weekly )?(?:sync|meeting|standup|stand-up|call))\b"
)
# Changing the subject is not an answer: "Let's move on to the hiring plan."
TOPIC_CHANGE = re.compile(r"(?i)^(?:ok(?:ay)?|so|alright|right)?[,.]?\s*(?:let's move on|moving on|next (?:item|topic)|let's (?:talk about|turn to|go to) )")
# A hedged reply ("Maybe a recording is safer") is an opinion, not an answer that settles the question.
HEDGED_REPLY = re.compile(r"(?i)^(?:maybe|perhaps|possibly|i guess|i suppose|could be|not sure|hmm|it depends)\b")
OPEN_ISSUE = re.compile(
    r"(?i)\b(still (?:unclear|unknown|open|undecided|up in the air|need to figure out)|(?:is|remains|it's) unclear|"
    r"open question|unresolved|no one knows|nobody knows|we don't know (?:yet )?(?:who|what|when|how|whether|if)|"
    r"we still don't know|we haven't (?:decided|figured out|agreed)|tbd|to be determined|"
    r"(?:need|have) to figure out|up in the air|park(?:ing)? (?:that|this|it)|parking lot|take (?:it|this|that) offline|"
    r"no decision (?:yet|on)|yet to be decided|not decided yet|leave (?:that|this|it) open|(?:still )?open for now|"
    r"(?:don't|do not) have anyone (?:assigned|on it)|no one(?:'s| is)? assigned|nobody(?:'s| is)? assigned|"
    r"figure (?:that|this|it) out (?:offline|later))\b"
)
POINTS_BACK = re.compile(r"(?i)\b(that|this|it)\b")


class QuestionExtractor:
    def __init__(self, transcript: ParsedTranscript, embedder: Embedder):
        self.t = transcript
        self.embedder = embedder

    def _answer_status(self, s) -> tuple[str, list]:
        """Look at the next turns by other speakers: 'answered', 'deferred' or 'unanswered'."""
        later = self.t.utterances[s.utterance_index + 1 : s.utterance_index + 4]
        hedged: list = []
        for utt in later:
            sents = sentences_of(self.t, utt)
            if not sents:
                continue
            reply = " ".join(x.text for x in sents[:2])
            if DEFERRAL.search(reply):
                # Includes the asker deferring it themselves: "Let's decide that next week."
                return "deferred", hedged + sents[:2]
            if TOPIC_CHANGE.match(sents[0].text):
                break
            if utt.speaker is not None and utt.speaker == s.speaker:
                continue
            if all(is_question(x.text) for x in sents[:1]):
                continue
            if HEDGED_REPLY.match(clean_sentence(sents[0].text)) or HEDGED_REPLY.match(sents[0].text):
                hedged.extend(sents[:1])
                continue
            # A substantive reply from someone else counts as an answer (deferrals were caught above).
            short_answer = re.match(r"(?i)^(yes|no|yeah|yep|nope|correct|exactly|definitely|\d)", reply.strip())
            if len(reply.split()) >= 4 or short_answer:
                return "answered", sents[:2]
            return "unanswered", []
        if hedged:  # only tentative replies, but nobody deferred it: treat as (tentatively) answered
            return "answered", hedged
        return "unanswered", []

    def extract(self) -> list[Question]:
        questions: list[Question] = []
        for s in self.t.sentences:
            raw = s.text.strip()
            text = clean_sentence(raw)
            if is_question(raw):
                if len(text.split()) < 4 or FILLER_Q.match(text) or FILLER_Q.match(raw) or REQUEST_Q.match(text):
                    continue
                status, replies = self._answer_status(s)
                if status == "answered":
                    continue
                note = None
                if status == "deferred":
                    note = "A reply deferred the answer or expressed uncertainty."
                questions.append(
                    Question(
                        id=f"Q{len(questions) + 1}",
                        text=text,
                        asked_by=s.speaker,
                        status=status,
                        note=note,
                        evidence=evidence_for([s]),
                        response_evidence=evidence_for(replies),
                    )
                )
            elif OPEN_ISSUE.search(text) and len(text.split()) >= 4:
                statement, referent = text, s
                if len(text.split()) <= 9 and POINTS_BACK.search(text):
                    # "We'll leave that open for now." -> report the earlier sentence it refers to.
                    referent = self._referent(s)
                    if referent is None:
                        continue
                existing = next((q for q in questions if any(e.sentence_id == referent.id for e in q.evidence)), None)
                if existing is not None:
                    existing.response_evidence.extend(evidence_for([s]))
                    continue
                if any(abs(int(e.sentence_id[1:]) - s.index - 1) <= 3 for q in questions for e in q.evidence) and referent is not s:
                    continue  # already covered by a nearby question
                questions.append(
                    Question(
                        id=f"Q{len(questions) + 1}",
                        text=clean_sentence(referent.text).rstrip(".") + ("." if not referent.text.endswith("?") else ""),
                        asked_by=referent.speaker,
                        status="open_issue",
                        note="Left open in the meeting: “" + statement + "”" if referent is not s else "Stated as an open or undecided issue.",
                        evidence=evidence_for([referent] if referent is s else [referent, s]),
                    )
                )
        return questions

    def _referent(self, s):
        for prev in reversed(self.t.sentences[max(0, s.index - 3) : s.index]):
            words = clean_sentence(prev.text).split()
            if len(words) >= 6 and not (len(words) <= 9 and POINTS_BACK.search(prev.text)):
                return prev
        return None
