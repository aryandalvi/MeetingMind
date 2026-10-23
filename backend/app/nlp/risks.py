"""Risk and blocker detection with evidence, a kind (risk vs blocker) and a heuristic severity."""
from __future__ import annotations

import re

from ..schemas import Risk
from .common import ANAPHORIC, RECAP, Embedder, PrototypeScorer, clean_sentence, evidence_for, is_question
from .preprocessing import ParsedTranscript

RISK_PROTOTYPES = [
    "I'm worried we won't hit the launch date.",
    "The main risk is that the vendor delivers late.",
    "We're blocked until the API keys arrive.",
    "There's a critical bug in the payment flow.",
    "We might go over budget on this project.",
    "The team is short-staffed this month.",
    "We can't continue until legal approves the contract.",
    "The server keeps crashing under load.",
]
NON_RISK_PROTOTYPES = [
    "Everything is on track for the release.",
    "The demo went really well yesterday.",
    "I'll send the notes after the meeting.",
    "We decided to use the new design.",
    "Thanks everyone for joining today.",
    "No blockers from my side.",
]

BLOCKER = re.compile(
    r"\b(blocked|blocker|blocking|waiting (?:on|for)|stuck|can't (?:proceed|continue|move forward|start|ship|release|deploy|test)|"
    r"cannot (?:proceed|continue|move forward|start|ship|release|deploy|test)|held up|on hold until|"
    r"(?:can't|cannot|unable to) (?:run|access|use|log ?in|reach|connect|build|merge)\b.{0,60}\bbecause|"
    r"until we (?:get|receive|have|hear)|dependent on|depends on (?!who\b|what\b|whether\b|how\b|when\b)|dependency|"
    r"haven't (?:received|got(?:ten)?|heard)|"
    r"still (?:don't|do not) have|no access|lack(?:ing)? access|need (?:approval|sign-off|access) (?:before|to))\b",
    re.I,
)
RISK = re.compile(
    r"\b(risks?|risky|concern(?:ed|s)?|worr(?:ied|y|ying)|afraid|nervous|danger|threat|jeopardi[sz]e|"
    r"at risk|might not (?:make|be ready|finish|hit)|may not (?:make|be ready|finish|hit)|won't (?:make it|be ready|finish)|"
    r"not going to make it|behind schedule|falling behind|slip(?:ping|page)?|delay(?:ed|s)?|late|"
    r"over budget|overspend|budget (?:cut|overrun)|short[- ]staffed|understaffed|bandwidth|capacity|"
    r"bottleneck|bugs?|crash(?:es|ing)?|outage|downtime|fail(?:ing|ure|s|ed)?|broken|unstable|regression|"
    r"vulnerabilit(?:y|ies)|security (?:issue|hole|risk)|breach|compliance|leak|data loss|"
    r"tight (?:deadline|timeline|schedule)|timeline is tight|aggressive (?:timeline|deadline)|"
    r"issue|problem|challenge|tricky|difficult|unclear requirements|scope creep|churn|complain(?:t|ts|ing)|"
    r"(?:has been|is|are|very|too) slow|taking (?:too |so )?long|overdue|still (?:waiting|pending)|no response|"
    r"rate[- ]limit\w*|throttl\w*|keeps? (?:failing|crashing|breaking|timing out|getting|cancel\w*)|timing out|time[- ]?outs?|"
    r"worries|corrupt\w*|(?:is|are|has been|have been|was|went) down|gone (?:quiet|silent|dark)|not responding|"
    r"unresponsive|no reply|still nothing|competitors?|los(?:e|ing) (?:the|a|our) (?:deal|customer|client|account)|"
    r"outdated|out of date|old (?:prices|pricing|version)|(?:still )?(?:hasn't|haven't|has not|have not) been "
    r"(?:published|updated|fixed|released|approved|installed|signed|delivered)|shortfall|short of|below (?:target|plan)|"
    r"behind (?:target|plan)|only have|never done|not sustainable|unsustainable|running (?:low|out)|run out|"
    r"waiting times?|wait times?|long (?:waits?|queues?)|missed|missing|cancel+ing|understaff\w*)\b",
    re.I,
)
NEGATED_RISK = re.compile(
    r"\b(no (?:blockers?|risks?|issues?|problems?|concerns?)|not (?:a|any) (?:concern|problem|issue|risk|blocker)|"
    r"nothing blocking|no longer (?:blocked|an issue|a problem)|isn't (?:a|an) (?:issue|problem|concern|risk)|"
    r"(?:fixed|resolved|solved) (?:the|that|it)|unblocked|no worries|not worried|don't worry|no problem|"
    r"on track|under control)\b",
    re.I,
)
HIGH = re.compile(
    r"\b(critical|severe|serious|major|huge|big|blocker|blocked|can't ship|cannot ship|launch|deadline|security|"
    r"breach|data loss|outage|compliance|lawsuit|customers? (?:are )?(?:leaving|churn)|showstopper|show-stopper|"
    r"miss (?:the )?(?:launch|deadline)|won't make it)\b",
    re.I,
)
LOW = re.compile(r"\b(minor|small|slight|little|low risk|cosmetic|nit|not a big deal|edge case)\b", re.I)
PROCESS_QUESTIONS = re.compile(r"(?i)^(any|are there any|do we have any|anything)\b.*\b(blockers?|risks?|concerns?|issues?)\b")
COMMITMENT_START = re.compile(r"(?i)^(?:i(?:'ll| will| can| am going to|'m going to)|let me|we(?:'ll| will) (?:go with|use|invite))\b")
SUGGESTION_ONLY = re.compile(r"(?i)\b(i think we should|we should|let's|maybe we|i suggest|i propose|i'd prefer|we could)\b")
EXPLICIT = re.compile(
    r"(?i)\b(risks?|blockers?|blocked|concern(?:ed|s)?|worr(?:ied|y)|issues?|problems?|at risk|"
    r"(?:has been|is|are|very|too) slow|taking (?:too |so )?long|overdue|still waiting|behind schedule|"
    r"rate[- ]limited|throttled|keeps? (?:failing|crashing|breaking|timing out))\b"
)


