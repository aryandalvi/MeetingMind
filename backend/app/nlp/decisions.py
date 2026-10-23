"""Decision detection.

Classifies sentences as confirmed / tentative / rejected decisions using decision cues,
and separates them from suggestions, hypotheticals and questions. A second pass detects
agreements: a proposal followed by explicit agreement from another participant.
Sentence embeddings act as a semantic check on plan-like statements without a strong cue.
"""
from __future__ import annotations

import re
from typing import Optional

from ..schemas import Decision
from .common import RECAP, Embedder, PrototypeScorer, clean_sentence, evidence_for, is_question, sentences_of
from .preprocessing import ParsedTranscript, SentenceRec

DECISION_PROTOTYPES = [
    "We decided to go with the cheaper vendor.",
    "The final decision is to launch in April.",
    "We agreed to move the weekly sync to Thursdays.",
    "The budget increase has been approved.",
    "Let's go with option B then.",
    "We will switch to the new billing system next quarter.",
    "We decided not to support the old browser versions.",
    "Everyone agreed that the redesign is postponed.",
]
NON_DECISION_PROTOTYPES = [
    "Maybe we should consider a different vendor.",
    "What if we launched in April instead?",
    "I think option B might be better.",
    "We could try a weekly sync on Thursdays.",
    "Has anyone looked at the budget numbers?",
    "If we were to switch systems, it would take months.",
    "I'll send the report tomorrow.",
    "The meeting last week was really long.",
]

