"""I/O helpers and schema constants for glossary_semantic (ADR-0033 step 9b)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from longtu_translation_pipeline.cleanup.common import ensure_csv_columns

LANGS = ["zh-CN", "zh-TW", "en", "th", "id", "ja", "ko", "pt", "ru", "vi"]
SCHEMA = ["term_id", "zh-CN", "ko"]


def read_glossary_baseline(glossary_path: Path) -> list[dict[str, str]]:
    with glossary_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        ensure_csv_columns(reader, SCHEMA, glossary_path)
        rows = list(reader)

    baseline: list[dict[str, str]] = []
    for idx, row in enumerate(rows, 1):
        item = {"original_term_id": row.get("term_id") or str(idx)}
        for lang in LANGS:
            item[lang] = (row.get(lang) or "").strip()
        baseline.append(item)
    return baseline


def read_segment_evidence(segments_path: Path) -> dict[str, str]:
    text = {"zh-CN": [], "ko": []}
    with segments_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            for lang in text:
                value = (row.get(lang) or "").strip()
                if value:
                    text[lang].append(value)
    joined = {lang: "\n".join(values) for lang, values in text.items()}
    joined["zh-CN_upper"] = joined["zh-CN"].upper()
    joined["ko_upper"] = joined["ko"].upper()
    return joined


def batched(values: list[str], size: int) -> list[list[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)]
