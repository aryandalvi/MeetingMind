"""Model-loading failures, long transcripts (hierarchical summarization) and the real abstractive model."""
import dataclasses

import pytest

from app.config import get_settings
from app.nlp.models import ModelRegistry, ModelUnavailableError
from app.nlp.pipeline import analyze
from app.nlp.summarizer import SummaryBuilder, _chunks
from app.schemas import AnalyzeRequest
from conftest import MEETING_DATE

TEXT = (
    "Ann: I'll send the budget spreadsheet to finance by Friday.\n"
    "Ben: We decided to go with the cheaper hosting provider.\n"
    "Cara: I'm worried the migration could delay the launch.\n"
    "Ann: Who will update the customer FAQ?\n"
)


def _broken(*_):
    raise OSError("simulated download failure")


def test_registry_records_failure_and_raises():
    reg = ModelRegistry(dataclasses.replace(get_settings(), summary_mode="abstractive"))
    reg._slots["summarizer"].loader = _broken
    with pytest.raises(ModelUnavailableError):
        reg.get("summarizer")
    status = {s["role"]: s for s in reg.status()}["abstractive summarization"]
    assert status["state"] == "failed" and "simulated" in status["error"]
    reg.reset_failures()
    assert reg.state("summarizer") == "not_loaded"


def test_summarizer_failure_falls_back_to_extractive(registry):
    reg = ModelRegistry(dataclasses.replace(registry.settings, summary_mode="abstractive"))
    reg._slots["spacy"] = registry._slots["spacy"]
    reg._slots["embeddings"] = registry._slots["embeddings"]
    reg._slots["summarizer"].loader = _broken
    report = analyze(AnalyzeRequest(transcript=TEXT, meeting_date=MEETING_DATE), registry=reg)
    assert report.summary.method == "extractive"
    assert any("Summarization model could not be loaded" in w for w in report.warnings)
    assert report.action_items  # the rest of the pipeline still ran


def test_all_models_failing_still_produces_a_report(registry):
    reg = ModelRegistry(dataclasses.replace(registry.settings, summary_mode="abstractive"))
    for key in reg.keys():
        reg._slots[key].loader = _broken
    report = analyze(AnalyzeRequest(transcript=TEXT, meeting_date=MEETING_DATE), registry=reg)
    assert len(report.models.fallbacks) == 3
    assert report.entities and all(e.source == "speaker_label" for e in report.entities)
    # Rule-based extraction keeps working without spaCy and embeddings.
    assert any(a.owner == "Ann" for a in report.action_items)
    assert any(d.status == "confirmed" for d in report.decisions)


class FakeSummarizer:
    """Stands in for the seq2seq model to check chunking without loading 1.2 GB."""

    def __init__(self):
        self.calls = []

    def count_tokens(self, text):
        return len(text.split())

    def summarize(self, texts, max_length=130, min_length=25):
        self.calls.append(len(texts))
        return [t.split(". ")[0][:200] + "." for t in texts]


def test_chunks_respect_token_limit():
    lines = [f"Speaker{i % 3}: " + "word " * 40 for i in range(100)]
    chunks = _chunks(lines, lambda s: len(s.split()), limit=300)
    assert len(chunks) > 10
    assert all(len(c.split()) <= 300 + 45 for c in chunks)


def _long_transcript(n_blocks: int = 50) -> str:
    topics = ["database migration", "marketing budget", "hiring plan", "security audit", "customer onboarding"]
    lines = []
    for i in range(n_blocks):
        topic = topics[(i * len(topics)) // n_blocks]
        lines += [
            f"Ann: Let's look at the {topic} status for week {i}. There are several open points on the {topic} we need to cover.",
            f"Ben: The {topic} work is progressing, but we found some issues with the {topic} timeline this week.",
            f"Cara: I'll write a short update on the {topic} for the steering group by Friday.",
            f"Ann: Thanks Cara. The {topic} numbers look reasonable compared with last month.",
        ]
    return "\n".join(lines)


def test_long_transcript_hierarchical_summary(registry):
    text = _long_transcript()
    assert len(text.split()) > 3000
    fake = FakeSummarizer()
    report = analyze(AnalyzeRequest(transcript=text, meeting_date=MEETING_DATE), registry=registry)
    assert report.stats.word_count > 3000
    assert 3 <= len(report.topics) <= 8
    # Run the abstractive path with the fake model to exercise map-reduce chunking.
    from app.nlp.common import Embedder
    from app.nlp.preprocessing import parse_transcript

    t = parse_transcript(text, registry.get("spacy"))
    builder = SummaryBuilder(t, Embedder(registry.get("embeddings")), fake)
    summary = builder.build(report.topics, report.decisions, report.action_items)
    assert summary.method == "abstractive"
    assert sum(fake.calls) > len(report.topics)  # more chunks than topics => chunked input
    assert summary.executive


def test_grounding_removes_unsupported_names(registry):
    from app.nlp.common import Embedder
    from app.nlp.preprocessing import parse_transcript

    t = parse_transcript(TEXT, registry.get("spacy"))
    builder = SummaryBuilder(t, Embedder(registry.get("embeddings")))
    kept = builder._ground(
        "Ann will send the budget spreadsheet to finance by Friday. Gregory approved a 40 percent raise for Zurich.", t.sentences
    )
    assert len(kept) == 1 and kept[0].text.startswith("Ann")
    assert builder.removed == 1


def test_grounding_flags_conflated_facts(registry, sample_text, sample_report):
    from app.nlp.common import Embedder
    from app.nlp.preprocessing import parse_transcript

    t = parse_transcript(sample_text, registry.get("spacy"))
    builder = SummaryBuilder(t, Embedder(registry.get("embeddings")))
    builder.actions = sample_report.action_items
    # "Android 9" and "March 17" come from different, non-adjacent sentences in the sample.
    conflated = builder._ground("The launch date of Android 9 has been moved to March 17.", t.sentences)
    faithful = builder._ground("Marcus Chen will fix the checkout crash by Thursday.", t.sentences)
    assert conflated[0].grounding == "weak"
    assert faithful[0].grounding == "supported"


def test_grounding_flags_commitments_without_matching_action(registry, run):
    from app.nlp.common import Embedder
    from app.nlp.preprocessing import parse_transcript

    text = (
        "Ann: Ben, can you renew the hosting contract by next Friday?\nBen: Sure, I'll take care of it.\n"
        "Ann: Who is going to write the launch announcement?\nCara: I'm not sure yet, I need to check with marketing."
    )
    report = run(text)
    t = parse_transcript(text, registry.get("spacy"))
    builder = SummaryBuilder(t, Embedder(registry.get("embeddings")))
    builder.actions = report.action_items
    kept = builder._ground("Ben will renew the hosting contract by next Friday. Cara is going to write the launch announcement.", t.sentences)
    assert [k.grounding for k in kept] == ["supported", "weak"]


@pytest.mark.slow
def test_real_abstractive_summarizer(sample_text):
    reg = ModelRegistry(dataclasses.replace(get_settings(), summary_mode="abstractive"))
    report = analyze(AnalyzeRequest(transcript=sample_text, meeting_date=MEETING_DATE), registry=reg)
    assert report.summary.method == "abstractive"
    assert 1 <= len(report.summary.executive) <= 10
    for s in report.summary.executive:
        assert s.evidence