REJECTED = re.compile(
    r"\b(decided (?:not to|against)|(?:have |'ve )?ruled out|rejected|won't be (?:using|going with|doing|pursuing)|"
    r"(?:are|'re) not (?:going to|gonna) (?:go with|use|do|pursue|move forward with|support)|"
    r"will not (?:go with|use|pursue|proceed with|be using|move forward|support)|"
    r"won't (?:go with|use|pursue|proceed with|move forward|support|be doing)|"
    r"drop(?:ped|ping)? (?:the idea|the plan|support for|the feature)|scrap(?:ped|ping)?|off the table|"
    r"turned (?:it |that )?down|not approved|vetoed|shelve[ds]?|abandon(?:ed|ing)|"
    r"agreed (?:not to|against)|no longer (?:using|going to|planning|support)|not (?:going ahead|moving forward) with|"
    r"(?:is|are|stays?|remains?) out of scope|descoped|de-scoped|cut from (?:the|this) (?:release|scope)|"
    r"we(?:'re| are) not doing|we aren't doing|not doing (?:the|a|any)|we won't (?:go above|go below|exceed|offer|accept|allow|do)|"
    r"we will not (?:go above|go below|exceed|offer|accept|allow|do))\b",
    re.I,
)
TENTATIVE = re.compile(
    r"\b(tentatively|provisionally|for now|for the time being|pending|subject to|leaning towards?|"
    r"probably (?:go with|use|going with|stick with)|likely (?:go with|use|going with)|pencil(?:l?ed)? in|"
    r"until we hear|in principle|soft commit|on hold|for the moment|interim|temporar(?:y|ily)|"
    r"unless|provided that|as long as|assuming|hold off|until we (?:see|know|hear|get|have)|until \w+'s)\b",
    re.I,
)
# "even if it costs more" is a concession, not a condition.
CONDITIONAL = re.compile(r"(?<!even )\b(if|unless|provided that|as long as|assuming|depending on)\b", re.I)
LEADING_CONDITION = re.compile(r"(?i)^(?:if|unless|in case|assuming)\b[^,]{3,80},\s*(?P<main>.+)$")
CONFIRMED_STRONG = re.compile(
    r"\b(we(?:'ve| have)? (?:all )?decided|(?:the )?decision (?:is|was|has been made)|(?:it's|it is) decided|"
    r"we(?:'ve| have)? (?:all )?agreed|(?:all |everyone |everybody )agreed|we(?:'re| are) (?:all )?agreed|"
    r"agreed (?:to|on|that)|let's go (?:with|ahead with)|we(?:'ll| will) go (?:with|ahead with)|"
    r"we(?:'re| are) going (?:to go )?with|final(?:ly)? decided|final decision|(?:has been |was |is |got )?approved|"
    r"approve[sd]? (?:the|it|that)|signed off|sign-off|we(?:'ll| will) (?:move forward|proceed) with|"
    r"(?:we're |we are )?moving forward with|settled on|(?:is |are |has been |was )confirmed|consensus|"
    r"we chose|we(?:'ve| have) chosen|we picked|green[- ]?lit|green[- ]?light(?:ed)?|done deal|locked in|"
    r"lock (?:it|that) in|it's official|we(?:'re| are) committing to|we committed to|ok(?:ay)?,? decided)\b",
    re.I,
)
CONFIRMED_PLAN = re.compile(
    r"^(?:(?:so|then|okay|ok|for now|for the time being|in that case|for this release)[,]?\s+)*"
    r"(?:the plan is(?: to)?|going forward,? we(?:'ll| will)|from now on,? we(?:'ll| will)|"
    r"we(?:'ll| will) (?:(?:tentatively|provisionally|probably|just)\s+)?(?:use|adopt|switch to|stick with|keep|launch|ship|postpone|delay|push|move|cancel|hire|"
    r"allocate|increase|reduce|freeze|stay with|standardi[sz]e on|migrate to|deprecate|release|hold)|"
    r"we(?:'re| are) (?:switching|moving|sticking|migrating|standardi[sz]ing|postponing|delaying|pushing|cancel+ing)|"
    r"the (?:launch|release|deadline|meeting|demo|go-live) (?:is|will be) (?:moved|pushed|postponed|rescheduled|delayed)|"
    r"let's (?:keep|stick with|stay with|hold off|use|go ahead|plan to|plan on|do the \w+ on)|"
    r"(?:the )?[\w -]{3,40} (?:moves|is moving|will move|is moved|gets moved|has moved|is postponed|is rescheduled) to)\b",
    re.I,
)
SUGGESTION = re.compile(
    r"^(?:maybe|perhaps|what if|how about|why don't we|why not|should we|could we|shall we|i suggest|i'd suggest|"
    r"i would suggest|i propose|i'd propose|i recommend|i'd recommend|my suggestion|one option|another option|"
    r"an option|we could|we might|it might|i think we should|i think we could|i wonder|i'd like to propose|"
    r"would it make sense|do we want to|do you think we should|is it worth)\b",
    re.I,
)
HYPOTHETICAL = re.compile(r"\b(hypothetically|in theory|if we were to|suppose|imagine|in an ideal world|would have)\b", re.I)
NOT_DECIDED = re.compile(
    r"\b(haven't (?:decided|agreed)|have not (?:decided|agreed)|not (?:yet )?decided|no decision|undecided|"
    r"still deciding|yet to decide|tbd|to be decided|to be determined|not agreed|don't agree|disagree|"
    r"can't agree|didn't agree|not sure (?:if|whether|we)|need to decide|needs to be decided|before we decide|"
    r"let's decide|we should decide|decide (?:on|later|next))\b",
    re.I,
)
STRONG_AGREE = re.compile(
    r"^(?:agreed|i agree|we agree|totally agree|fully agree|yes,? let's (?:do (?:it|that)|go with (?:it|that))|"
    r"let's do (?:it|that)|approved|deal|that works(?: for (?:me|us))?|works for me|i'm on board|"
    r"i'm fine with that|sounds like a plan|\+1|absolutely,? let's|makes sense,? let's (?:do|go)|"
    r"let's go with (?:it|that)|i'm in|i support that|i second that|seconded|consensus|"
    r"(?:yes,?\s*)?(?:that's|that is) (?:confirmed|right|correct)|confirmed|correct|exactly|"
    r"(?:[\w ]{1,30} )?works for (?:me|us|everyone)|same here)\b",
    re.I,
)
WEAK_AGREE = re.compile(r"^(?:sounds good|sounds great|ok(?:ay)?|fine|sure|yeah|yes|yep|makes sense|good idea|great idea|love it|nice)\b", re.I)
DISAGREE = re.compile(r"\b(but|however|not sure|i disagree|i don't think|concern|worried|what about|instead|hold on|wait)\b", re.I)
TAG_QUESTION = re.compile(r"(?i),?\s*(?:right|correct|isn't it|didn't we|don't we|yes|no|ok(?:ay)?)\s*\?$")
LETS_PROCESS = re.compile(
    r"(?i)^let's\s+(?:get started|start|begin|move on|wrap up|take (?:a|it|this|that)|talk|discuss|figure|"
    r"circle back|revisit|see|look at|recap|go around|jump|keep it short|have a (?:quick )?(?:look|chat)|"
    r"leave|park|think|check|meet|sync|catch up|schedule|regroup|reconvene|follow up|have a follow-up)\b"
)
PROPOSAL_STRIP = re.compile(
    r"^(?:maybe|perhaps|what if|how about|why don't we|why not|should we|could we|shall we|i suggest(?: that)?|"
    r"i'd suggest|i would suggest|i propose(?: that)?|i'd propose|i recommend|i'd recommend|i think we should|"
    r"i think we could|we could|let's)\s+(?:we\s+)?",
    re.I,
)


