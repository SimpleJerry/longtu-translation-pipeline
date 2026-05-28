"""Config loading for training and inference entry points.

The RF-006 phase 1 entry points intentionally validate JSON configs without
importing model libraries. Real model loading is deferred to a later phase.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
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
    train_ratio: float
    validation_ratio: float
    test_ratio: float
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
    max_steps: int | None
    per_device_train_batch_size: int
    per_device_eval_batch_size: int
    gradient_accumulation_steps: int
    learning_rate: float | None
    warmup_ratio: float
    weight_decay: float
    max_grad_norm: float | None
    save_steps: int | None
    eval_steps: int | None
    save_total_limit: int | None
    logging_steps: int | None
    load_best_model_at_end: bool = False
    metric_for_best_model: str | None = None
    greater_is_better: bool | None = None
    early_stopping_patience: int | None = None
    early_stopping_threshold: float = 0.0
    lr_scheduler_type: str | None = None


@dataclass(frozen=True)
class MetricsConfig:
    enabled: bool = False
    composite_weight_bleu: float = 0.5
    composite_weight_preservation_nospace: float = 0.5
    predict_with_generate: bool = False
    generation_max_length: int = 400
    generation_num_beams: int = 1
    eval_subset_rows: int | None = None


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
    metrics: MetricsConfig | None = None


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
class InferenceGlossaryConfig:
    path: Path
    source_terminology_markers: bool


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
    glossary: InferenceGlossaryConfig
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
class ChrfConfig:
    enabled: bool
    max_n: int
    beta: float


@dataclass(frozen=True)
class EvaluationConfig:
    path: Path
    input: EvaluationInputConfig
    glossary: EvaluationGlossaryConfig
    bleu: BleuConfig
    output: EvaluationOutputConfig
    chrf: ChrfConfig = field(default_factory=lambda: ChrfConfig(enabled=True, max_n=6, beta=2.0))


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
    metrics_section = data.get("metrics")

    train_ratio = require_float(split_section, "train_ratio", config_path)
    validation_ratio = require_float(split_section, "validation_ratio", config_path)
    test_ratio = require_float(split_section, "test_ratio", config_path)
    validate_split_ratios(train_ratio, validation_ratio, test_ratio, config_path)

    metrics_config: MetricsConfig | None = None
    if metrics_section is not None:
        if not isinstance(metrics_section, dict):
            raise ValueError(f"metrics must be a JSON object: {config_path}")
        metrics_config = load_metrics_config(metrics_section, config_path)

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
            train_ratio=train_ratio,
            validation_ratio=validation_ratio,
            test_ratio=test_ratio,
            seed=require_int(split_section, "seed", config_path),
        ),
        tokenization=TokenizationConfig(
            max_length=require_positive_int(tokenization_section, "max_length", config_path),
            padding=require_str(tokenization_section, "padding", config_path),
            truncation=require_bool(tokenization_section, "truncation", config_path),
            terminology_markers=require_bool(tokenization_section, "terminology_markers", config_path),
        ),
        training=load_training_arguments_config(training_section, config_path),
        dry_run=DryRunConfig(
            preview_rows=require_non_negative_int(dry_run_section, "preview_rows", config_path),
        ),
        metrics=metrics_config,
    )


def load_inference_config(path: str | Path, base_dir: str | Path | None = None) -> InferenceConfig:
    config_path = Path(path)
    path_base = Path(base_dir) if base_dir is not None else config_path.parent
    data = read_json_object(config_path)

    input_section = require_mapping(data, "input", config_path)
    language_section = require_mapping(data, "language", config_path)
    model_section = require_mapping(data, "model", config_path)
    glossary_section = require_mapping(data, "glossary", config_path)
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
        glossary=InferenceGlossaryConfig(
            path=resolve_config_path(require_str(glossary_section, "path", config_path), path_base),
            source_terminology_markers=require_bool(
                glossary_section,
                "source_terminology_markers",
                config_path,
            ),
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
    chrf_section = data.get("chrf")

    tokenization = require_str(bleu_section, "tokenization", config_path)
    if tokenization not in {"whitespace", "char"}:
        raise ValueError(f"bleu.tokenization must be 'whitespace' or 'char': {config_path}")

    chrf_config: ChrfConfig
    if chrf_section is not None:
        if not isinstance(chrf_section, dict):
            raise ValueError(f"chrf must be a JSON object: {config_path}")
        chrf_config = ChrfConfig(
            enabled=optional_bool(chrf_section, "enabled", config_path, default=True),  # type: ignore[arg-type]
            max_n=optional_positive_int(chrf_section, "max_n", config_path, default=6),  # type: ignore[arg-type]
            beta=optional_positive_float(chrf_section, "beta", config_path, default=2.0),  # type: ignore[arg-type]
        )
    else:
        chrf_config = ChrfConfig(enabled=True, max_n=6, beta=2.0)

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
        chrf=chrf_config,
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


def load_training_arguments_config(data: JsonObject, path: Path) -> TrainingArgumentsConfig:
    warmup_ratio = optional_non_negative_float(data, "warmup_ratio", path, default=0.0)
    if warmup_ratio >= 1:
        raise ValueError(f"training.warmup_ratio must be >= 0 and < 1: {path}")

    return TrainingArgumentsConfig(
        num_train_epochs=require_positive_float(data, "num_train_epochs", path),
        max_steps=optional_positive_int(data, "max_steps", path),
        per_device_train_batch_size=require_positive_int(
            data,
            "per_device_train_batch_size",
            path,
        ),
        per_device_eval_batch_size=require_positive_int(
            data,
            "per_device_eval_batch_size",
            path,
        ),
        gradient_accumulation_steps=optional_positive_int(
            data,
            "gradient_accumulation_steps",
            path,
            default=1,
        ),
        learning_rate=optional_positive_float(data, "learning_rate", path),
        warmup_ratio=warmup_ratio,
        weight_decay=optional_non_negative_float(data, "weight_decay", path, default=0.0),
        max_grad_norm=optional_positive_float(data, "max_grad_norm", path),
        save_steps=optional_positive_int(data, "save_steps", path),
        eval_steps=optional_positive_int(data, "eval_steps", path),
        save_total_limit=optional_positive_int(data, "save_total_limit", path),
        logging_steps=optional_positive_int(data, "logging_steps", path),
        load_best_model_at_end=optional_bool(data, "load_best_model_at_end", path, default=False),
        metric_for_best_model=optional_str(data, "metric_for_best_model", path),
        greater_is_better=optional_bool(data, "greater_is_better", path),
        early_stopping_patience=optional_positive_int(data, "early_stopping_patience", path),
        early_stopping_threshold=optional_non_negative_float(
            data, "early_stopping_threshold", path, default=0.0
        ),
        lr_scheduler_type=optional_str(data, "lr_scheduler_type", path),
    )


def load_metrics_config(data: JsonObject, path: Path) -> MetricsConfig:
    weight_bleu = optional_non_negative_float(data, "composite_weight_bleu", path, default=0.5)
    weight_pres = optional_non_negative_float(
        data, "composite_weight_preservation_nospace", path, default=0.5
    )
    if weight_bleu + weight_pres <= 0:
        raise ValueError(
            "composite_weight_bleu + composite_weight_preservation_nospace must be > 0: "
            f"{path}"
        )
    return MetricsConfig(
        enabled=optional_bool(data, "enabled", path, default=False),
        composite_weight_bleu=weight_bleu,
        composite_weight_preservation_nospace=weight_pres,
        predict_with_generate=optional_bool(data, "predict_with_generate", path, default=False),
        generation_max_length=optional_positive_int(data, "generation_max_length", path, default=400),
        generation_num_beams=optional_positive_int(data, "generation_num_beams", path, default=1),
        eval_subset_rows=optional_positive_int(data, "eval_subset_rows", path),
    )


def validate_split_ratios(
    train_ratio: float,
    validation_ratio: float,
    test_ratio: float,
    path: Path,
) -> None:
    ratios = {
        "split.train_ratio": train_ratio,
        "split.validation_ratio": validation_ratio,
        "split.test_ratio": test_ratio,
    }
    for name, value in ratios.items():
        if value < 0 or value >= 1:
            raise ValueError(f"{name} must be >= 0 and < 1: {path}")
    if train_ratio <= 0:
        raise ValueError(f"split.train_ratio must be > 0: {path}")
    if validation_ratio <= 0:
        raise ValueError(f"split.validation_ratio must be > 0: {path}")
    if test_ratio <= 0:
        raise ValueError(f"split.test_ratio must be > 0: {path}")
    total = train_ratio + validation_ratio + test_ratio
    if abs(total - 1.0) > 1e-9:
        raise ValueError(
            "split.train_ratio + split.validation_ratio + split.test_ratio "
            f"must equal 1.0: {path}"
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


def optional_positive_int(
    data: JsonObject,
    key: str,
    path: Path,
    default: int | None = None,
) -> int | None:
    if key not in data:
        return default
    return require_positive_int(data, key, path)


def optional_positive_float(
    data: JsonObject,
    key: str,
    path: Path,
    default: float | None = None,
) -> float | None:
    if key not in data:
        return default
    return require_positive_float(data, key, path)


def optional_bool(
    data: JsonObject,
    key: str,
    path: Path,
    default: bool | None = None,
) -> bool | None:
    if key not in data:
        return default
    return require_bool(data, key, path)


def optional_str(
    data: JsonObject,
    key: str,
    path: Path,
    default: str | None = None,
) -> str | None:
    if key not in data:
        return default
    value = data[key]
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string: {path}")
    return value


def optional_non_negative_float(
    data: JsonObject,
    key: str,
    path: Path,
    default: float = 0.0,
) -> float:
    if key not in data:
        return default
    value = require_float(data, key, path)
    if value < 0:
        raise ValueError(f"{key} must be a non-negative number: {path}")
    return value
