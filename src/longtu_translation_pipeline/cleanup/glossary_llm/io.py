"""CSV/JSONL input and output for glossary LLM cleanup.

Extracted verbatim from the former ``scripts/glossary_llm_cleanup_pipeline.py``
under ADR-0033. Reads the glossary CSV, batches rows, writes the cleaned
glossary (locale-sorted by Chinese), the removed-rows CSV, and raw per-batch
request/response dumps. The glossary CSV schema (term_id, zh-CN, ko) is the
data-schema invariant (ADR-0004).
"""

from __future__ import annotations

import csv
import json
import locale
from pathlib import Path
from typing import Any

from longtu_translation_pipeline.cleanup.common import ensure_csv_columns

from .models import (
    Decision,
    GLOSSARY_SCHEMA,
    GlossaryRow,
    KEEP_ACTION,
    REMOVED_FIELDS,
)


def read_glossary(path: Path) -> list[GlossaryRow]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        ensure_csv_columns(reader, GLOSSARY_SCHEMA, path)
        rows = [
            GlossaryRow(
                term_id=(row.get("term_id") or "").strip(),
                zh=(row.get("zh-CN") or "").strip(),
                ko=(row.get("ko") or "").strip(),
            )
            for row in reader
        ]
    if not rows:
        raise RuntimeError(f"No glossary rows found: {path}")
    for index, row in enumerate(rows, 1):
        if not row.term_id or not row.zh or not row.ko:
            raise RuntimeError(f"Invalid empty glossary field at input row {index}.")
    return rows


def make_batches(rows: list[GlossaryRow], batch_size: int) -> list[list[GlossaryRow]]:
    return [rows[index : index + batch_size] for index in range(0, len(rows), batch_size)]


def write_removed_csv(path: Path, audit_rows: list[dict[str, str]]) -> None:
    rows: list[dict[str, str]] = []
    for removed_id, row in enumerate(audit_rows, 1):
        rows.append(
            {
                "removed_id": str(removed_id),
                "original_term_id": row["original_term_id"],
                "action": row["action"],
                "reason": row["reason"],
                "zh-CN": row["zh-CN"],
                "ko": row["ko"],
            }
        )
    write_csv(path, REMOVED_FIELDS, rows)


def write_clean_glossary(
    path: Path, rows: list[GlossaryRow], decisions: dict[str, Decision]
) -> None:
    kept_rows = [row for row in rows if decisions[row.term_id].action == KEEP_ACTION]
    sorted_rows = sort_by_chinese(kept_rows)
    output = [
        {"term_id": str(new_id), "zh-CN": row.zh, "ko": row.ko}
        for new_id, row in enumerate(sorted_rows, 1)
    ]
    write_csv(path, GLOSSARY_SCHEMA, output)


def sort_by_chinese(rows: list[GlossaryRow]) -> list[GlossaryRow]:
    try:
        locale.setlocale(locale.LC_COLLATE, "Chinese_China.936")
    except locale.Error:
        try:
            locale.setlocale(locale.LC_COLLATE, "zh_CN.UTF-8")
        except locale.Error:
            locale.setlocale(locale.LC_COLLATE, "")
    return sorted(rows, key=lambda row: locale.strxfrm(row.zh))


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
    payload = {
        "batch_no": batch_no,
        "attempt": attempt,
        "request": request_payload,
        "response": response,
        "error": error,
    }
    path = raw_dir / f"batch-{batch_no:04d}-attempt-{attempt}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