def _status(text: str) -> Optional[tuple[str, int, str]]:
    """Return (status, strength, kind) for a sentence, or None if it is not a decision."""
    if NOT_DECIDED.search(text) or HYPOTHETICAL.search(text):
        return None
    if is_question(text):
        return None
    conditional_lead = LEADING_CONDITION.match(text)
    if conditional_lead:
        # "If we don't hear back by April 15, we'll invite Dr. Singh instead." -> contingency plan
        main = conditional_lead.group("main")[:1].upper() + conditional_lead.group("main")[1:]
        inner = _status(main)
        if inner:
            return ("tentative", inner[1], inner[2])
        if re.match(r"(?i)^we(?:'ll| will| are going to|'re going to)\s+(?!revisit|reconsider|discuss|talk|review|look|think|see)\w+", main):
            return ("tentative", 2, "decision")
        return None
    suggestion = bool(SUGGESTION.match(text))
    if REJECTED.search(text) and not suggestion:
        return ("rejected", 3, "decision")
    strong = CONFIRMED_STRONG.search(text)
    plan = CONFIRMED_PLAN.match(text)
    if suggestion and not (strong and re.search(r"\b(decided|agreed|approved|decision)\b", text, re.I)):
        return None
    if not strong and not plan:
        return None
    lowered = text.lower()
    kind = "decision"
    if re.search(r"\b(approved|approve[sd]?|signed off|sign-off|green[- ]?l)", lowered):
        kind = "approval"
    elif re.search(r"\b(agreed|consensus|we agree)\b", lowered):
        kind = "agreement"
    if TENTATIVE.search(text) or CONDITIONAL.search(text):
        return ("tentative", 3 if strong else 2, kind)
    return ("confirmed", 3 if strong else 2, kind)


def _proposal_text(text: str) -> str:
    t = PROPOSAL_STRIP.sub("", clean_sentence(text)).strip(" ?.!")
    t = re.sub(r"^(?:we\s+)?(?:should|could|can|go ahead and)\s+", "", t, flags=re.I)
    return (t[:1].upper() + t[1:]) if t else text


