import io
import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(registry):
    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def report_json(client, sample_text):
    r = client.post("/api/analyze", json={"transcript": sample_text, "title": "Launch Sync", "meeting_date": "2026-03-04"})
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ health / validation
def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert {m["role"] for m in body["models"]} >= {"sentence embeddings", "abstractive summarization"}


@pytest.mark.parametrize(
    "payload,fragment",
    [
        ({"transcript": ""}, "empty"),
        ({"transcript": "   \n "}, "empty"),
        ({"transcript": "Ann: hi there."}, "too short"),
        ({}, "transcript"),
        ({"transcript": "Ann: " + "word " * 50, "meeting_date": "not-a-date"}, "meeting_date"),
        ({"transcript": "1234 5678 ---- ++++ //// " * 10}, "does not look like a transcript"),
    ],
)
def test_analyze_validation_errors(client, payload, fragment):
    r = client.post("/api/analyze", json=payload)
    assert r.status_code == 422
    assert fragment in r.json()["detail"]
    # The response must not echo the transcript back.
    assert "word word" not in r.text


def test_analyze_rejects_too_long(client, registry, monkeypatch):
    import dataclasses

    import app.api.routes as routes

    small = dataclasses.replace(registry.settings, max_transcript_chars=100)
    monkeypatch.setattr(routes, "get_settings", lambda: small)
    r = client.post("/api/analyze", json={"transcript": "Ann: " + "hello there " * 50})
    assert r.status_code == 422 and "too long" in r.json()["detail"]


def test_analyze_report_shape(report_json):
    for key in ["summary", "topics", "decisions", "action_items", "deadlines", "risks", "questions", "entities",
                "people", "keywords", "next_steps", "sentences", "utterances", "stats", "models"]:
        assert key in report_json
    assert report_json["meeting"]["date"] == "2026-03-04"
    assert report_json["stats"]["speaker_count"] == 4


def test_stream_emits_real_stages_then_result(client, sample_text):
    with client.stream("POST", "/api/analyze/stream", json={"transcript": sample_text, "meeting_date": "2026-03-04"}) as r:
        assert r.status_code == 200
        events = [json.loads(line) for line in r.iter_lines() if line]
    assert events[0]["type"] == "accepted"
    assert events[-1]["type"] == "result"
    completed = [e["stage"] for e in events if e.get("type") == "stage" and e["status"] == "completed"]
    expected = [s["key"] for s in events[0]["stages"]]
    assert completed == expected
    starts = [e for e in events if e.get("status") == "started"]
    assert len(starts) == len(expected)
    assert all("elapsed_ms" in e for e in events if e.get("status") == "completed")


def test_stream_validation_error_is_http_422(client):
    r = client.post("/api/analyze/stream", json={"transcript": "too short"})
    assert r.status_code == 422


# ------------------------------------------------------------------ file uploads
def _docx_bytes(lines):
    import docx

    d = docx.Document()
    for line in lines:
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _pdf_bytes(lines=None):
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for line in lines or []:
        c.drawString(50, y, line)
        y -= 20
    if not lines:
        c.rect(50, 50, 200, 200, fill=1)  # an "image-only" page with no text
    c.showPage()
    c.save()
    return buf.getvalue()


LINES = ["Ann: I'll send the budget by Friday.", "Ben: Thanks Ann, I will review it on Monday morning."]