class RiskExtractor:
    def __init__(self, transcript: ParsedTranscript, embedder: Embedder):
        self.t = transcript
        self.embedder = embedder
        self.scorer = PrototypeScorer(embedder, RISK_PROTOTYPES, NON_RISK_PROTOTYPES)

    def extract(self) -> list[Risk]:
        cands = []
        for s in self.t.sentences:
            text = clean_sentence(s.text)
            if len(text.split()) < 4 or NEGATED_RISK.search(text) or PROCESS_QUESTIONS.match(text):
                continue
            if RECAP.match(text) or (ANAPHORIC.match(text) and len(text.split()) <= 6):
                continue  # recaps repeat earlier items; "That's a real risk." has no content of its own
            if SUGGESTION_ONLY.search(text) and not EXPLICIT.search(text):
                continue
            if COMMITMENT_START.match(text) and not EXPLICIT.search(text):
                continue  # "I'll place an emergency order..." is an action, not a risk statement
            if is_question(text) and not re.search(r"(?i)\b(what if .* (fail|late|delay)|are we at risk)\b", text):
                continue
            blocker = BLOCKER.search(text)
            risk = RISK.search(text)
            if not blocker and not risk:
                continue
            cands.append((s, text, bool(blocker)))

        margins = self.scorer.margins([c[1] for c in cands])
        risks: list[Risk] = []
        texts: list[str] = []
        for (s, text, is_blocker), margin in zip(cands, margins):
            margin = float(margin) if self.embedder.semantic else 0.0
            explicit = bool(EXPLICIT.search(text))
            # The prototype margin is a weak signal on its own (see evaluation), so it only vetoes
            # sentences that read clearly unlike a problem statement.
            threshold = -0.15 if is_blocker else -0.05 if explicit else -0.02
            if self.embedder.semantic and margin < threshold:
                continue
            if not self.embedder.semantic and not (is_blocker or explicit):
                continue
            if texts:
                sims = self.embedder.similarity([text], texts)[0]
                j = int(sims.argmax())
                if sims[j] > 0.85:
                    risks[j].evidence.extend(evidence_for([s]))
                    continue
            severity = "high" if HIGH.search(text) else "low" if LOW.search(text) else "medium"
            reasons = []
            signal = "strong" if margin > 0.1 or (explicit and margin > 0) else "moderate" if margin > -0.02 else "weak"
            if signal == "weak":
                reasons.append("Weak signal: the sentence mentions a problem word but may not be a real risk.")
            texts.append(text)
            risks.append(
                Risk(
                    id=f"R{len(risks) + 1}",
                    text=text.rstrip(".") + ".",
                    kind="blocker" if is_blocker else "risk",
                    severity=severity,
                    speaker=s.speaker,
                    needs_review=bool(reasons),
                    review_reasons=reasons,
                    signal=signal,
                    evidence=evidence_for([s]),
                )
            )
        return risks