class DecisionExtractor:
    def __init__(self, transcript: ParsedTranscript, embedder: Embedder):
        self.t = transcript
        self.embedder = embedder
        self.scorer = PrototypeScorer(embedder, DECISION_PROTOTYPES, NON_DECISION_PROTOTYPES)

    def _agreement_for(self, s: SentenceRec) -> Optional[tuple[list[SentenceRec], bool]]:
        """If a proposal is followed by agreement from someone else, return (reply sentences, strong?)."""
        for utt in self.t.utterances[s.utterance_index + 1 : s.utterance_index + 3]:
            if utt.speaker == s.speaker or not utt.speaker:
                continue
            sents = sentences_of(self.t, utt)
            if not sents:
                continue
            first = clean_sentence(sents[0].text) if len(sents[0].text.split()) > 2 else sents[0].text
            raw_first = sents[0].text.strip()
            if DISAGREE.search(utt.text[:80]):
                return None
            if STRONG_AGREE.match(raw_first) or STRONG_AGREE.match(first):
                return (sents[:1], True)
            if WEAK_AGREE.match(raw_first):
                return (sents[:1], False)
            return None
        return None

    def extract(self) -> list[Decision]:
        found: list[tuple[SentenceRec, str, int, str, list, bool, list[str], str]] = []
        candidates: list[tuple[SentenceRec, str, list, str, int, str]] = []
        for s in self.t.sentences:
            text = clean_sentence(s.text)
            if len(text.split()) < 3 or RECAP.match(text):
                continue
            # "We agreed not to support Android 9, right?" is a statement seeking confirmation.
            statement = TAG_QUESTION.sub(".", text)
            tagged = statement != text
            res = _status(statement)
            if res and re.fullmatch(r"(?i)let's\s+\w+(?:\s+\w+)?\s+(?:it|that|this|them)[.!]?", statement):
                res = None  # "Let's keep that." points back at something; too vague on its own
            if res:
                replies = []
                if tagged:
                    agreement = self._agreement_for(s)
                    if agreement is None:
                        continue  # nobody confirmed the recollection
                    replies = agreement[0]
                candidates.append((s, statement, replies, *res))
                continue
            # Agreement pass: proposal + explicit agreement from another speaker.
            proposal = SUGGESTION.match(text) or (
                re.match(r"(?i)^let's\s+", text) and not LETS_PROCESS.match(text)
            )
            if proposal:
                body = _proposal_text(s.text)
                if len(body.split()) < 3 or re.fullmatch(r"(?i)(?:\w+\s+)?(?:it|that|this|them)", body):
                    continue  # "Let's keep that." - too vague to stand alone as a decision
                agreement = self._agreement_for(s)
                if agreement:
                    replies, strong = agreement
                    reasons = [] if strong else ["Agreement inferred from a brief reply (e.g. 'sounds good')."]
                    status = "tentative" if (TENTATIVE.search(text) or CONDITIONAL.search(text)) else "confirmed"
                    if status == "tentative":
                        reasons.append("Agreed proposal is conditional or provisional.")
                    found.append((s, body, 3 if strong else 2, status, replies, True, reasons, "agreement"))

        margins = self.scorer.margins([c[1] for c in candidates])
        for (s, text, replies, status, strength, kind), margin in zip(candidates, margins):
            reasons: list[str] = []
            if strength < 3 and self.embedder.semantic and margin < -0.05:
                continue  # plan-like wording, but semantically not a decision
            if status == "tentative" and CONDITIONAL.search(text):
                reasons.append("Decision is conditional; check whether the condition was met.")
            if strength < 3:
                reasons.append("Stated as a plan rather than an explicit decision.")
            found.append((s, text, strength, status, replies, False, reasons, kind))

        found.sort(key=lambda f: f[0].index)
        decisions: list[Decision] = []
        texts = [f[1] for f in found]
        vecs = self.embedder.encode(texts) if texts else None
        kept_idx: list[int] = []
        for i, (s, text, strength, status, replies, inferred, reasons, kind) in enumerate(found):
            dup = None
            for k in kept_idx:
                sim = float(vecs[i] @ vecs[k])
                near = abs(s.utterance_index - found[k][0].utterance_index) <= 2
                if sim > (0.88 if self.embedder.semantic else 0.85) or (near and sim > 0.55):
                    dup = k
                    break
            if dup is not None:
                d = decisions[kept_idx.index(dup)]
                d.evidence.extend(e for e in evidence_for([s] + replies) if e.sentence_id not in {x.sentence_id for x in d.evidence})
                continue
            kept_idx.append(i)
            signal = "strong" if strength >= 3 and not inferred else "moderate" if strength >= 2 else "weak"
            decisions.append(
                Decision(
                    id=f"DEC{len(decisions) + 1}",
                    text=text.rstrip(".") + ".",
                    status=status,
                    kind=kind,
                    speaker=s.speaker,
                    is_inferred=inferred,
                    needs_review=bool(reasons),
                    review_reasons=reasons,
                    signal=signal,
                    evidence=evidence_for([s] + replies),
                )
            )
        return decisions
