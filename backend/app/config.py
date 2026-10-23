"""Runtime configuration, read from environment variables (optionally via a .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

try:  # python-dotenv is optional
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # pragma: no cover
    pass


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # Models
    summarizer_model: str = field(
        default_factory=lambda: os.getenv("MEETINGMIND_SUMMARIZER_MODEL", "philschmid/distilbart-cnn-12-6-samsum")
    )
    embedding_model: str = field(
        default_factory=lambda: os.getenv("MEETINGMIND_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    )
    spacy_model: str = field(default_factory=lambda: os.getenv("MEETINGMIND_SPACY_MODEL", "en_core_web_sm"))
    # "abstractive" uses the transformer summarizer; "extractive" skips it (fast, low memory).
    summary_mode: str = field(default_factory=lambda: os.getenv("MEETINGMIND_SUMMARY_MODE", "abstractive").lower())
    preload_models: bool = field(default_factory=lambda: _bool("MEETINGMIND_PRELOAD_MODELS", False))
    device: str = field(default_factory=lambda: os.getenv("MEETINGMIND_DEVICE", "auto"))

    # Limits
    max_upload_mb: int = field(default_factory=lambda: _int("MEETINGMIND_MAX_UPLOAD_MB", 10))
    max_transcript_chars: int = field(default_factory=lambda: _int("MEETINGMIND_MAX_TRANSCRIPT_CHARS", 300_000))
    min_transcript_words: int = field(default_factory=lambda: _int("MEETINGMIND_MIN_TRANSCRIPT_WORDS", 15))

    # Server
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in os.getenv(
                "MEETINGMIND_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if o.strip()
        )
    )
    log_level: str = field(default_factory=lambda: os.getenv("MEETINGMIND_LOG_LEVEL", "INFO"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
