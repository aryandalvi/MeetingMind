"""Named entity recognition (spaCy) merged with speaker labels, plus per-person statistics."""
from __future__ import annotations

import re
from collections import defaultdict

from ..schemas import Entity, Person
from .common import evidence_for
from .preprocessing import ParsedTranscript

LABELS = {
    "PERSON": "People",
    "ORG": "Organizations",
    "GPE": "Locations (countries, cities)",
    "LOC": "Locations",
    "FAC": "Facilities",
    "DATE": "Dates",
    "TIME": "Times",
    "MONEY": "Money",
    "PRODUCT": "Products",
    "EVENT": "Events",
    "NORP": "Groups / nationalities",
    "PERCENT": "Percentages",
    "LAW": "Laws / regulations",
    "WORK_OF_ART": "Titles / documents",
}
STOP = {
    "i", "we", "you", "he", "she", "they", "it", "this", "that", "today", "everyone", "everybody", "someone",
    "okay", "ok", "yeah", "yes", "no", "thanks", "hi", "hello", "um", "uh", "hmm", "great", "sure", "q", "eod",
}


# Common business/tech acronyms that the small spaCy model often mislabels as organisations.
GENERIC_ACRONYMS = {
    "sdk", "eta", "faq", "qa", "api", "apis", "ui", "ux", "kpi", "kpis", "roi", "ceo", "cto", "cfo", "coo", "pr", "hr",
    "it", "eod", "eow", "asap", "mvp", "okr", "okrs", "sla", "slas", "crm", "ai", "ml", "pdf", "url", "db", "sql",
    "q1", "q2", "q3", "q4", "fyi", "tbd", "poc", "rfp", "sow", "nda", "b2b", "b2c", "saas", "cicd", "ci", "cd", "seo",
}
GENERIC_DATES = re.compile(
    r"(?i)^(?:(?:this|that|next|last|the|a|one|same)\s+)?(?:week|month|year|day|quarter|time|weekend|morning|afternoon|"
    r"evening|night|today|now|launch week)$"
)


def _norm(text: str) -> str:
    text = re.sub(r"^(?:the|a|an)\s+", "", text.strip(), flags=re.I)
    text = re.sub(r"'s$", "", text)
    return text.strip(" .,;:!?\"'()")


def extract_entities(t: ParsedTranscript, has_ner: bool) -> list[Entity]:
    speaker_lookup = {}
    for sp in t.speakers:
        speaker_lookup[sp.lower()] = sp
        parts = sp.split()
        if len(parts) > 1:
            speaker_lookup.setdefault(parts[0].lower(), sp)

    buckets: dict[tuple[str, str], dict] = {}
    if has_ner:
        for s in t.sentences:
            for ent in s.span.ents:
                if ent.label_ not in LABELS:
                    continue
                text = _norm(ent.text)
                if len(text) < 2 or text.lower() in STOP or not re.search(r"[A-Za-z0-9]", text):
                    continue
                label = ent.label_
                if label in {"ORG", "PRODUCT", "GPE"} and text.lower() in GENERIC_ACRONYMS:
                    continue
                if label in {"DATE", "TIME"} and GENERIC_DATES.match(text):
                    continue
                if label in {"PERSON", "ORG", "GPE", "NORP", "PRODUCT"} and text.lower() in speaker_lookup:
                    text, label = speaker_lookup[text.lower()], "PERSON"
                if label == "PERSON" and text.islower():
                    continue
                key = (text.lower(), label)
                b = buckets.setdefault(key, {"text": text, "label": label, "count": 0, "sents": [], "source": "ner"})
                b["count"] += 1
                if len(b["sents"]) < 5 and s not in b["sents"]:
                    b["sents"].append(s)

    for sp in t.speakers:
        key = (sp.lower(), "PERSON")
        if key in buckets:
            buckets[key]["source"] = "ner+speaker_label"
        else:
            first = next((s for s in t.sentences if s.speaker == sp), None)
            buckets[key] = {"text": sp, "label": "PERSON", "count": 0, "sents": [first] if first else [], "source": "speaker_label"}

    entities = [
        Entity(
            text=b["text"],
            label=b["label"],
            label_description=LABELS.get(b["label"], b["label"]),
            count=b["count"],
            source=b["source"],
            evidence=evidence_for([x for x in b["sents"] if x is not None]),
        )
        for b in buckets.values()
    ]
    order = list(LABELS)
    entities.sort(key=lambda e: (order.index(e.label) if e.label in order else 99, -e.count, e.text.lower()))
    return entities


def people_stats(t: ParsedTranscript, entities: list[Entity]) -> list[Person]:
    words: dict[str, int] = defaultdict(int)
    utterances: dict[str, int] = defaultdict(int)
    for u in t.utterances:
        if u.speaker:
            words[u.speaker] += len(u.text.split())
            utterances[u.speaker] += 1
    total = sum(words.values()) or 1
    mentions = {e.text: e.count for e in entities if e.label == "PERSON"}
    people = [
        Person(
            name=sp,
            is_speaker=True,
            utterances=utterances[sp],
            words=words[sp],
            talk_share=round(100 * words[sp] / total, 1),
            mentions=mentions.get(sp, 0),
        )
        for sp in t.speakers
    ]
    for e in entities:
        if e.label == "PERSON" and e.text not in t.speakers:
            people.append(Person(name=e.text, is_speaker=False, mentions=e.count))
    return people
