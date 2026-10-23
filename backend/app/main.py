"""FastAPI application factory.

Run with:  uvicorn app.main:app --reload --port 8000   (from the backend/ directory)
"""
from __future__ import annotations

import logging
import threading

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .api.routes import router
from .config import get_settings
from .nlp.models import get_registry


def _validation_message(exc: RequestValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x not in ("body",))
        msg = err.get("msg", "invalid value").removeprefix("Value error, ")
        parts.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(parts) or "Invalid request."


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = FastAPI(
        title="MeetingMind API",
        version=__version__,
        description="Meeting transcript intelligence: summaries, decisions, action items, deadlines, risks and more.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    max_body = settings.max_transcript_chars * 4 + 2_000_000

    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):
        length = request.headers.get("content-length")
        limit = max(max_body, settings.max_upload_mb * 1_048_576 + 100_000)
        if length and length.isdigit() and int(length) > limit:
            return JSONResponse(status_code=413, content={"detail": "Request body is too large."})
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(_: Request, exc: RequestValidationError):
        # Do not echo the submitted body (it may contain the transcript) back to the client.
        return JSONResponse(status_code=422, content={"detail": _validation_message(exc)})

    app.include_router(router)

    @app.get("/")
    def root():
        return {"name": "MeetingMind API", "version": __version__, "docs": "/docs", "health": "/api/health"}

    if settings.preload_models:
        def preload():
            registry = get_registry()
            for key in registry.keys():
                if registry.state(key) != "disabled":
                    registry.try_get(key)

        threading.Thread(target=preload, name="model-preload", daemon=True).start()
    return app


app = create_app()
