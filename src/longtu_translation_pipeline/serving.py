"""Synchronous HTTP/JSON translation service (ADR-0034).

A thin serving layer over the shared generation core: it applies source
terminology markers, runs the fixed-default decoding, strips markers, and
exposes model provenance. The request/response schema is deliberately distinct
from the RF-007 evaluation CSV — serving has no reference at request time
(ADR-0034 sec 2 / sec 9).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import ServingConfig
from .inference import LoadedTranslator, translate_texts
from .text_protection import GlossaryTerm

if TYPE_CHECKING:  # pragma: no cover
    pass


class TranslateItem(BaseModel):
    text: str
    id: str | None = None


class TranslateRequest(BaseModel):
    items: list[TranslateItem]


def build_model_info(
    serving_config: ServingConfig,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Provenance + contract parameters exposed by /info and every response."""
    inference = serving_config.inference
    prov = provenance or {}
    return {
        "checkpoint": str(inference.model.path),
        "tokenizer": inference.model.tokenizer_name,
        "language_pair": f"{inference.language.source_code}->{inference.language.target_code}",
        "decoding": {
            "num_beams": inference.generation.num_beams,
            "length_penalty": inference.generation.length_penalty,
            "no_repeat_ngram_size": inference.generation.no_repeat_ngram_size,
            "max_length": inference.generation.max_length,
        },
        "source_terminology_markers": inference.glossary.source_terminology_markers,
        "strip_glossary_markers": inference.output.strip_glossary_markers,
        "corpus_sha256": prov.get("corpus_sha256"),
        "seed": prov.get("seed"),
    }


def create_app(
    serving_config: ServingConfig,
    translator: LoadedTranslator,
    terms: Sequence[GlossaryTerm] | None = None,
    provenance: dict[str, Any] | None = None,
) -> FastAPI:
    """Build the FastAPI app over an already-loaded translator (ADR-0034).

    The model is loaded by the caller (see ``build_runtime_app``) and injected,
    which keeps ``/health`` model-free and lets contract tests run without a
    model download (ADR-0011 spirit).
    """
    runtime = serving_config.runtime
    max_length = serving_config.inference.generation.max_length
    info = build_model_info(serving_config, provenance)
    semaphore = threading.Semaphore(runtime.max_concurrency)

    app = FastAPI(title="longtu zh-CN -> ko translation", version="adr-0034")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/info")
    def info_endpoint() -> dict[str, Any]:
        return {"model": info}

    @app.post("/translate")
    def translate(request: TranslateRequest) -> dict[str, Any]:
        items = request.items
        if not items:
            raise HTTPException(status_code=422, detail="items must not be empty")
        if len(items) > runtime.max_items_per_request:
            raise HTTPException(
                status_code=422,
                detail=f"items exceeds max_items_per_request={runtime.max_items_per_request}",
            )

        texts: list[str] = []
        for index, item in enumerate(items):
            text = item.text.strip()
            if not text:
                raise HTTPException(status_code=422, detail=f"items[{index}].text must not be empty")
            if _too_long(translator, text, max_length):
                raise HTTPException(
                    status_code=422,
                    detail=f"items[{index}].text exceeds max_length={max_length} tokens",
                )
            texts.append(text)

        if not semaphore.acquire(blocking=False):
            raise HTTPException(status_code=429, detail="server at max_concurrency, retry later")
        try:
            translations = translate_texts(translator, texts, terms)
        finally:
            semaphore.release()

        results = [
            {"id": item.id, "source": text, "translation": translation}
            for item, text, translation in zip(items, texts, translations)
        ]
        return {"model": info, "results": results}

    return app


def build_runtime_app(serving_config: ServingConfig, device: str = "auto") -> FastAPI:
    """Load the model + glossary once and build the serving app (ADR-0034).

    Fail-fast: a missing model / tokenizer / glossary raises here, before the
    process becomes servable (ADR-0034 sec 7).
    """
    from .inference import load_translator
    from .text_protection import load_glossary_terms

    inference = serving_config.inference
    translator = load_translator(inference, inference.model.path, device=device)
    terms = (
        load_glossary_terms(inference.glossary.path)
        if inference.glossary.source_terminology_markers
        else []
    )
    provenance = _read_provenance(inference.model.path)
    return create_app(serving_config, translator, terms=terms, provenance=provenance)


def _too_long(translator: LoadedTranslator, text: str, max_length: int) -> bool:
    try:
        token_ids = translator.tokenizer.encode(text)
    except Exception:
        return False
    return len(token_ids) > max_length


def _read_provenance(model_path: str | Path) -> dict[str, Any] | None:
    """Best-effort read of corpus SHA256 + seed from the run manifest.

    The training ``run_manifest.json`` sits in the run directory; a published
    checkpoint is a ``checkpoint-N`` subdirectory of it (ADR-0020). Returns
    ``None`` when no manifest is found or readable.
    """
    path = Path(model_path)
    for candidate in (path / "run_manifest.json", path.parent / "run_manifest.json"):
        if not candidate.exists():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        section = data.get("data", {}) if isinstance(data, dict) else {}
        if not isinstance(section, dict):
            return None
        return {
            "corpus_sha256": section.get("segments_sha256"),
            "seed": section.get("split_seed"),
        }
    return None
