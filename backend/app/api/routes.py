"""HTTP API. All endpoints are stateless: nothing is stored between requests."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse

from .. import __version__
from ..config import get_settings
from ..nlp.models import get_registry
from ..nlp.pipeline import STAGES, TranscriptValidationError, analyze, validate_transcript
from ..schemas import AnalysisReport, AnalyzeRequest, ExtractResponse, HealthResponse, ModelStatus
from ..services.exports import EXPORTERS, safe_filename
from ..services.file_extraction import FileExtractionError, extract_text

log = logging.getLogger("meetingmind.api")
router = APIRouter(prefix="/api")

# The models are CPU/GPU heavy; analyse one transcript at a time and queue the rest.
_analysis_lock = asyncio.Lock()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    registry = get_registry()
    return HealthResponse(
        status="ok",
        version=__version__,
        summary_mode=registry.settings.summary_mode,
        models=[ModelStatus(**m) for m in registry.status()],
    )


@router.post("/models/warmup", response_model=list[ModelStatus])
async def warmup() -> list[ModelStatus]:
    """Load all models now (otherwise they load on the first analysis). Retries earlier failures."""
    registry = get_registry()
    registry.reset_failures()

    def load_all():
        for key in registry.keys():
            if registry.state(key) != "disabled":
                registry.try_get(key)

    await run_in_threadpool(load_all)
    return [ModelStatus(**m) for m in registry.status()]


@router.post("/extract", response_model=ExtractResponse)
async def extract(file: UploadFile = File(...)) -> ExtractResponse:
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1_048_576
    data = await file.read(max_bytes + 1)
    await file.close()
    try:
        return await run_in_threadpool(extract_text, file.filename or "upload", data, max_bytes)
    except FileExtractionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _validate(req: AnalyzeRequest) -> None:
    s = get_settings()
    try:
        validate_transcript(req.transcript, s.min_transcript_words, s.max_transcript_chars)
    except TranscriptValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/analyze", response_model=AnalysisReport)
async def analyze_endpoint(req: AnalyzeRequest) -> AnalysisReport:
    _validate(req)
    async with _analysis_lock:
        try:
            return await run_in_threadpool(analyze, req)
        except TranscriptValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:  # never echo transcript content back in errors or logs
            log.exception("Analysis failed")
            raise HTTPException(status_code=500, detail=f"Analysis failed: {type(exc).__name__}") from exc


@router.post("/analyze/stream")
async def analyze_stream(req: AnalyzeRequest) -> StreamingResponse:
    """Run the analysis and stream newline-delimited JSON events.

    Events: {"type": "accepted"}, {"type": "queued"}, {"type": "stage", ...} for each real pipeline
    stage (started / progress / completed / failed), then {"type": "result", "report": {...}}
    or {"type": "error", "code": ..., "message": ...}.
    """
    _validate(req)
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def progress(event: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    async def runner() -> None:
        try:
            if _analysis_lock.locked():
                await queue.put({"type": "queued", "message": "Waiting for another analysis to finish."})
            async with _analysis_lock:
                report = await run_in_threadpool(analyze, req, None, progress)
            await queue.put({"type": "result", "report": report.model_dump(mode="json")})
        except TranscriptValidationError as exc:
            await queue.put({"type": "error", "code": "validation", "message": str(exc)})
        except Exception as exc:
            log.exception("Streaming analysis failed")
            await queue.put({"type": "error", "code": "internal", "message": f"Analysis failed: {type(exc).__name__}"})
        finally:
            await queue.put(None)

    async def events():
        task = asyncio.create_task(runner())
        yield json.dumps({"type": "accepted", "stages": [{"key": k, "label": label} for k, label in STAGES]}) + "\n"
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield json.dumps(event, default=str) + "\n"
        finally:
            await task

    return StreamingResponse(events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store"})


@router.post("/export/{fmt}")
async def export(fmt: Literal["json", "csv", "markdown", "pdf"], report: AnalysisReport) -> Response:
    """Render the report the client sends (including the user's edits) into a downloadable file."""
    exporter, media_type, ext = EXPORTERS[fmt]
    if report.edited_at is None and any(a.edited for a in report.action_items):
        report.edited_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        content = await run_in_threadpool(exporter, report)
    except Exception as exc:
        log.exception("Export failed")
        raise HTTPException(status_code=500, detail=f"Export failed: {type(exc).__name__}") from exc
    filename = safe_filename(report.meeting.title, ext)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )
