"""CSV/JSONL input and output for segment LLM cleanup.

Extracted verbatim from the former ``scripts/segments_llm_cleanup_pipeline.py``
under ADR-0033. Reads the segments/glossary CSVs, batches rows, and writes the
rewritten segments CSV plus raw per-batch request/response dumps. The segments
CSV schema (segment_id, zh-CN, ko) is the data-schema invariant (ADR-0004).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from longtu_translation_pipeline.cleanup.common import ensure_csv_columns

from .models import (
    GLOSSARY_SCHEMA,
    GlossaryTerm,
    RowOutcome,
    SEGMENT_SCHEMA,
    SegmentRow,
)


def read_segments(path: Path) -> list[SegmentRow]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        ensure_csv_columns(reader, SEGMENT_SCHEMA, path)
        rows = [
            SegmentRow(
                segment_id=(row.get("segment_id") or "").strip(),
                zh=(row.get("zh-CN") or "").strip(),
                ko=(row.get("ko") or "").strip(),
            )
            for row in reader
        ]
    if not rows:
        raise RuntimeError(f"No segment rows found: {path}")
    return rows


def read_glossary(path: Path) -> list[GlossaryTerm]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        ensure_csv_columns(reader, GLOSSARY_SCHEMA, path)
        rows = [
            GlossaryTerm(
                term_id=(row.get("term_id") or "").strip(),
                zh=(row.get("zh-CN") or "").strip(),
                ko=(row.get("ko") or "").strip(),
            )
            for row in reader
            if (row.get("zh-CN") or "").strip() and (row.get("ko") or "").strip()
        ]
    if not rows:
        raise RuntimeError(f"No glossary rows found: {path}")
    return rows


def make_batches(rows: list[SegmentRow], batch_size: int) -> list[list[SegmentRow]]:
    return [rows[index : index + batch_size] for index in range(0, len(rows), batch_size)]


def write_segments(path: Path, outcomes: list[RowOutcome]) -> None:
    output: list[dict[str, str]] = []
    for new_id, outcome in enumerate(
        [outcome for outcome in outcomes if outcome.final_action != "REMOVE"], 1
    ):
        output.append(
            {
                "segment_id": str(new_id),
                "zh-CN": outcome.row.zh,
                "ko": outcome.final_ko,
            }
        )
    write_csv(path, SEGMENT_SCHEMA, output)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_raw_batch(
    raw_dir: Path,
    batch_no: int,
    attempt: int,
    request_payload: dict[str, Any],
    response: dict[str, Any] | None,
    error: str | None,
) -> None:
    path = raw_dir / f"batch-{batch_no:04d}-attempt-{attempt}.json"
    payload = {
        "batch_no": batch_no,
        "attempt": attempt,
        "request": request_payload,
        "response": response,
        "error": error,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
