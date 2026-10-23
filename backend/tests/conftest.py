import dataclasses
import os
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from app.config import get_settings  # noqa: E402
from app.nlp import models as models_module  # noqa: E402
from app.nlp.models import ModelRegistry  # noqa: E402
from app.nlp.pipeline import analyze  # noqa: E402
from app.schemas import AnalyzeRequest  # noqa: E402

SAMPLE = ROOT.parent / "samples" / "sample_transcript.txt"
MEETING_DATE = date(2026, 3, 4)  # a Wednesday


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: loads the abstractive summarization model (~1.2 GB)")


@pytest.fixture(scope="session")
def registry():
    """Real spaCy + Sentence-Transformers models; summarizer disabled for speed."""
    settings = dataclasses.replace(get_settings(), summary_mode="extractive")
    reg = ModelRegistry(settings)
    models_module.set_registry(reg)
    yield reg
    models_module.set_registry(None)


@pytest.fixture(scope="session")
def run(registry):
    def _run(text: str, meeting_date=MEETING_DATE, **kw):
        return analyze(AnalyzeRequest(transcript=text, meeting_date=meeting_date, **kw), registry=registry)

    return _run


@pytest.fixture(scope="session")
def sample_text() -> str:
    return SAMPLE.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def sample_report(run, sample_text):
    return run(sample_text, title="Mobile App Launch Sync")


def find(items, needle: str, attr: str = "description"):
    needle = needle.lower()
    return [i for i in items if needle in getattr(i, attr).lower()]
