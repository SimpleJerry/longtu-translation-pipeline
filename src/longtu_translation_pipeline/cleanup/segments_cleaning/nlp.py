"""NLP model loading and caching for the segments_cleaning pipeline (ADR-0033 step 8b)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

ZH_STANZA_PROCESSORS = "tokenize,pos"
KO_STANZA_PROCESSORS = "tokenize,pos"


def batched(values: list[Any], size: int) -> list[list[Any]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def summarize_stanza_doc(doc: Any) -> dict[str, Any]:
    words = [word for sent in doc.sentences for word in sent.words]
    upos = [word.upos for word in words]
    summary = " ".join(f"{word.text}/{word.upos}" for word in words[:10])
    return {"upos": upos, "summary": summary}


def load_stanza_pipelines(stanza_dir: Path) -> tuple[Any, Any]:
    import stanza

    common = {"model_dir": str(stanza_dir), "download_method": None, "verbose": False}
    try:
        zh = stanza.Pipeline("zh", processors=ZH_STANZA_PROCESSORS, **common)
        ko = stanza.Pipeline("ko", processors=KO_STANZA_PROCESSORS, **common)
    except Exception as exc:  # pragma: no cover - user-facing setup guard
        command = (
            "$env:STANZA_RESOURCES_DIR="
            f"'{stanza_dir.resolve()}'; "
            "venv\\Scripts\\python.exe -c "
            f"\"import stanza; stanza.download('zh', model_dir=r'{stanza_dir.resolve()}'); "
            f"stanza.download('ko', model_dir=r'{stanza_dir.resolve()}')\""
        )
        raise RuntimeError(
            "Stanza zh/ko models are not available. Download them first:\n"
            f"{command}\nOriginal error: {type(exc).__name__}: {exc}"
        ) from exc
    return zh, ko


def build_stanza_cache(
    pipeline: Any,
    values: list[str],
    *,
    batch_size: int,
    label: str,
) -> dict[str, dict[str, Any]]:
    unique = sorted({value for value in values if value})
    cache: dict[str, dict[str, Any]] = {}
    print(f"Stanza processing {label}: {len(unique)} unique texts")
    for batch in batched(unique, batch_size):
        docs = pipeline.bulk_process(batch)
        for text, doc in zip(batch, docs):
            cache[text] = summarize_stanza_doc(doc)
    return cache


def load_embedding_model(primary: str, fallback: str, hf_home: Path) -> tuple[Any, str, str]:
    os.environ.setdefault("HF_HOME", str(hf_home.resolve()))

    import torch
    from sentence_transformers import SentenceTransformer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    try:
        return SentenceTransformer(primary, device=device), primary, device
    except Exception as exc:
        print(f"Primary embedding model failed: {type(exc).__name__}: {exc}")
        return SentenceTransformer(fallback, device=device), fallback, device
