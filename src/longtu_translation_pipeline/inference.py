"""Inference planning and generation helpers for RF-006."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .config import InferenceConfig
from .text_protection import strip_glossary_markers
from .training import (
    add_marker_special_tokens,
    cuda_device_name,
    cuda_memory_summary,
    find_latest_checkpoint,
    resolve_training_device,
)


@dataclass(frozen=True)
class InferenceRecord:
    record_id: str
    text: str
    reference: str


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


@dataclass(frozen=True)
class GeneratedTranslationRow:
    record_id: str
    source: str
    reference: str
    candidate: str


@dataclass(frozen=True)
class InferenceGenerationResult:
    config_path: Path
    input_path: Path
    output_path: Path
    model_path: Path
    tokenizer_name: str
    source_code: str
    target_code: str
    forced_bos_token_id: int
    special_tokens_added: int
    tokenizer_vocab_size: int
    embedding_size_before: int
    embedding_size_after: int
    device: str
    cuda_device_name: str
    cuda_memory_summary: str
    batch_size: int
    max_length: int
    strip_glossary_markers: bool
    input_rows: int
    generated_rows: int
    output_columns: list[str]
    preview_rows: list[GeneratedTranslationRow]


@dataclass(frozen=True)
class ValidationGenerationResult:
    generation: InferenceGenerationResult
    run_dir: Path
    training_manifest_path: Path
    validation_split_path: Path
    generation_manifest_path: Path


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
        require_columns(
            input_path,
            reader.fieldnames,
            [config.input.id_column, config.input.text_column, config.input.reference_column],
        )
        for row_number, row in enumerate(reader, start=2):
            record_id = row.get(config.input.id_column, "").strip()
            text = row.get(config.input.text_column, "").strip()
            reference = row.get(config.input.reference_column, "").strip()
            if not record_id or not text or not reference:
                raise ValueError(f"Empty inference value at {input_path}:{row_number}")
            records.append(InferenceRecord(record_id=record_id, text=text, reference=reference))

    if not records:
        raise ValueError(f"No inference records found: {input_path}")

    return records


def generate_translations(
    config: InferenceConfig,
    model_path: str | Path | None = None,
    output_path: str | Path | None = None,
    sample_rows: int = 8,
    device: str = "auto",
) -> InferenceGenerationResult:
    if sample_rows <= 0:
        raise ValueError("sample_rows must be a positive integer")

    records = read_inference_records(config)[:sample_rows]
    if not records:
        raise ValueError("No inference records selected for generation")

    resolved_model_path = Path(model_path) if model_path is not None else config.model.path
    resolved_output_path = Path(output_path) if output_path is not None else config.output.path
    return generate_records(
        config,
        records,
        resolved_model_path,
        resolved_output_path,
        device=device,
    )


def generate_validation_translations(
    config: InferenceConfig,
    run_dir: str | Path,
    model_path: str | Path | None = None,
    output_path: str | Path | None = None,
    validation_rows: int | None = None,
    device: str = "auto",
    repo_root: str | Path | None = None,
) -> ValidationGenerationResult:
    if validation_rows is not None and validation_rows <= 0:
        raise ValueError("validation_rows must be a positive integer when provided")

    resolved_run_dir = Path(run_dir)
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    manifest_path = resolved_run_dir / "run_manifest.json"
    manifest = read_run_manifest(manifest_path)
    validation_split_path = resolve_manifest_path(
        require_manifest_string(manifest, ["data", "validation_split_path"], manifest_path),
        run_dir=resolved_run_dir,
        repo_root=root,
    )
    if not validation_split_path.exists():
        raise ValueError(f"Validation split does not exist: {validation_split_path}")

    resolved_model_path = (
        Path(model_path)
        if model_path is not None
        else resolve_latest_run_checkpoint(resolved_run_dir)
    )
    if not resolved_model_path.is_absolute() and not resolved_model_path.exists():
        candidate = root / resolved_model_path
        if candidate.exists():
            resolved_model_path = candidate
    if not resolved_model_path.exists() or not resolved_model_path.is_dir():
        raise ValueError(f"Checkpoint does not exist or is not a directory: {resolved_model_path}")

    records = read_validation_records(validation_split_path)
    if validation_rows is not None:
        records = records[:validation_rows]
    if not records:
        raise ValueError("No validation records selected for generation")

    resolved_output_path = (
        Path(output_path)
        if output_path is not None
        else default_validation_output_path(root, resolved_run_dir)
    )
    generation = generate_records(
        config,
        records,
        resolved_model_path,
        resolved_output_path,
        device=device,
        input_path=validation_split_path,
    )
    generation_manifest_path = resolved_output_path.with_name("validation_generation_manifest.json")
    write_validation_generation_manifest(
        generation_manifest_path,
        generation,
        run_dir=resolved_run_dir,
        training_manifest_path=manifest_path,
        validation_split_path=validation_split_path,
    )
    return ValidationGenerationResult(
        generation=generation,
        run_dir=resolved_run_dir,
        training_manifest_path=manifest_path,
        validation_split_path=validation_split_path,
        generation_manifest_path=generation_manifest_path,
    )


def generate_records(
    config: InferenceConfig,
    records: Sequence[InferenceRecord],
    model_path: Path,
    output_path: Path,
    device: str = "auto",
    input_path: Path | None = None,
) -> InferenceGenerationResult:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(config.model.tokenizer_name)
    configure_tokenizer_language_codes(tokenizer, config)
    special_tokens_added = add_marker_special_tokens(tokenizer)
    forced_bos_token_id = tokenizer.convert_tokens_to_ids(config.language.target_code)
    if forced_bos_token_id is None or forced_bos_token_id < 0:
        raise ValueError(f"Tokenizer does not know target language code: {config.language.target_code}")

    inference_device = resolve_training_device(device)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
    embedding_size_before = model.get_input_embeddings().num_embeddings
    if embedding_size_before != len(tokenizer):
        model.resize_token_embeddings(len(tokenizer))
    embedding_size_after = model.get_input_embeddings().num_embeddings

    if inference_device == "cuda":
        model = model.to("cuda")
    model.eval()

    rows = run_generation_batches(config, tokenizer, model, records, int(forced_bos_token_id))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_generation_csv(output_path, rows)

    return InferenceGenerationResult(
        config_path=config.path,
        input_path=input_path if input_path is not None else config.input.path,
        output_path=output_path,
        model_path=model_path,
        tokenizer_name=config.model.tokenizer_name,
        source_code=config.language.source_code,
        target_code=config.language.target_code,
        forced_bos_token_id=int(forced_bos_token_id),
        special_tokens_added=special_tokens_added,
        tokenizer_vocab_size=len(tokenizer),
        embedding_size_before=embedding_size_before,
        embedding_size_after=embedding_size_after,
        device=inference_device,
        cuda_device_name=cuda_device_name(inference_device),
        cuda_memory_summary=cuda_memory_summary(inference_device),
        batch_size=config.generation.batch_size,
        max_length=config.generation.max_length,
        strip_glossary_markers=config.output.strip_glossary_markers,
        input_rows=len(records),
        generated_rows=len(rows),
        output_columns=["segment_id", "source", "references", "candidates"],
        preview_rows=rows[: config.dry_run.preview_rows],
    )


def read_validation_records(path: str | Path) -> list[InferenceRecord]:
    validation_path = Path(path)
    records: list[InferenceRecord] = []
    with validation_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        require_columns(validation_path, reader.fieldnames, ["segment_id", "zh-CN", "ko"])
        for row_number, row in enumerate(reader, start=2):
            record_id = row.get("segment_id", "").strip()
            text = row.get("zh-CN", "").strip()
            reference = row.get("ko", "").strip()
            if not record_id or not text or not reference:
                raise ValueError(f"Empty validation value at {validation_path}:{row_number}")
            records.append(InferenceRecord(record_id=record_id, text=text, reference=reference))
    if not records:
        raise ValueError(f"No validation records found: {validation_path}")
    return records


def read_run_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise ValueError(f"Run manifest does not exist: {manifest_path}")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid run manifest JSON: {manifest_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Run manifest root must be a JSON object: {manifest_path}")
    return data


def require_manifest_string(data: dict[str, Any], keys: Sequence[str], path: Path) -> str:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"Run manifest is missing {'.'.join(keys)}: {path}")
        value = value[key]
    if not isinstance(value, str) or not value:
        raise ValueError(f"Run manifest field must be a non-empty string: {'.'.join(keys)}")
    return value


def resolve_manifest_path(value: str, run_dir: Path, repo_root: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    candidates = [repo_root / path, run_dir / path]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def resolve_latest_run_checkpoint(run_dir: str | Path) -> Path:
    checkpoint = find_latest_checkpoint(run_dir)
    if checkpoint is None:
        raise ValueError(f"No numeric checkpoint found in run directory: {run_dir}")
    return checkpoint


def default_validation_output_path(repo_root: Path, run_dir: Path) -> Path:
    return repo_root / "data" / "review" / "inference" / "validation" / run_dir.name / "validation_generated.csv"


def write_validation_generation_manifest(
    path: Path,
    generation: InferenceGenerationResult,
    run_dir: Path,
    training_manifest_path: Path,
    validation_split_path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_dir": str(run_dir),
        "training_manifest_path": str(training_manifest_path),
        "checkpoint_path": str(generation.model_path),
        "validation_split_path": str(validation_split_path),
        "output_csv": str(generation.output_path),
        "row_count": generation.generated_rows,
        "language_pair": f"{generation.source_code}->{generation.target_code}",
        "forced_bos_token_id": generation.forced_bos_token_id,
        "device": generation.device,
        "batch_size": generation.batch_size,
        "max_length": generation.max_length,
        "strip_glossary_markers": generation.strip_glossary_markers,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def configure_tokenizer_language_codes(tokenizer: object, config: InferenceConfig) -> None:
    for attribute, value in (
        ("src_lang", config.language.source_code),
        ("tgt_lang", config.language.target_code),
    ):
        try:
            setattr(tokenizer, attribute, value)
        except Exception:
            continue


def run_generation_batches(
    config: InferenceConfig,
    tokenizer: object,
    model: object,
    records: Sequence[InferenceRecord],
    forced_bos_token_id: int,
) -> list[GeneratedTranslationRow]:
    rows: list[GeneratedTranslationRow] = []
    for start in range(0, len(records), config.generation.batch_size):
        batch_records = records[start : start + config.generation.batch_size]
        texts = [record.text for record in batch_records]
        encoded = tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=config.generation.max_length,
        )
        model_device = next(model.parameters()).device
        encoded = {key: value.to(model_device) for key, value in encoded.items()}
        generated = model.generate(
            **encoded,
            forced_bos_token_id=forced_bos_token_id,
            max_length=config.generation.max_length,
        )
        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        for record, candidate in zip(batch_records, decoded):
            clean_candidate = candidate.strip()
            if config.output.strip_glossary_markers:
                clean_candidate = strip_glossary_markers(clean_candidate).strip()
            rows.append(
                GeneratedTranslationRow(
                    record_id=record.record_id,
                    source=record.text,
                    reference=record.reference,
                    candidate=clean_candidate,
                )
            )
    return rows


def write_generation_csv(path: Path, rows: Sequence[GeneratedTranslationRow]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["segment_id", "source", "references", "candidates"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "segment_id": row.record_id,
                    "source": row.source,
                    "references": row.reference,
                    "candidates": row.candidate,
                }
            )


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
        lines.append(f"preview_{index}={record.record_id}: {record.text} => {record.reference}")
    return "\n".join(lines)


def format_inference_generation(result: InferenceGenerationResult) -> str:
    lines = [
        "Inference generation result",
        f"config={result.config_path}",
        f"input={result.input_path}",
        f"output={result.output_path}",
        f"model_path={result.model_path}",
        f"tokenizer_name={result.tokenizer_name}",
        f"language_pair={result.source_code}->{result.target_code}",
        f"forced_bos_token_id={result.forced_bos_token_id}",
        f"special_tokens_added={result.special_tokens_added}",
        f"tokenizer_vocab_size={result.tokenizer_vocab_size}",
        f"embedding_size_before={result.embedding_size_before}",
        f"embedding_size_after={result.embedding_size_after}",
        f"device={result.device}",
        f"cuda_device_name={result.cuda_device_name}",
        f"cuda_memory_summary={result.cuda_memory_summary}",
        f"batch_size={result.batch_size}",
        f"max_length={result.max_length}",
        f"strip_glossary_markers={result.strip_glossary_markers}",
        f"input_rows={result.input_rows}",
        f"generated_rows={result.generated_rows}",
        f"output_columns={','.join(result.output_columns)}",
    ]
    for index, row in enumerate(result.preview_rows, start=1):
        lines.append(
            f"preview_{index}={row.record_id}: "
            f"{row.source} => {row.candidate} | reference={row.reference}"
        )
    return "\n".join(lines)


def format_validation_generation(result: ValidationGenerationResult) -> str:
    lines = [
        "Validation generation result",
        f"run_dir={result.run_dir}",
        f"training_manifest={result.training_manifest_path}",
        f"validation_split={result.validation_split_path}",
        f"generation_manifest={result.generation_manifest_path}",
    ]
    lines.extend(format_inference_generation(result.generation).splitlines()[1:])
    return "\n".join(lines)
