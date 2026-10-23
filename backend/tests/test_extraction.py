"""Action items, decisions, risks, questions, entities and keywords on small focused transcripts."""
from datetime import date

from conftest import find


# ------------------------------------------------------------------ action items
def test_self_commitment_owner_is_speaker(run):
    r = run("Ann: I'll send the budget spreadsheet to finance by Friday.\nBen: Thanks Ann, that helps a lot.")
    a = find(r.action_items, "budget spreadsheet")[0]
    assert a.owner == "Ann" and a.owner_source == "self_commitment"
    assert a.deadline.normalized_date == date(2026, 3, 6)
    assert a.evidence and a.evidence[0].speaker == "Ann"


def test_named_owner_in_third_person(run):
    r = run("Ann: Ben will update the onboarding docs before the release.\nBen: Yes, that's fine with me.")
    a = find(r.action_items, "onboarding docs")[0]
    assert a.owner == "Ben" and a.owner_source == "explicit_name"


def test_minutes_style_name_to_verb(run):
    r = run("Ann: Action item: Ben to book the venue for the team offsite in May.\nBen: Noted, thanks, I have a list of options.")
    a = find(r.action_items, "book the venue")[0]
    assert a.owner == "Ben"


def test_request_with_vocative(run):
    r = run("Ann: Ben, can you review the pull request today?\nCara: I can help if needed.\nBen: Will do.")
    a = find(r.action_items, "review the pull request")[0]
    assert a.owner == "Ben" and a.owner_source == "addressed_request"


def test_owner_inferred_from_reply(run):
    r = run("Ann: Can someone follow up with the vendor about pricing?\nCara: Sure, I'll take that.\nBen: Great.")
    a = find(r.action_items, "follow up with the vendor")[0]
    assert a.owner == "Cara" and a.owner_source == "inferred_from_reply" and a.is_inferred
    assert a.needs_review


def test_unassigned_when_nobody_volunteers(run):
    r = run("Ann: Someone needs to update the app store screenshots.\nBen: The designers would know which ones changed.")
    a = find(r.action_items, "screenshots")[0]
    assert a.owner == "Unassigned" and a.needs_review
    assert any("volunteer" in x for x in a.review_reasons)


def test_multiple_speakers_each_get_their_items(run):
    text = (
        "Ann: I'll prepare the slides for Monday.\n"
        "Ben: I'm going to fix the login bug by tomorrow.\n"
        "Cara: Let me check with legal about the contract.\n"
    )
    r = run(text)
    owners = {a.owner for a in r.action_items}
    assert {"Ann", "Ben", "Cara"} <= owners


def test_past_tense_and_hypotheticals_are_not_actions(run):
    text = (
        "Ann: I already sent the report yesterday.\n"
        "Ben: If we were to rewrite the app, it would take months.\n"
        "Cara: I think the design looks really good overall.\n"
        "Ann: I'll be honest, I did not expect that result.\n"
    )
    assert run(text).action_items == []


def test_clause_level_commitment_with_antecedent(run):
    r = run("Marcus: The checkout crash is on our side, and I'll fix it by Thursday.\nPriya: Thank you Marcus, great.")
    a = r.action_items[0]
    assert a.owner == "Marcus" and "checkout crash" in a.description.lower()


def test_vague_reply_is_merged_into_request(run):
    text = "Priya: Marcus, can you write up the bug details for the vendor?\nMarcus: Sure, I'll have that to you this afternoon.\nPriya: Thanks."
    r = run(text)
    assert len(r.action_items) == 1
    a = r.action_items[0]
    assert a.owner == "Marcus" and a.deadline and a.deadline.normalized_date == date(2026, 3, 4)
    assert len(a.evidence) == 2


def test_unlabelled_transcript_still_finds_named_owner(run):
    r = run("We met to plan the launch. Sarah will prepare the press release by Friday. The rest is on track.")
    a = find(r.action_items, "press release")[0]
    assert a.owner == "Sarah"


# ------------------------------------------------------------------ decisions
def test_decision_statuses(run):
    text = (
        "Ann: We decided to go with Postgres for the analytics store.\n"
        "Ben: We decided not to support Internet Explorer anymore.\n"
        "Cara: For now, we'll tentatively keep the weekly release cadence.\n"
    )
    r = run(text)
    status = {d.status for d in r.decisions}
    assert status == {"confirmed", "rejected", "tentative"}


def test_suggestions_questions_and_hypotheticals_are_not_decisions(run):
    text = (
        "Ann: Maybe we should consider switching vendors next year.\n"
        "Ben: What if we launched in April instead of March?\n"
        "Cara: Hypothetically, if we moved to Azure, costs would drop.\n"
        "Ann: Have we decided on the pricing model yet?\n"
        "Ben: We haven't decided on the pricing model.\n"
    )
    assert run(text).decisions == []


