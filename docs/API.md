# API reference

Base URL: `http://127.0.0.1:8000`. Interactive OpenAPI documentation is at `/docs`, and the schema at `/openapi.json`. All endpoints are stateless, and errors use the shape `{"detail": "human-readable message"}`.

## GET /api/health

```json
{
  "status": "ok",
  "version": "1.0.0",
  "summary_mode": "abstractive",
  "models": [
    {"name": "en_core_web_sm", "role": "linguistic analysis & NER", "state": "ready", "error": null, "load_seconds": 0.35},
    {"name": "sentence-transformers/all-MiniLM-L6-v2", "role": "sentence embeddings", "state": "ready", "error": null, "load_seconds": 7.2},
    {"name": "philschmid/distilbart-cnn-12-6-samsum", "role": "abstractive summarization", "state": "not_loaded", "error": null, "load_seconds": null}
  ]
}
```

`state` is one of `not_loaded`, `loading`, `ready`, `failed` or `disabled`.

## POST /api/models/warmup

Loads every enabled model now and returns the same `models` list. Models that failed earlier are retried.

## POST /api/extract

Send `multipart/form-data` with a `file` field. Accepted types are `.txt`, `.md`, `.vtt`, `.srt`, `.docx` and text-based `.pdf`; the default size limit is 10 MB.

```json
{"filename": "notes.docx", "file_type": "docx", "text": "Ann: I'll send…", "word_count": 18, "char_count": 96, "pages": null, "warnings": []}
```

| Status | When |
|---|---|
| 400 | empty file |
| 413 | file too large |
| 415 | unsupported type, legacy `.doc`, binary data, or the content does not match the extension |
| 422 | corrupt, password-protected or scanned (image-only) PDF |

## POST /api/analyze

Request:

```json
{
  "transcript": "Priya: Marcus, can you fix the checkout crash by Thursday?\nMarcus: Sure, I'll do it.",
  "title": "Launch sync",
  "meeting_date": "2026-03-04",
  "context": "Mobile team"
}
```

Only `transcript` is required. `meeting_date` (ISO format) is used to resolve relative deadlines; if it is missing, a `Date:` header line in the transcript is used when present.

Response: `AnalysisReport`. The main fields are:

| Field | Content |
|---|---|
| `meeting`, `stats`, `warnings`, `models`, `timings_ms` | metadata and processing notes |
| `summary` | `method`, `executive[]` and `detailed[]` (each sentence: `text`, `evidence[]`, `grounding`), `discussion_points[]`, `decision_summary`, `follow_up_summary`, `removed_unsupported` |
| `topics[]` | `title`, `keywords`, `summary`, `key_points`, `speakers`, `sentence_ids`, timestamps |
| `action_items[]` | `id`, `description`, `owner`, `owner_source`, `deadline`, `status`, `priority`, `is_inferred`, `needs_review`, `review_reasons`, `signal`, `evidence`, `edited` |
| `deadlines[]` | `text`, `normalized_date`, `date_type`, `granularity`, `is_ambiguous`, `note`, `related_action_id`, `evidence` |
| `decisions[]` | `text`, `status` (confirmed/tentative/rejected), `kind` (decision/agreement/approval), `is_inferred`, review fields, `evidence` |
| `risks[]` | `text`, `kind` (risk/blocker), `severity`, review fields, `evidence` |
| `questions[]` | `text`, `asked_by`, `status` (unanswered/deferred/open_issue), `evidence`, `response_evidence` |
| `entities[]`, `people[]`, `keywords[]`, `next_steps[]` | see `schemas.py` |
| `utterances[]`, `sentences[]` | the parsed transcript; evidence refers to `sentences[].id` |

`Evidence` objects have the shape `{sentence_id, speaker, timestamp, text}`.

Validation errors return 422, for example: `transcript: Transcript is empty.`, `The transcript is too short to analyse (6 words; at least 15 are needed).`, `The transcript is too long (…)` or `meeting_date: Input should be a valid date…`.

## POST /api/analyze/stream

This takes the same body as `/api/analyze` and returns `application/x-ndjson`, one JSON event per line:

```text
{"type": "accepted", "stages": [{"key": "models", "label": "Loading NLP models"}, … 11 stages]}
{"type": "queued", "message": "Waiting for another analysis to finish."}          (only if busy)
{"type": "stage", "stage": "models", "label": "Loading NLP models", "status": "started", "detail": null}
{"type": "stage", "stage": "models", "label": "Loading NLP models", "status": "progress", "detail": "Loading summarization model … (downloads ~1.2 GB on first run)"}
{"type": "stage", "stage": "models", "label": "Loading NLP models", "status": "completed", "detail": null, "elapsed_ms": 11054.3}
…
{"type": "stage", "stage": "summary", "status": "progress", "detail": "Summarising topic 2 of 4"}
…
{"type": "result", "report": { …AnalysisReport… }}
```

If something goes wrong, the stream ends with `{"type": "error", "code": "validation" | "internal", "message": "…"}` instead of `result`. Input validation happens before streaming starts, so invalid input gets an HTTP 422 rather than a stream.

The stages, in order, are: `models`, `preprocess`, `entities`, `topics`, `actions`, `decisions`, `risks`, `questions`, `summary`, `next_steps`, `finalize`.

## POST /api/export/{format}

`format` is one of `json`, `csv`, `markdown` or `pdf`. The body is an `AnalysisReport`, typically the one returned by analyze with the user's edits applied. The response is a file with `Content-Disposition: attachment; filename="MeetingMind_<title>.<ext>"`.

- **CSV columns:** `id, description, owner, owner_source, status, priority, deadline_text, deadline_date, deadline_ambiguous, needs_review, review_reasons, edited, evidence`. The file is UTF-8 with a BOM, and cells starting with `=`, `+`, `-` or `@` are prefixed with `'` to prevent spreadsheet formula injection.
- **PDF:** meeting minutes containing the executive summary, decisions table, action-item table (with review markers), risks, open questions, next steps and topics.
- If any action item has `edited: true` and `edited_at` is empty, the server sets `edited_at`.

## Example with curl

```bash
curl -s -X POST localhost:8000/api/analyze -H "content-type: application/json" \
  -d '{"transcript": "Ann: I will send the budget to finance by Friday.\nBen: Thanks Ann, I will review it on Monday.", "meeting_date": "2026-03-04"}' \
  | python -m json.tool | head -40
```
