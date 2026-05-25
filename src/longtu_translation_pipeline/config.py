"""Config loading for training and inference entry points.

The RF-006 phase 1 entry points intentionally validate JSON configs without
importing model libraries. Real model loading is deferred to a later phase.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class TrainingDataConfig:
    segments_path: Path
    glossary_path: Path
    source_column: str
    target_column: str
    id_column: str


@dataclass(frozen=True)
class LanguageConfig:
    source_code: str
    target_code: str


@dataclass(frozen=True)
class TrainingModelConfig:
    base_model: str
    output_dir: Path


@dataclass(frozen=True)
class SplitConfig:
    validation_ratio: float
    seed: int


@dataclass(frozen=True)
class TokenizationConfig:
    max_length: int
    padding: str
    truncation: bool
    terminology_markers: bool


@dataclass(frozen=True)
class TrainingArgumentsConfig:
    num_train_epochs: float
    per_device_train_batch_size: int
    per_device_eval_batch_size: int


@dataclass(frozen=True)
class DryRunConfig:
    preview_rows: int


@dataclass(frozen=True)
class TrainingConfig:
    path: Path
    data: TrainingDataConfig
    language: LanguageConfig
    model: TrainingModelConfig
    split: SplitConfig
    tokenization: TokenizationConfig
    training: TrainingArgumentsConfig
    dry_run: DryRunConfig


@dataclass(frozen=True)
class InferenceInputConfig:
    path: Path
    text_column: str
    reference_column: str
    id_column: str


@dataclass(frozen=True)
class InferenceModelConfig:
    path: Path
    tokenizer_name: str


@dataclass(frozen=True)
class InferenceOutputConfig:
    path: Path
    strip_glossary_markers: bool


@dataclass(frozen=True)
class GenerationConfig:
    batch_size: int
    max_length: int


@dataclass(frozen=True)
class InferenceConfig:
    path: Path
    input: InferenceInputConfig
    language: LanguageConfig
    model: InferenceModelConfig
    output: InferenceOutputConfig
    generation: GenerationConfig
    dry_run: DryRunConfig


@dataclass(frozen=True)
class EvaluationInputConfig:
    path: Path
    source_column: str
    reference_column: str
    candidate_column: str


@dataclass(frozen=True)
class EvaluationGlossaryConfig:
    path: Path
    source_column: str
    target_column: str


@dataclass(frozen=True)
class BleuConfig:
    tokenization: str
    max_order: int
    smooth_value: float


@dataclass(frozen=True)
class EvaluationOutputConfig:
    report_dir: Path
    write_reports: bool


@dataclass(frozen=True)
class EvaluationConfig:
    path: Path
    input: EvaluationInputConfig
    glossary: EvaluationGlossaryConfig
    bleu: BleuConfig
    output: EvaluationOutputConfig


def load_training_config(path: str | Path, base_dir: str | Path | None = None) -> TrainingConfig:
    config_path = Path(path)
    path_base = Path(base_dir) if base_dir is not None else config_path.parent
    data = read_json_object(config_path)

    data_section = require_mapping(data, "data", config_path)
    language_section = require_mapping(data, "language", config_path)
    model_section = require_mapping(data, "model", config_path)
    split_section = require_mapping(data, "split", config_path)
    tokenization_section = require_mapping(data, "tokenization", config_path)
    training_section = require_mapping(data, "training", config_path)
    dry_run_section = require_mapping(data, "dry_run", config_path)

    validation_ratio = require_float(split_section, "validation_ratio", config_path)
    if not 0 <= validation_ratio < 1:
        raise ValueError(f"split.validation_ratio must be >= 0 and < 1: {config_path}")

    return TrainingConfig(
        path=config_path,
        data=TrainingDataConfig(
            segments_path=resolve_config_path(
                require_str(data_section, "segments_path", config_path),
                path_base,
            ),
            glossary_path=resolve_config_path(
                require_str(data_section, "glossary_path", config_path),
                path_base,
            ),
            source_column=require_str(data_section, "source_column", config_path),
            target_column=require_str(data_section, "target_column", config_path),
            id_column=require_str(data_section, "id_column", config_path),
        ),
        language=load_language_config(language_section, config_path),
        model=TrainingModelConfig(
            base_model=require_str(model_section, "base_model", config_path),
            output_dir=resolve_config_path(
                require_str(model_section, "output_dir", config_path),
                path_base,
            ),
        ),
        split=SplitConfig(
            validation_ratio=validation_ratio,
            seed=require_int(split_section, "seed", config_path),
        ),
        tokenization=TokenizationConfig(
            max_length=require_positive_int(tokenization_section, "max_length", config_path),
            padding=require_str(tokenization_section, "padding", config_path),
            truncation=require_bool(tokenization_section, "truncation", config_path),
            terminology_markers=require_bool(tokenization_section, "terminology_markers", config_path),
        ),
        training=TrainingArgumentsConfig(
            num_train_epochs=require_positive_float(training_section, "num_train_epochs", config_path),
            per_device_train_batch_size=require_positive_int(
                training_section,
                "per_device_train_batch_size",
                config_path,
            ),
            per_device_eval_batch_size=require_positive_int(
                training_section,
                "per_device_eval_batch_size",
                config_path,
            ),
        ),
        dry_run=DryRunConfig(
            preview_rows=require_non_negative_int(dry_run_section, "preview_rows", config_path),
        ),
    )


def load_inference_config(path: str | Path, base_dir: str | Path | None = None) -> InferenceConfig:
    config_path = Path(path)
    path_base = Path(base_dir) if base_dir is not None else config_path.parent
    data = read_json_object(config_path)

    input_section = require_mapping(data, "input", config_path)
    language_section = require_mapping(data, "language", config_path)
    model_section = require_mapping(data, "model", config_path)
    output_section = require_mapping(data, "output", config_path)
    generation_section = require_mapping(data, "generation", config_path)
    dry_run_section = require_mapping(data, "dry_run", config_path)

    return InferenceConfig(
        path=config_path,
        input=InferenceInputConfig(
            path=resolve_config_path(require_str(input_section, "path", config_path), path_base),
            text_column=require_str(input_section, "text_column", config_path),
            reference_column=require_str(input_section, "reference_column", config_path),
            id_column=require_str(input_section, "id_column", config_path),
        ),
        language=load_language_config(language_section, config_path),
        model=InferenceModelConfig(
            path=resolve_config_path(require_str(model_section, "path", config_path), path_base),
            tokenizer_name=require_str(model_section, "tokenizer_name", config_path),
        ),
        output=InferenceOutputConfig(
            path=resolve_config_path(require_str(output_section, "path", config_path), path_base),
            strip_glossary_markers=require_bool(output_section, "strip_glossary_markers", config_path),
        ),
        generation=GenerationConfig(
            batch_size=require_positive_int(generation_section, "batch_size", config_path),
            max_length=require_positive_int(generation_section, "max_length", config_path),
        ),
        dry_run=DryRunConfig(
            preview_rows=require_non_negative_int(dry_run_section, "preview_rows", config_path),
        ),
    )


def load_evaluation_config(path: str | Path, base_dir: str | Path | None = None) -> EvaluationConfig:
    config_path = Path(path)
    path_base = Path(base_dir) if base_dir is not None else config_path.parent
    data = read_json_object(config_path)

    input_section = require_mapping(data, "input", config_path)
    glossary_section = require_mapping(data, "glossary", config_path)
    bleu_section = require_mapping(data, "bleu", config_path)
    output_section = require_mapping(data, "output", config_path)

    tokenization = require_str(bleu_section, "tokenization", config_path)
    if tokenization not in {"whitespace", "char"}:
        raise ValueError(f"bleu.tokenization must be 'whitespace' or 'char': {config_path}")

    return EvaluationConfig(
        path=config_path,
        input=EvaluationInputConfig(
            path=resolve_config_path(require_str(input_section, "path", config_path), path_base),
            source_column=require_str(input_section, "source_column", config_path),
            reference_column=require_str(input_section, "reference_column", config_path),
            candidate_column=require_str(input_section, "candidate_column", config_path),
        ),
        glossary=EvaluationGlossaryConfig(
            path=resolve_config_path(require_str(glossary_section, "path", config_path), path_base),
            source_column=require_str(glossary_section, "source_column", config_path),
            target_column=require_str(glossary_section, "target_column", config_path),
        ),
        bleu=BleuConfig(
            tokenization=tokenization,
            max_order=require_positive_int(bleu_section, "max_order", config_path),
            smooth_value=require_positive_float(bleu_section, "smooth_value", config_path),
        ),
        output=EvaluationOutputConfig(
            report_dir=resolve_config_path(require_str(output_section, "report_dir", config_path), path_base),
            write_reports=require_bool(output_section, "write_reports", config_path),
        ),
    )


def read_json_object(path: Path) -> JsonObject:
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a JSON object: {path}")
    return data


def load_language_config(data: JsonObject, path: Path) -> LanguageConfig:
    return LanguageConfig(
        source_code=require_str(data, "source_code", path),
        target_code=require_str(data, "target_code", path),
    )


def resolve_config_path(value: str, base_dir: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base_dir / path


def require_mapping(data: JsonObject, key: str, path: Path) -> JsonObject:
    value = require_key(data, key, path)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object: {path}")
    return value


def require_key(data: JsonObject, key: str, path: Path) -> Any:
    if key not in data:
        raise ValueError(f"Missing required config key '{key}': {path}")
    return data[key]


def require_str(data: JsonObject, key: str, path: Path) -> str:
    value = require_key(data, key, path)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string: {path}")
    return value


def require_bool(data: JsonObject, key: str, path: Path) -> bool:
    value = require_key(data, key, path)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean: {path}")
    return value


def require_int(data: JsonObject, key: str, path: Path) -> int:
    value = require_key(data, key, path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer: {path}")
    return value


def require_float(data: JsonObject, key: str, path: Path) -> float:
    value = require_key(data, key, path)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number: {path}")
    return float(value)


def require_positive_int(data: JsonObject, key: str, path: Path) -> int:
    value = require_int(data, key, path)
    if value <= 0:
        raise ValueError(f"{key} must be a positive integer: {path}")
    return value


def require_non_negative_int(data: JsonObject, key: str, path: Path) -> int:
    value = require_int(data, key, path)
    if value < 0:
        raise ValueError(f"{key} must be a non-negative integer: {path}")
    return value


def require_positive_float(data: JsonObject, key: str, path: Path) -> float:
    value = require_float(data, key, path)
    if value <= 0:
        raise ValueError(f"{key} must be a positive number: {path}")
    return value
