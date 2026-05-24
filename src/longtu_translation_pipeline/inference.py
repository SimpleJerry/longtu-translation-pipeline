"""Dry-run inference planning for RF-006 phase 1."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .config import InferenceConfig


@dataclass(frozen=True)
class InferenceRecord:
    record_id: str
    text: str


@dataclass(frozen=True)
class InferenceDryRunPlan:
    config_path: Path
    input_path: Path
    output_path: Path
    model_path: Path
    source_code: str
    target_code: str
    batch_size: int
    max_length: int
    strip_glossary_markers: bool
    total_rows: int
    preview_records: list[InferenceRecord]


def build_inference_dry_run(config: InferenceConfig) -> InferenceDryRunPlan:
    records = read_inference_records(config)
    return InferenceDryRunPlan(
        config_path=config.path,
        input_path=config.input.path,
        output_path=config.output.path,
        model_path=config.model.path,
        source_code=config.language.source_code,
        target_code=config.language.target_code,
        batch_size=config.generation.batch_size,
        max_length=config.generation.max_length,
        strip_glossary_markers=config.output.strip_glossary_markers,
        total_rows=len(records),
        preview_records=records[: config.dry_run.preview_rows],
    )


def read_inference_records(config: InferenceConfig) -> list[InferenceRecord]:
    input_path = config.input.path
    records: list[InferenceRecord] = []

    with input_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        require_columns(input_path, reader.fieldnames, [config.input.id_column, config.input.text_column])
        for row_number, row in enumerate(reader, start=2):
            record_id = row.get(config.input.id_column, "").strip()
            text = row.get(config.input.text_column, "").strip()
            if not record_id or not text:
                raise ValueError(f"Empty inference value at {input_path}:{row_number}")
            records.append(InferenceRecord(record_id=record_id, text=text))

    if not records:
        raise ValueError(f"No inference records found: {input_path}")

    return records


def require_columns(path: Path, fieldnames: Sequence[str] | None, columns: Sequence[str]) -> None:
    missing = [column for column in columns if column not in (fieldnames or [])]
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")


def format_inference_dry_run(plan: InferenceDryRunPlan) -> str:
    lines = [
        "Inference dry-run plan",
        f"config={plan.config_path}",
        f"input={plan.input_path}",
        f"output={plan.output_path}",
        f"model={plan.model_path}",
        f"language_pair={plan.source_code}->{plan.target_code}",
        f"batch_size={plan.batch_size}",
        f"max_length={plan.max_length}",
        f"strip_glossary_markers={plan.strip_glossary_markers}",
        f"total_rows={plan.total_rows}",
    ]
    for index, record in enumerate(plan.preview_records, start=1):
        lines.append(f"preview_{index}={record.record_id}: {record.text}")
    return "\n".join(lines)
