"""Lazy, thread-safe loading and caching of the NLP models.

Each model is loaded at most once per process. If a model fails to load, the failure is
recorded (and reported through /api/health and in report warnings) and the pipeline uses a
documented fallback instead of crashing.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..config import Settings, get_settings

log = logging.getLogger("meetingmind.models")


class ModelUnavailableError(RuntimeError):
    """Raised when a model cannot be loaded."""


@dataclass
class _Slot:
    name: str
    role: str
    loader: Callable[[], Any]
    state: str = "not_loaded"  # not_loaded | loading | ready | failed | disabled
    obj: Any = None
    error: Optional[str] = None
    load_seconds: Optional[float] = None
    lock: threading.Lock = field(default_factory=threading.Lock)


def _resolve_device(setting: str) -> str:
    if setting != "auto":
        return setting
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:  # pragma: no cover
        return "cpu"


class Seq2SeqSummarizer:
    """Thin wrapper around a seq2seq model. Uses generate() directly, which works on
    Transformers v4 and v5 (v5 removed the `summarization` pipeline)."""

    def __init__(self, model_name: str, device: str):
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.model.eval()
        self.device = device
        self.model.to(device)
        self.max_input_tokens = min(getattr(self.tokenizer, "model_max_length", 1024) or 1024, 1024)

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def summarize(self, texts: list[str], max_length: int = 130, min_length: int = 25) -> list[str]:
        import torch

        outputs: list[str] = []
        for text in texts:
            batch = self.tokenizer(
                [text], return_tensors="pt", truncation=True, max_length=self.max_input_tokens
            ).to(self.device)
            input_len = int(batch["input_ids"].shape[1])
            # Never ask for a summary longer than the input.
            hi = max(16, min(max_length, int(input_len * 0.8)))
            lo = min(min_length, max(5, hi // 3))
            with torch.no_grad():
                ids = self.model.generate(
                    **batch,
                    max_length=hi,
                    min_length=lo,
                    num_beams=4,
                    no_repeat_ngram_size=3,
                    early_stopping=True,
                )
            outputs.append(self.tokenizer.decode(ids[0], skip_special_tokens=True).strip())
        return outputs


class ModelRegistry:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.device = _resolve_device(self.settings.device)
        self._slots: dict[str, _Slot] = {
            "spacy": _Slot(self.settings.spacy_model, "linguistic analysis & NER", self._load_spacy),
            "embeddings": _Slot(self.settings.embedding_model, "sentence embeddings", self._load_embeddings),
            "summarizer": _Slot(self.settings.summarizer_model, "abstractive summarization", self._load_summarizer),
        }
        if self.settings.summary_mode != "abstractive":
            self._slots["summarizer"].state = "disabled"

    # -- loaders -----------------------------------------------------------------
    def _load_spacy(self):
        import spacy

        return spacy.load(self.settings.spacy_model)

    def _load_embeddings(self):
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(self.settings.embedding_model, device=self.device)

    def _load_summarizer(self):
        return Seq2SeqSummarizer(self.settings.summarizer_model, self.device)

    # -- public API --------------------------------------------------------------
    def get(self, key: str) -> Any:
        """Return the loaded model or raise ModelUnavailableError."""
        slot = self._slots[key]
        if slot.state == "ready":
            return slot.obj
        if slot.state == "disabled":
            raise ModelUnavailableError(f"{key} model disabled by configuration")
        with slot.lock:
            if slot.state == "ready":
                return slot.obj
            if slot.state == "failed":
                raise ModelUnavailableError(slot.error or f"{key} failed to load")
            slot.state = "loading"
            started = time.perf_counter()
            try:
                slot.obj = slot.loader()
            except Exception as exc:  # noqa: BLE001 - any loader failure must be contained
                slot.state = "failed"
                slot.error = f"{type(exc).__name__}: {exc}"[:500]
                log.error("Failed to load %s model %s: %s", key, slot.name, slot.error)
                raise ModelUnavailableError(slot.error) from exc
            slot.load_seconds = round(time.perf_counter() - started, 2)
            slot.state = "ready"
            log.info("Loaded %s model %s in %.1fs", key, slot.name, slot.load_seconds)
            return slot.obj

    def try_get(self, key: str) -> Any:
        try:
            return self.get(key)
        except ModelUnavailableError:
            return None

    def is_ready(self, key: str) -> bool:
        return self._slots[key].state == "ready"

    def state(self, key: str) -> str:
        return self._slots[key].state

    def name(self, key: str) -> str:
        return self._slots[key].name

    def error(self, key: str) -> Optional[str]:
        return self._slots[key].error

    def reset_failures(self) -> None:
        """Allow a retry of models that previously failed (e.g. after network recovery)."""
        for slot in self._slots.values():
            if slot.state == "failed":
                slot.state, slot.error = "not_loaded", None

    def status(self) -> list[dict]:
        return [
            {
                "name": s.name,
                "role": s.role,
                "state": s.state,
                "error": s.error,
                "load_seconds": s.load_seconds,
            }
            for s in self._slots.values()
        ]

    def keys(self) -> list[str]:
        return list(self._slots)


_registry: Optional[ModelRegistry] = None
_registry_lock = threading.Lock()


def get_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = ModelRegistry()
    return _registry


def set_registry(registry: Optional[ModelRegistry]) -> None:
    """Replace the global registry (used by tests and the notebook)."""
    global _registry
    _registry = registry
