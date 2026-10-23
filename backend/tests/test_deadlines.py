from datetime import date

import pytest

from app.nlp.deadlines import best_deadline, find_deadlines

WED = date(2026, 3, 4)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("send it by Friday", date(2026, 3, 6)),
        ("finish it tomorrow", date(2026, 3, 5)),
        ("by end of day", WED),
        ("by EOD", WED),
        ("by end of week", date(2026, 3, 6)),
        ("in two weeks", date(2026, 3, 18)),
        ("within 3 days", date(2026, 3, 7)),
        ("by March 10", date(2026, 3, 10)),
        ("by the 15th", date(2026, 3, 15)),
        ("due 2026-04-01", date(2026, 4, 1)),
        ("by the end of the month", date(2026, 3, 31)),
        ("by the end of Q2", date(2026, 6, 30)),
        ("Friday next week", date(2026, 3, 13)),
        ("on 12/25", date(2026, 12, 25)),
    ],
)
def test_resolves_explicit_and_relative_dates(text, expected):
    d = best_deadline(text, WED)
    assert d is not None and d.normalized_date == expected


def test_month_without_year_rolls_into_next_year():
    d = best_deadline("by January 15", date(2026, 11, 20))
    assert d.normalized_date == date(2027, 1, 15)


@pytest.mark.parametrize("text", ["by next Friday", "next Wednesday", "due 3/4", "next week", "mid-April", "next month"])
def test_ambiguous_dates_are_flagged(text):
    d = best_deadline(text, WED)
    assert d is not None and d.is_ambiguous and d.note


def test_bare_weekday_equal_to_meeting_day_is_ambiguous():
    d = best_deadline("send it Wednesday", WED)
    assert d.is_ambiguous and d.normalized_date == date(2026, 3, 11)


@pytest.mark.parametrize("text", ["ASAP", "as soon as possible", "by end of sprint", "before the launch"])
def test_vague_timing_is_never_converted_to_a_date(text):
    d = best_deadline(text, WED)
    assert d is not None and d.normalized_date is None and d.date_type == "vague"


def test_relative_dates_not_resolved_without_meeting_date():
    d = best_deadline("by Friday", None)
    assert d.normalized_date is None and d.is_ambiguous
    assert "Meeting date not provided" in d.note


def test_explicit_year_resolves_without_meeting_date():
    d = best_deadline("by March 10, 2027", None)
    assert d.normalized_date == date(2027, 3, 10)


@pytest.mark.parametrize("text", ["I may be late", "we met last Tuesday", "it happened yesterday", "the meeting was great"])
def test_no_deadline_invented(text):
    assert find_deadlines(text, WED) == []


def test_prefers_phrase_with_preposition():
    d = best_deadline("On Monday we reviewed it and I'll send the fix by Thursday", WED)
    assert d.text.lower() == "by thursday"
