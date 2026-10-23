import pytest

from app.nlp.preprocessing import is_plausible_speaker, parse_transcript


@pytest.fixture(scope="module")
def nlp(registry):
    return registry.get("spacy")


def test_basic_speaker_labels_and_sentences(nlp):
    t = parse_transcript("Alice: Hello team. Let's begin.\nBob: Thanks Alice.\nAlice: Great.", nlp)
    assert t.speakers == ["Alice", "Bob"]
    assert [u.speaker for u in t.utterances] == ["Alice", "Bob", "Alice"]
    assert len(t.utterances[0].sentence_ids) == 2
    assert t.has_speaker_labels


@pytest.mark.parametrize(
    "line,speaker,ts",
    [
        ("[00:01:23] Priya Sharma: We should ship.", "Priya Sharma", "00:01:23"),
        ("Priya (12:05): We should ship.", "Priya", "12:05"),
        ("00:12 - Priya: We should ship.", "Priya", "00:12"),
        ("**Priya:** We should ship.", "Priya", None),
        ("Speaker 1: We should ship.", "Speaker 1", None),
    ],
)
def test_speaker_formats(nlp, line, speaker, ts):
    t = parse_transcript(line + "\nBob: ok sounds fine to me.", nlp)
    assert t.utterances[0].speaker == speaker
    assert t.utterances[0].timestamp == ts


def test_metadata_lines_are_not_speakers(nlp):
    text = "Meeting: Weekly sync\nDate: March 4, 2026\nAttendees: Ann Lee, Raj Patel\nAnn Lee: Hi all.\nRaj Patel: Hello."
    t = parse_transcript(text, nlp)
    assert t.speakers == ["Ann Lee", "Raj Patel"]
    assert t.header_date_text == "March 4, 2026"
    assert t.attendees == ["Ann Lee", "Raj Patel"]
    assert all("Weekly sync" not in s.text for s in t.sentences)


def test_otter_style_headers(nlp):
    text = "Dana Smith  0:03\nWe need the report.\nIt is late.\n\nLee Wong  0:15\nI will send it today."
    t = parse_transcript(text, nlp)
    assert [u.speaker for u in t.utterances] == ["Dana Smith", "Lee Wong"]
    assert "It is late" in t.utterances[0].text


def test_webvtt_voice_tags(nlp):
    text = "WEBVTT\n\n00:00:01.000 --> 00:00:04.000\n<v Maria>I'll draft the agenda.</v>\n\n00:00:05.000 --> 00:00:07.000\n<v Tom>Thanks Maria.</v>"
    t = parse_transcript(text, nlp)
    assert [u.speaker for u in t.utterances] == ["Maria", "Tom"]
    assert t.utterances[0].timestamp == "00:00:01"


def test_srt_numbers_are_skipped(nlp):
    text = "1\n00:00:01,000 --> 00:00:03,000\nAnna: Let's start.\n\n2\n00:00:04,000 --> 00:00:06,000\nBen: Sure thing."
    t = parse_transcript(text, nlp)
    assert [u.speaker for u in t.utterances] == ["Anna", "Ben"]
    assert all(not s.text.isdigit() for s in t.sentences)


def test_plain_text_without_speakers_warns(nlp):
    t = parse_transcript("We talked about the budget. The team will review the numbers next week.", nlp)
    assert t.speakers == []
    assert not t.has_speaker_labels
    assert any("speaker labels" in w for w in t.warnings)


def test_continuation_lines_merge_into_previous_turn(nlp):
    t = parse_transcript("Alice: First line\nsecond line of the same turn\nBob: Reply.", nlp)
    assert len(t.utterances) == 2
    assert "second line" in t.utterances[0].text


@pytest.mark.parametrize("label,ok", [("Priya", True), ("Dr. Smith", True), ("Note", False), ("So the plan is", False), ("Action items", False)])
def test_speaker_plausibility(label, ok):
    assert is_plausible_speaker(label) is ok