def test_agreement_on_proposal_becomes_inferred_decision(run):
    text = "Ann: How about we move the standup to 10am every day?\nBen: Agreed, that works for everyone on my team.\nCara: Fine."
    r = run(text)
    assert len(r.decisions) == 1
    d = r.decisions[0]
    assert d.kind == "agreement" and d.is_inferred and d.status == "confirmed"
    assert len(d.evidence) == 2


def test_conditional_decision_is_tentative(run):
    r = run("Ann: We decided to delay the launch if the audit is not finished by Friday.\nBen: Understood, makes sense.")
    assert r.decisions[0].status == "tentative" and r.decisions[0].needs_review


# ------------------------------------------------------------------ risks and blockers
def test_risks_and_blockers(run):
    text = (
        "Ann: We're blocked until the security team approves the firewall change.\n"
        "Ben: I'm worried the vendor will deliver the hardware late, which puts the launch at risk.\n"
        "Cara: The demo went really well, everyone loved it.\n"
        "Ann: No blockers from my side this week.\n"
    )
    r = run(text)
    kinds = sorted(x.kind for x in r.risks)
    assert kinds == ["blocker", "risk"]
    assert all(x.evidence for x in r.risks)
    assert any(x.severity == "high" for x in r.risks)


# ------------------------------------------------------------------ questions
def test_unanswered_and_deferred_questions(run):
    text = (
        "Ann: Who owns the customer migration plan going forward?\n"
        "Ben: Not sure yet, I need to check with the director.\n"
        "Cara: What time is the client call on Thursday?\n"
        "Ann: It's at 3pm, I'll forward the invite to everyone.\n"
        "Ben: Should we offer a discount to the early adopters?\n"
        "Cara: Let's move on to the hiring plan now.\n"
    )
    r = run(text)
    statuses = {q.text.split()[0]: q.status for q in r.questions}
    assert statuses.get("Who") == "deferred"
    assert "What" not in statuses  # answered
    assert statuses.get("Should") == "unanswered"


def test_filler_questions_ignored(run):
    r = run("Ann: Can everyone hear me okay?\nBen: Yes, loud and clear here.\nAnn: Okay, makes sense?\nBen: Sure, all good.")
    assert r.questions == []


# ------------------------------------------------------------------ entities, keywords, people, evidence
def test_entities_people_and_keywords(sample_report):
    labels = {e.label for e in sample_report.entities}
    assert {"PERSON", "ORG", "DATE"} <= labels
    assert any(e.text == "PayFlow" for e in sample_report.entities)
    speakers = [p for p in sample_report.people if p.is_speaker]
    assert len(speakers) == 4
    assert abs(sum(p.talk_share for p in speakers) - 100) < 1
    assert len(sample_report.keywords) >= 5
    assert not any(k.phrase.lower() in {"chen", "okay", "thanks"} for k in sample_report.keywords)


def test_every_item_has_evidence_that_exists_in_transcript(sample_report):
    ids = {s.id for s in sample_report.sentences}
    groups = [sample_report.action_items, sample_report.decisions, sample_report.risks, sample_report.questions]
    for group in groups:
        for item in group:
            assert item.evidence, item
            assert all(e.sentence_id in ids for e in item.evidence)
    for s in sample_report.summary.executive:
        assert s.evidence and all(e.sentence_id in ids for e in s.evidence)


def test_sample_report_core_items(sample_report):
    r = sample_report
    assert find(r.action_items, "checkout crash")[0].owner == "Marcus Chen"
    assert find(r.action_items, "press release")[0].deadline.is_ambiguous  # "next Wednesday"
    assert find(r.action_items, "FAQ")[0].owner == "Unassigned"
    assert find(r.decisions, "March 17", "text")[0].status == "confirmed"
    assert find(r.decisions, "chatbot", "text")[0].status == "rejected"
    assert any(x.kind == "blocker" and "PayFlow" in x.text for x in r.risks)
    assert 2 <= len(r.topics) <= 6
    assert r.next_steps and all(n.rationale for n in r.next_steps)
    assert r.stats.duration is not None


def test_no_meeting_date_uses_header_or_warns(run, sample_text):
    r = run(sample_text, meeting_date=None)
    assert r.meeting.date == date(2026, 3, 4)  # from "Date: March 4, 2026" header
    r2 = run("Ann: I'll send the quarterly report by Friday please.\nBen: Thanks Ann, that sounds good to me.", meeting_date=None)
    assert r2.action_items[0].deadline.normalized_date is None
    assert any("No meeting date" in w for w in r2.warnings)
