"""Training data preparation and smoke-test tokenization helpers."""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .config import TrainingConfig
from .text_protection import load_glossary_terms, protect_training_pair


@dataclass(frozen=True)
class TrainingExample:
    segment_id: str
    source_text: str
    target_text: str


@dataclass(frozen=True)
class TrainingDryRunPlan:
    config_path: Path
    segments_path: Path
    glossary_path: Path
    base_model: str
    output_dir: Path
    source_code: str
    target_code: str
    terminology_markers: bool
    terminology_marker_scope: str
    total_rows: int
    train_rows: int
    validation_rows: int
    preview_examples: list[TrainingExample]


@dataclass(frozen=True)
class TokenizedTrainingExample:
    segment_id: str
    input_ids: list[int]
    attention_mask: list[int]
    labels: list[int]


@dataclass(frozen=True)
class TrainingSmokeTestPlan:
    config_path: Path
    segments_path: Path
    glossary_path: Path
    tokenizer_name: str
    source_code: str
    target_code: str
    max_length: int
    padding: str
    truncation: bool
    terminology_markers: bool
    terminology_marker_scope: str
    prepared_rows: int
    tokenized_rows: int
    language_code_assignments: list[str]
    preview_examples: list[TrainingExample]
    tokenized_examples: list[TokenizedTrainingExample]


def build_training_dry_run(config: TrainingConfig) -> TrainingDryRunPlan:
    examples = read_training_examples(config)
    train_examples, validation_examples = split_examples(
        examples,
        config.split.validation_ratio,
        config.split.seed,
    )
    preview_examples = apply_optional_terminology_markers(
        examples[: config.dry_run.preview_rows],
        config,
    )

    return TrainingDryRunPlan(
        config_path=config.path,
        segments_path=config.data.segments_path,
        glossary_path=config.data.glossary_path,
        base_model=config.model.base_model,
        output_dir=config.model.output_dir,
        source_code=config.language.source_code,
        target_code=config.language.target_code,
        terminology_markers=config.tokenization.terminology_markers,
        terminology_marker_scope="preview_only" if config.tokenization.terminology_markers else "disabled",
        total_rows=len(examples),
        train_rows=len(train_examples),
        validation_rows=len(validation_examples),
        preview_examples=preview_examples,
    )


def build_training_smoke_test(
    config: TrainingConfig,
    tokenizer: Any,
    tokenizer_name: str,
    sample_rows: int | None = None,
) -> TrainingSmokeTestPlan:
    row_limit = sample_rows if sample_rows is not None else config.dry_run.preview_rows
    prepared_examples = prepare_training_examples(config, limit=row_limit)
    language_assignments = configure_tokenizer_language_codes(tokenizer, config)
    tokenized_examples = tokenize_training_examples(config, tokenizer, prepared_examples)

    return TrainingSmokeTestPlan(
        config_path=config.path,
        segments_path=config.data.segments_path,
        glossary_path=config.data.glossary_path,
        tokenizer_name=tokenizer_name,
        source_code=config.language.source_code,
        target_code=config.language.target_code,
        max_length=config.tokenization.max_length,
        padding=config.tokenization.padding,
        truncation=config.tokenization.truncation,
        terminology_markers=config.tokenization.terminology_markers,
        terminology_marker_scope="prepared_examples"
        if config.tokenization.terminology_markers
        else "disabled",
        prepared_rows=len(prepared_examples),
        tokenized_rows=len(tokenized_examples),
        language_code_assignments=language_assignments,
        preview_examples=prepared_examples[: config.dry_run.preview_rows],
        tokenized_examples=tokenized_examples[: config.dry_run.preview_rows],
    )


def read_training_examples(config: TrainingConfig) -> list[TrainingExample]:
    return read_segment_examples(
        config.data.segments_path,
        config.data.id_column,
        config.data.source_column,
        config.data.target_column,
    )


def read_segment_examples(
    path: str | Path,
    id_column: str,
    source_column: str,
    target_column: str,
) -> list[TrainingExample]:
    segment_path = Path(path)
    examples: list[TrainingExample] = []

    with segment_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        require_columns(segment_path, reader.fieldnames, [id_column, source_column, target_column])
        for row_number, row in enumerate(reader, start=2):
            segment_id = row.get(id_column, "").strip()
            source_text = row.get(source_column, "").strip()
            target_text = row.get(target_column, "").strip()
            if not segment_id or not source_text or not target_text:
                raise ValueError(f"Empty training value at {segment_path}:{row_number}")
            examples.append(TrainingExample(segment_id, source_text, target_text))

    if not examples:
        raise ValueError(f"No training examples found: {segment_path}")

    return examples


def prepare_training_examples(
    config: TrainingConfig,
    limit: int | None = None,
) -> list[TrainingExample]:
    examples = read_training_examples(config)
    if limit is not None:
        if limit <= 0:
            raise ValueError("limit must be a positive integer")
        examples = examples[:limit]
    return apply_optional_terminology_markers(examples, config)


def apply_optional_terminology_markers(
    examples: Sequence[TrainingExample],
    config: TrainingConfig,
) -> list[TrainingExample]:
    if not config.tokenization.terminology_markers:
        return list(examples)

    terms = load_glossary_terms(config.data.glossary_path)
    marked_examples: list[TrainingExample] = []
    for example in examples:
        protected = protect_training_pair(example.source_text, example.target_text, terms)
        marked_examples.append(
            TrainingExample(
                segment_id=example.segment_id,
                source_text=protected.source_text,
                target_text=protected.target_text,
            )
        )
    return marked_examples