@pytest.mark.parametrize(
    "name,data,ftype",
    [
        ("notes.txt", "\n".join(LINES).encode("utf-8"), "text"),
        ("notes_utf16.txt", "\n".join(LINES).encode("utf-16"), "text"),
        ("notes.docx", _docx_bytes(LINES), "docx"),
        ("notes.pdf", _pdf_bytes(LINES), "pdf"),
    ],
    ids=["txt", "txt-utf16", "docx", "pdf"],
)
def test_extract_supported_files(client, name, data, ftype):
    r = client.post("/api/extract", files={"file": (name, data)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["file_type"] == ftype
    assert "Ann" in body["text"] and "budget" in body["text"]
    assert body["word_count"] > 5


@pytest.mark.parametrize(
    "name,data,status,fragment",
    [
        ("notes.exe", b"MZ\x90\x00", 415, "Unsupported"),
        ("notes.doc", b"\xd0\xcf\x11\xe0", 415, ".docx"),
        ("empty.txt", b"", 400, "empty"),
        ("fake.pdf", b"hello this is not a pdf", 415, "valid PDF"),
        ("fake.docx", b"not a zip", 415, "valid .docx"),
        ("scan.pdf", _pdf_bytes(), 422, "scanned"),
        ("binary.txt", b"\x00\x01\x02\x03" * 100, 415, "binary"),
    ],
)
def test_extract_rejects_bad_files(client, name, data, status, fragment):
    r = client.post("/api/extract", files={"file": (name, data)})
    assert r.status_code == status
    assert fragment in r.json()["detail"]


def test_extract_rejects_oversized_file(client, registry, monkeypatch):
    import dataclasses

    import app.api.routes as routes

    small = dataclasses.replace(registry.settings, max_upload_mb=1)
    monkeypatch.setattr(routes, "get_settings", lambda: small)
    r = client.post("/api/extract", files={"file": ("big.txt", b"a " * 700_000)})
    assert r.status_code == 413


def test_temporary_upload_files_are_removed(client):
    before = {p for p in os.listdir(tempfile.gettempdir()) if p.startswith("meetingmind_")}
    client.post("/api/extract", files={"file": ("notes.docx", _docx_bytes(LINES))})
    client.post("/api/extract", files={"file": ("bad.pdf", b"%PDF-1.4 broken")})
    after = {p for p in os.listdir(tempfile.gettempdir()) if p.startswith("meetingmind_")}
    assert after <= before


# ------------------------------------------------------------------ exports
@pytest.mark.parametrize("fmt,ctype", [("json", "application/json"), ("csv", "text/csv"), ("markdown", "text/markdown"), ("pdf", "application/pdf")])
def test_exports(client, report_json, fmt, ctype):
    r = client.post(f"/api/export/{fmt}", json=report_json)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(ctype)
    assert "attachment" in r.headers["content-disposition"]
    assert len(r.content) > 500


def test_user_edits_are_reflected_in_every_export(client, report_json):
    edited = json.loads(json.dumps(report_json))
    item = edited["action_items"][0]
    item.update(description="Renegotiate the PayFlow contract", owner="Zoë Müller", owner_source="user",
                status="done", edited=True, needs_review=False)
    item["deadline"] = {"text": "2026-04-30", "normalized_date": "2026-04-30", "date_type": "user"}
    edited["action_items"].append({"id": "A99", "description": "Manually added follow-up", "owner": "Sam",
                                   "owner_source": "user", "status": "in_progress", "edited": True})

    js = client.post("/api/export/json", json=edited).json()
    assert js["action_items"][0]["owner"] == "Zoë Müller" and js["edited_at"]

    csv_text = client.post("/api/export/csv", json=edited).content.decode("utf-8-sig")
    assert "Renegotiate the PayFlow contract" in csv_text and "Zoë Müller" in csv_text
    assert "2026-04-30" in csv_text and "Done" in csv_text and "Manually added follow-up" in csv_text

    md = client.post("/api/export/markdown", json=edited).text
    assert "Renegotiate the PayFlow contract" in md and "In progress" in md and "last edited" in md

    from pypdf import PdfReader

    pdf = client.post("/api/export/pdf", json=edited).content
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
    assert "Renegotiate the PayFlow" in text and "Manually added follow-up" in text


def test_csv_neutralises_formula_injection(client, report_json):
    edited = json.loads(json.dumps(report_json))
    edited["action_items"][0]["description"] = "=HYPERLINK(\"http://evil\")"
    csv_text = client.post("/api/export/csv", json=edited).content.decode("utf-8-sig")
    assert "'=HYPERLINK" in csv_text


def test_export_rejects_invalid_report(client):
    assert client.post("/api/export/csv", json={"foo": "bar"}).status_code == 422
    assert client.post("/api/export/docx", json={}).status_code == 422
