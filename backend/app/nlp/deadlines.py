"""Deadline detection and normalisation.

Relative expressions ("next Friday", "end of month", "in two weeks") are resolved against the
meeting date with explicit, documented rules. Explicit dates ("March 3", "2026-03-15", "3/4")
are parsed with `dateparser`. Anything vague ("ASAP", "soon", "end of sprint") is recorded
but never converted into an invented calendar date.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
WD = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9,
    "sep": 9, "sept": 9, "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
MON = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)"
NUM_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "a couple of": 2, "couple of": 2,
}
NUM = r"(?:\d{1,3}|a couple of|couple of|an|a|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
PREP = r"(?:(?:by|before|until|till|no later than|due|due on|due by|on|for|ahead of|as of|starting|from)\s+(?:the\s+)?)?"
ORD = r"(?:st|nd|rd|th)?"
DAYPART = r"(?:\s+(?:morning|afternoon|evening|night|eod|end of day))?"


@dataclass
class DeadlineMatch:
    text: str
    start: int
    end: int
    normalized_date: Optional[date]
    date_type: str  # explicit | relative | vague (| past, filtered out)
    granularity: str  # day | week | month | quarter | unknown
    is_ambiguous: bool
    note: Optional[str]
    has_preposition: bool


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _end_of_month(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def _add_months(d: date, n: int) -> tuple[int, int]:
    m = d.month - 1 + n
    return d.year + m // 12, m % 12 + 1


def _quarter_end(y: int, q: int) -> date:
    return _end_of_month(y, q * 3)


def _parse_num(token: str) -> int:
    token = token.lower().strip()
    return int(token) if token.isdigit() else NUM_WORDS.get(token, 1)


class _Rules:
    """Each rule returns (normalized_date, date_type, granularity, ambiguous, note)."""

    def __init__(self, base: Optional[date]):
        self.base = base

    def needs_base(self):
        return (None, "relative", "unknown", True, "Meeting date not provided, so this relative date was not resolved.")

    # --- day-level relative expressions ---------------------------------------------
    def today(self, m):
        if not self.base:
            return self.needs_base()
        return (self.base, "relative", "day", False, None)

    def tomorrow(self, m):
        if not self.base:
            return self.needs_base()
        offset = 2 if "after" in m.group(0).lower() else 1
        return (self.base + timedelta(days=offset), "relative", "day", False, None)

    def weekday(self, m):
        if not self.base:
            return self.needs_base()
        phrase = m.group(0).lower()
        target = WEEKDAYS.index(m.group("wd").lower())
        this_week = _week_start(self.base) + timedelta(days=target)
        nearest = self.base + timedelta(days=(target - self.base.weekday()) % 7)
        next_week = this_week + timedelta(days=7)
        if re.search(r"\b(next week|of next week)\b", phrase) or re.search(r"\bweek after\b", phrase):
            return (next_week, "relative", "day", False, None)
        if re.search(r"\bnext\b", phrase):
            if nearest == next_week:
                return (next_week, "relative", "day", False, None)
            return (
                next_week,
                "relative",
                "day",
                True,
                f"'next {m.group('wd').title()}' could mean {nearest.isoformat()} or {next_week.isoformat()}; "
                f"interpreted as the {m.group('wd').title()} of next week.",
            )
        if re.search(r"\blast\b", phrase):
            return (None, "past", "day", True, "Refers to a past day; not treated as a deadline.")
        if re.search(r"\bthis\b", phrase):
            if this_week >= self.base:
                return (this_week, "relative", "day", False, None)
            return (nearest, "relative", "day", True, "This weekday has already passed this week; the next one was used.")
        # bare weekday
        if nearest == self.base:
            return (
                self.base + timedelta(days=7),
                "relative",
                "day",
                True,
                "The meeting is on this weekday, so this could mean today or a week from today; a week from today was used.",
            )
        return (nearest, "relative", "day", False, None)

    def end_of_week(self, m):
        if not self.base:
            return self.needs_base()
        phrase = m.group(0).lower()
        friday = _week_start(self.base) + timedelta(days=4)
        if "next" in phrase:
            return (friday + timedelta(days=7), "relative", "day", False, "End of week interpreted as Friday.")
        if friday < self.base:  # meeting held on a weekend
            friday += timedelta(days=7)
        return (friday, "relative", "day", False, "End of week interpreted as Friday.")

    def week(self, m):
        if not self.base:
            return self.needs_base()
        phrase = m.group(0).lower()
        friday = _week_start(self.base) + timedelta(days=4)
        if "next" in phrase or "following" in phrase:
            friday += timedelta(days=7)
        elif friday < self.base:
            friday += timedelta(days=7)
        return (friday, "relative", "week", True, "Week-level deadline with no specific day; the Friday of that week was used for sorting.")

    def end_of_month(self, m):
        if not self.base:
            return self.needs_base()
        phrase = m.group(0).lower()
        y, mo = _add_months(self.base, 1 if "next" in phrase else 0)
        return (_end_of_month(y, mo), "relative", "day", False, "Interpreted as the last day of the month.")

    def month(self, m):
        if not self.base:
            return self.needs_base()
        phrase = m.group(0).lower()
        y, mo = _add_months(self.base, 1 if "next" in phrase else 0)
        return (_end_of_month(y, mo), "relative", "month", True, "Month-level deadline with no specific day; the last day of the month was used for sorting.")

    def quarter(self, m):
        if not self.base:
            return self.needs_base()
        phrase = m.group(0).lower()
        q = (self.base.month - 1) // 3 + 1
        y = self.base.year
        if "next" in phrase:
            q += 1
            if q == 5:
                q, y = 1, y + 1
        exact = "end of" in phrase
        return (
            _quarter_end(y, q),
            "relative",
            "day" if exact else "quarter",
            not exact,
            f"Interpreted as the end of Q{q} {y}." if exact else f"Quarter-level deadline (Q{q} {y}); quarter end used for sorting.",
        )

    def named_quarter(self, m):
        q = int(m.group("q"))
        if m.group("year"):
            y = int(m.group("year"))
            if y < 100:
                y += 2000
        elif self.base:
            y = self.base.year if _quarter_end(self.base.year, q) >= self.base else self.base.year + 1
        else:
            return (None, "explicit", "quarter", True, "Year not stated and meeting date unknown.")
        if "end of" in m.group(0).lower():
            return (_quarter_end(y, q), "explicit", "day", False, f"Interpreted as the last day of Q{q} {y}.")
        return (_quarter_end(y, q), "explicit", "quarter", True, f"Quarter-level deadline (Q{q} {y}); quarter end used for sorting.")

    def in_n(self, m):
        if not self.base:
            return self.needs_base()
        n = _parse_num(m.group("n"))
        unit = m.group("unit").lower()
        if unit.startswith("day"):
            return (self.base + timedelta(days=n), "relative", "day", False, None)
        if unit.startswith("week"):
            return (self.base + timedelta(weeks=n), "relative", "day" if n <= 1 else "week", n > 1, None if n <= 1 else "Approximate: counted from the meeting date.")
        y, mo = _add_months(self.base, n)
        day = min(self.base.day, calendar.monthrange(y, mo)[1])
        return (date(y, mo, day), "relative", "month", True, "Approximate: counted from the meeting date.")

    def nth_of_month(self, m):
        day = int(m.group("day"))
        if not self.base:
            return self.needs_base()
        y, mo = self.base.year, self.base.month
        if day < self.base.day:
            y, mo = _add_months(self.base, 1)
        try:
            return (date(y, mo, day), "relative", "day", False, "Month inferred from the meeting date.")
        except ValueError:
            return (None, "relative", "day", True, "Day does not exist in the inferred month.")

    def part_of_month(self, m):
        mo = MONTHS[m.group("mon").lower()]
        part = m.group("part").lower()
        y = self._infer_year(mo, 28 if part != "early" else 1)
        if y is None:
            return (None, "explicit", "month", True, "Year unknown (no meeting date).")
        if part in {"end", "the end"}:
            return (_end_of_month(y, mo), "explicit", "day", False, "Interpreted as the last day of the month.")
        day = {"early": 7, "mid": 15, "middle": 15, "late": 25}.get(part, 15)
        return (date(y, mo, day), "explicit", "month", True, f"Approximate ('{part} {m.group('mon')}'); day {day} used for sorting.")

    def _infer_year(self, month: int, day: int) -> Optional[int]:
        if not self.base:
            return None
        try:
            candidate = date(self.base.year, month, min(day, calendar.monthrange(self.base.year, month)[1]))
        except ValueError:
            return None
        return self.base.year if candidate >= self.base - timedelta(days=30) else self.base.year + 1

    # --- explicit dates via dateparser ----------------------------------------------
    def explicit(self, m):
        import dateparser

        phrase = m.group("date")
        has_year = bool(re.search(r"\b\d{4}\b", phrase)) or bool(re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", phrase))
        numeric = re.fullmatch(r"\s*(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?\s*", phrase)
        if not has_year and not self.base:
            return (None, "explicit", "day", True, "Year not stated and meeting date unknown, so the date was not resolved.")
        settings = {"PREFER_DATES_FROM": "future", "DATE_ORDER": "MDY", "REQUIRE_PARTS": ["day", "month"]}
        if self.base:
            settings["RELATIVE_BASE"] = datetime.combine(self.base - timedelta(days=30), datetime.min.time())
        cleaned = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", phrase, flags=re.I)
        parsed = dateparser.parse(cleaned, languages=["en"], settings=settings)
        if not parsed:
            return (None, "explicit", "day", True, "Could not parse this date.")
        resolved = parsed.date()
        ambiguous, note = False, None
        if numeric:
            a, b = int(numeric.group(1)), int(numeric.group(2))
            if a <= 12 and b <= 12 and a != b:
                ambiguous = True
                note = f"Numeric date '{phrase.strip()}' is ambiguous (month/day vs day/month); interpreted as month/day."
        if not has_year and not note:
            note = "Year inferred from the meeting date."
        return (resolved, "explicit", "day", ambiguous, note)

    def vague(self, m):
        return (None, "vague", "unknown", True, "No specific date was given.")

    def sprint(self, m):
        return (None, "vague", "unknown", True, "Sprint dates are not known from the transcript.")

    def past_ref(self, m):
        return (None, "past", "day", True, "Refers to the past; not treated as a deadline.")


_RULES: list[tuple[str, str]] = [
    (rf"{PREP}(?P<date>\d{{4}}-\d{{2}}-\d{{2}})", "explicit"),
    (rf"{PREP}(?P<date>{MON}\.?\s+\d{{1,2}}{ORD}(?:,?\s+\d{{4}})?)", "explicit"),
    (rf"{PREP}(?P<date>\d{{1,2}}{ORD}\s+(?:of\s+)?{MON}(?:,?\s+\d{{4}})?)", "explicit"),
    (rf"{PREP}(?P<date>\d{{1,2}}[/.]\d{{1,2}}(?:[/.]\d{{2,4}})?)(?![\d/.])", "explicit"),
    (rf"{PREP}(?P<part>early|mid|middle|late|end|the end)[\s-]+(?:of\s+)?(?P<mon>{MON})\b", "part_of_month"),
    (rf"{PREP}(?:end of (?:the )?day|eod|cob|close of business|end of play|tonight|today|this (?:morning|afternoon|evening))\b", "today"),
    (rf"{PREP}(?:the )?(?:day after )?tomorrow(?:\s+(?:morning|afternoon|evening|night))?\b", "tomorrow"),
    (rf"{PREP}(?:end of (?:the )?(?:this |next )?(?:work\s?)?week|eow|end of next week)\b", "end_of_week"),
    (rf"{PREP}(?:(?:this|next|coming|the coming|the following)\s+)?(?P<wd>{WD})(?:\s+of)?\s+next week{DAYPART}\b", "weekday"),
    (rf"{PREP}(?:(?:this|next|coming|the coming|last)\s+)?(?P<wd>{WD}){DAYPART}\b", "weekday"),
    (rf"{PREP}(?:(?:the\s+)?end of (?:the |this )?month|eom|end of next month)\b", "end_of_month"),
    (rf"{PREP}(?:(?:the\s+)?end of (?:the |this |next )?quarter|eoq)\b", "quarter"),
    (rf"{PREP}(?:this|next) quarter\b", "quarter"),
    (rf"{PREP}(?:the )?(?:end of )?q(?P<q>[1-4])(?:\s+(?P<year>\d{{4}}|'?\d{{2}}))?\b", "named_quarter"),
    (rf"{PREP}(?:(?:this|next|the following)\s+week|the week after)\b", "week"),
    (rf"{PREP}(?:this|next) month\b", "month"),
    (rf"(?:in|within)\s+(?:the next\s+)?(?P<n>{NUM})\s+(?P<unit>days?|weeks?|months?)\b", "in_n"),
    (rf"(?:by|before|on|until)\s+the\s+(?P<day>\d{{1,2}}){ORD}\b(?!\s+(?:of\s+)?{MON})", "nth_of_month"),
    (rf"{PREP}(?:the )?(?:end of (?:the |this )?sprint|next sprint|this sprint)\b", "sprint"),
    (rf"(?:asap|as soon as possible|at some point|eventually|when(?:ever)? possible|in the near future|"
     rf"before the next meeting|by the next meeting|before (?:the )?(?:launch|release|demo|deadline)|"
     rf"later this (?:week|month)|sometime (?:soon|next week))\b", "vague"),
    (rf"\b(?:yesterday|last week|last month)\b", "past_ref"),
]
_COMPILED = [(re.compile(r"\b" + pat, re.IGNORECASE), handler) for pat, handler in _RULES]
_PREP_RE = re.compile(r"^(?:by|before|until|till|no later than|due|ahead of)\b", re.IGNORECASE)


def find_deadlines(text: str, meeting_date: Optional[date]) -> list[DeadlineMatch]:
    rules = _Rules(meeting_date)
    found: list[DeadlineMatch] = []
    for regex, handler in _COMPILED:
        for m in regex.finditer(text):
            if any(not (m.end() <= f.start or m.start() >= f.end) for f in found):
                continue  # earlier (more specific) rules win on overlap
            # "may" is a modal verb unless followed by a day number, which the regex already requires.
            normalized, dtype, gran, amb, note = getattr(rules, handler)(m)
            phrase = m.group(0).strip()
            found.append(
                DeadlineMatch(
                    text=phrase,
                    start=m.start(),
                    end=m.end(),
                    normalized_date=normalized,
                    date_type=dtype,
                    granularity=gran,
                    is_ambiguous=amb or gran != "day",
                    note=note,
                    has_preposition=bool(_PREP_RE.match(phrase)),
                )
            )
    found.sort(key=lambda d: d.start)
    return [f for f in found if f.date_type != "past"]


def best_deadline(text: str, meeting_date: Optional[date]) -> Optional[DeadlineMatch]:
    """Pick the deadline most likely to be the due date of a task in this sentence."""
    matches = find_deadlines(text, meeting_date)
    if not matches:
        return None
    with_prep = [m for m in matches if m.has_preposition]
    return (with_prep or matches)[-1]


DEADLINE_CONTEXT = re.compile(
    r"\b(by|before|until|due|deadline|no later than|target|scheduled|launch|release|ship|go[- ]live|"
    r"deliver|submit|ready|finish|complete|wrap up|demo|present|freeze|cutoff|cut-off)\b",
    re.IGNORECASE,
)


def parse_header_date(text: Optional[str]) -> Optional[date]:
    if not text:
        return None
    import dateparser

    parsed = dateparser.parse(text, languages=["en"], settings={"REQUIRE_PARTS": ["day", "month", "year"]})
    return parsed.date() if parsed else None