def configure_tokenizer_language_codes(tokenizer: Any, config: TrainingConfig) -> list[str]:
    assignments: list[str] = []
    for attribute, value in (
        ("src_lang", config.language.source_code),
        ("tgt_lang", config.language.target_code),
    ):
        try:
            setattr(tokenizer, attribute, value)
        except Exception:
            continue
        assignments.append(f"{attribute}={value}")
    return assignments


def tokenize_training_examples(
    config: TrainingConfig,
    tokenizer: Any,
    examples: Sequence[TrainingExample],
) -> list[TokenizedTrainingExample]:
    if not examples:
        raise ValueError("No training examples to tokenize")

    source_batch = tokenize_texts(
        tokenizer,
        [example.source_text for example in examples],
        config,
    )
    target_batch = tokenize_texts(
        tokenizer,
        [example.target_text for example in examples],
        config,
    )

    input_ids = batch_list(source_batch, "input_ids")
    attention_mask = batch_list(source_batch, "attention_mask")
    labels = batch_list(target_batch, "input_ids")
    if not (len(input_ids) == len(attention_mask) == len(labels) == len(examples)):
        raise ValueError("Tokenizer returned inconsistent batch sizes")

    tokenized: list[TokenizedTrainingExample] = []
    for example, ids, mask, label_ids in zip(examples, input_ids, attention_mask, labels):
        tokenized.append(
            TokenizedTrainingExample(
                segment_id=example.segment_id,
                input_ids=ids,
                attention_mask=mask,
                labels=label_ids,
            )
        )
    return tokenized


def tokenize_texts(tokenizer: Any, texts: Sequence[str], config: TrainingConfig) -> Any:
    return tokenizer(
        list(texts),
        max_length=config.tokenization.max_length,
        padding=config.tokenization.padding,
        truncation=config.tokenization.truncation,
    )


def batch_list(batch: Any, field: str) -> list[list[int]]:
    if field not in batch:
        raise ValueError(f"Tokenizer output is missing '{field}'")
    value = batch[field]
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, list):
        raise ValueError(f"Tokenizer output field '{field}' must be a list")
    return [list(item) for item in value]


def split_examples(
    examples: Sequence[TrainingExample],
    validation_ratio: float,
    seed: int,
) -> tuple[list[TrainingExample], list[TrainingExample]]:
    shuffled = list(examples)
    random.Random(seed).shuffle(shuffled)

    if not shuffled or validation_ratio == 0:
        return shuffled, []

    validation_count = max(1, int(len(shuffled) * validation_ratio))
    validation_count = min(validation_count, len(shuffled) - 1)
    validation_examples = shuffled[:validation_count]
    train_examples = shuffled[validation_count:]
    return train_examples, validation_examples


def require_columns(path: Path, fieldnames: Sequence[str] | None, columns: Sequence[str]) -> None:
    missing = [column for column in columns if column not in (fieldnames or [])]
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")


def format_training_dry_run(plan: TrainingDryRunPlan) -> str:
    lines = [
        "Training dry-run plan",
        f"config={plan.config_path}",
        f"segments={plan.segments_path}",
        f"glossary={plan.glossary_path}",
        f"base_model={plan.base_model}",
        f"output_dir={plan.output_dir}",
        f"language_pair={plan.source_code}->{plan.target_code}",
        f"terminology_markers={plan.terminology_markers}",
        f"terminology_marker_scope={plan.terminology_marker_scope}",
        f"total_rows={plan.total_rows}",
        f"train_rows={plan.train_rows}",
        f"validation_rows={plan.validation_rows}",
    ]
    for index, example in enumerate(plan.preview_examples, start=1):
        lines.append(
            f"preview_{index}={example.segment_id}: "
            f"{example.source_text} => {example.target_text}"
        )
    return "\n".join(lines)


def format_training_smoke_test(plan: TrainingSmokeTestPlan) -> str:
    lines = [
        "Training tokenizer smoke-test plan",
        f"config={plan.config_path}",
        f"segments={plan.segments_path}",
        f"glossary={plan.glossary_path}",
        f"tokenizer={plan.tokenizer_name}",
        f"language_pair={plan.source_code}->{plan.target_code}",
        f"max_length={plan.max_length}",
        f"padding={plan.padding}",
        f"truncation={plan.truncation}",
        f"terminology_markers={plan.terminology_markers}",
        f"terminology_marker_scope={plan.terminology_marker_scope}",
        f"prepared_rows={plan.prepared_rows}",
        f"tokenized_rows={plan.tokenized_rows}",
        f"language_code_assignments={';'.join(plan.language_code_assignments)}",
    ]
    for index, example in enumerate(plan.preview_examples, start=1):
        lines.append(
            f"prepared_preview_{index}={example.segment_id}: "
            f"{example.source_text} => {example.target_text}"
        )
    for index, example in enumerate(plan.tokenized_examples, start=1):
        lines.append(
            f"tokenized_preview_{index}={example.segment_id}: "
            f"input_ids={len(example.input_ids)} labels={len(example.labels)}"
        )
    return "\n".join(lines)
