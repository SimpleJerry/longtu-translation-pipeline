"""Training data preparation and smoke-test tokenization helpers."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import random
import subprocess
from datetime import datetime
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
    test_rows: int
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


@dataclass(frozen=True)
class NllbTrainerSmokeResult:
    config_path: Path
    segments_path: Path
    glossary_path: Path
    tokenizer_name: str
    output_dir: Path
    source_code: str
    target_code: str
    target_language_token_id: int
    special_tokens_added: int
    tokenizer_vocab_size: int
    max_length: int
    prepared_rows: int
    tokenized_rows: int
    input_shape: str
    label_shape: str
    trainer_max_steps: int
    train_loss: float | None


@dataclass(frozen=True)
class RealModelSmokeResult:
    config_path: Path
    segments_path: Path
    glossary_path: Path
    model_name: str
    output_dir: Path
    source_code: str
    target_code: str
    target_language_token_id: int
    special_tokens_added: int
    tokenizer_vocab_size: int
    embedding_size_before: int
    embedding_size_after: int
    parameter_count: int
    device: str
    cuda_device_name: str
    cuda_memory_summary: str
    torch_dtype: str
    max_length: int
    prepared_rows: int
    tokenized_rows: int
    input_shape: str
    label_shape: str
    trainer_max_steps: int
    train_loss: float | None


@dataclass(frozen=True)
class RealModelPilotTrainingResult:
    config_path: Path
    segments_path: Path
    glossary_path: Path
    model_name: str
    output_dir: Path
    source_code: str
    target_code: str
    target_language_token_id: int
    special_tokens_added: int
    tokenizer_vocab_size: int
    embedding_size_before: int
    embedding_size_after: int
    parameter_count: int
    device: str
    cuda_device_name: str
    cuda_memory_summary: str
    torch_dtype: str
    max_length: int
    prepared_rows: int
    tokenized_rows: int
    input_shape: str
    label_shape: str
    first_stage_steps: int
    final_max_steps: int
    save_steps: int
    resume_checkpoint: Path
    checkpoint_paths: list[Path]
    first_stage_loss: float | None
    final_train_loss: float | None
    final_global_step: int


@dataclass(frozen=True)
class FormalTrainingRunResult:
    config_path: Path
    segments_path: Path
    glossary_path: Path
    model_name: str
    output_dir: Path
    manifest_path: Path
    train_split_path: Path
    validation_split_path: Path
    test_split_path: Path
    source_code: str
    target_code: str
    target_language_token_id: int
    special_tokens_added: int
    tokenizer_vocab_size: int
    embedding_size_before: int
    embedding_size_after: int
    parameter_count: int
    device: str
    cuda_device_name: str
    cuda_memory_summary: str
    torch_dtype: str
    max_length: int
    total_rows: int
    row_limit: int | None
    segments_sha256: str
    split_seed: int
    train_ratio: float
    validation_ratio: float
    test_ratio: float
    train_rows: int
    validation_rows: int
    test_rows: int
    tokenized_train_rows: int
    tokenized_validation_rows: int
    input_shape: str
    label_shape: str
    max_steps: int
    save_steps: int
    eval_steps: int
    save_total_limit: int
    logging_steps: int
    gradient_accumulation_steps: int
    learning_rate: float | None
    warmup_ratio: float
    weight_decay: float
    max_grad_norm: float | None
    resume_checkpoint: Path | None
    checkpoint_paths: list[Path]
    train_loss: float | None
    eval_loss: float | None
    final_global_step: int


def build_training_dry_run(config: TrainingConfig) -> TrainingDryRunPlan:
    examples = read_training_examples(config)
    train_examples, validation_examples, test_examples = split_examples(
        examples,
        config.split.train_ratio,
        config.split.validation_ratio,
        config.split.test_ratio,
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
        test_rows=len(test_examples),
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


def run_nllb_trainer_smoke_test(
    config: TrainingConfig,
    output_dir: str | Path,
    sample_rows: int = 2,
    max_steps: int = 1,
) -> NllbTrainerSmokeResult:
    if sample_rows <= 0:
        raise ValueError("sample_rows must be a positive integer")
    if max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")

    tokenizer = load_nllb_tokenizer(config)
    special_tokens_added = add_marker_special_tokens(tokenizer)
    target_language_token_id = tokenizer.convert_tokens_to_ids(config.language.target_code)
    if target_language_token_id is None or target_language_token_id < 0:
        raise ValueError(f"Tokenizer does not know target language code: {config.language.target_code}")

    prepared_examples = prepare_training_examples(config, limit=sample_rows)
    tokenized_examples = tokenize_training_examples(config, tokenizer, prepared_examples)
    dataset = TorchTrainingDataset(tokenized_examples)

    from transformers import M2M100Config, M2M100ForConditionalGeneration

    model_config = M2M100Config(
        vocab_size=len(tokenizer),
        decoder_start_token_id=target_language_token_id,
        bos_token_id=tokenizer.bos_token_id,
        eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.pad_token_id,
        d_model=32,
        encoder_layers=1,
        decoder_layers=1,
        encoder_attention_heads=1,
        decoder_attention_heads=1,
        encoder_ffn_dim=64,
        decoder_ffn_dim=64,
        max_position_embeddings=max(config.tokenization.max_length, 32),
    )
    model = M2M100ForConditionalGeneration(model_config)
    model.resize_token_embeddings(len(tokenizer))

    smoke_output_dir = Path(output_dir)
    trainer = build_trainer(
        model=model,
        dataset=dataset,
        output_dir=smoke_output_dir,
        max_steps=max_steps,
        use_cpu=True,
        fp16=False,
    )
    train_result = trainer.train()
    train_loss = train_result.training_loss

    input_shape = shape_text([example.input_ids for example in tokenized_examples])
    label_shape = shape_text([example.labels for example in tokenized_examples])
    return NllbTrainerSmokeResult(
        config_path=config.path,
        segments_path=config.data.segments_path,
        glossary_path=config.data.glossary_path,
        tokenizer_name=config.model.base_model,
        output_dir=smoke_output_dir,
        source_code=config.language.source_code,
        target_code=config.language.target_code,
        target_language_token_id=int(target_language_token_id),
        special_tokens_added=special_tokens_added,
        tokenizer_vocab_size=len(tokenizer),
        max_length=config.tokenization.max_length,
        prepared_rows=len(prepared_examples),
        tokenized_rows=len(tokenized_examples),
        input_shape=input_shape,
        label_shape=label_shape,
        trainer_max_steps=max_steps,
        train_loss=float(train_loss) if train_loss is not None else None,
    )


def run_real_nllb_model_smoke_test(
    config: TrainingConfig,
    output_dir: str | Path,
    sample_rows: int = 2,
    max_steps: int = 1,
    device: str = "auto",
) -> RealModelSmokeResult:
    if sample_rows <= 0:
        raise ValueError("sample_rows must be a positive integer")
    if max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")

    tokenizer = load_nllb_tokenizer(config)
    special_tokens_added = add_marker_special_tokens(tokenizer)
    target_language_token_id = tokenizer.convert_tokens_to_ids(config.language.target_code)
    if target_language_token_id is None or target_language_token_id < 0:
        raise ValueError(f"Tokenizer does not know target language code: {config.language.target_code}")

    prepared_examples = prepare_training_examples(config, limit=sample_rows)
    tokenized_examples = tokenize_training_examples(config, tokenizer, prepared_examples)
    dataset = TorchTrainingDataset(tokenized_examples)

    from transformers import AutoModelForSeq2SeqLM

    smoke_device = resolve_training_device(device)
    torch_dtype = "float32"
    if smoke_device == "cuda":
        torch_dtype = "float32+fp16_trainer"

    model = AutoModelForSeq2SeqLM.from_pretrained(config.model.base_model)
    embedding_size_before = model.get_input_embeddings().num_embeddings
    model.resize_token_embeddings(len(tokenizer))
    embedding_size_after = model.get_input_embeddings().num_embeddings
    parameter_count = sum(parameter.numel() for parameter in model.parameters())

    smoke_output_dir = Path(output_dir)
    trainer = build_trainer(
        model=model,
        dataset=dataset,
        output_dir=smoke_output_dir,
        max_steps=max_steps,
        use_cpu=smoke_device == "cpu",
        fp16=smoke_device == "cuda",
    )
    train_result = trainer.train()
    train_loss = train_result.training_loss

    input_shape = shape_text([example.input_ids for example in tokenized_examples])
    label_shape = shape_text([example.labels for example in tokenized_examples])
    return RealModelSmokeResult(
        config_path=config.path,
        segments_path=config.data.segments_path,
        glossary_path=config.data.glossary_path,
        model_name=config.model.base_model,
        output_dir=smoke_output_dir,
        source_code=config.language.source_code,
        target_code=config.language.target_code,
        target_language_token_id=int(target_language_token_id),
        special_tokens_added=special_tokens_added,
        tokenizer_vocab_size=len(tokenizer),
        embedding_size_before=embedding_size_before,
        embedding_size_after=embedding_size_after,
        parameter_count=parameter_count,
        device=smoke_device,
        cuda_device_name=cuda_device_name(smoke_device),
        cuda_memory_summary=cuda_memory_summary(smoke_device),
        torch_dtype=torch_dtype,
        max_length=config.tokenization.max_length,
        prepared_rows=len(prepared_examples),
        tokenized_rows=len(tokenized_examples),
        input_shape=input_shape,
        label_shape=label_shape,
        trainer_max_steps=max_steps,
        train_loss=float(train_loss) if train_loss is not None else None,
    )


def run_real_nllb_pilot_training(
    config: TrainingConfig,
    output_dir: str | Path | None = None,
    pilot_rows: int = 64,
    max_steps: int = 4,
    save_steps: int = 2,
    device: str = "auto",
) -> RealModelPilotTrainingResult:
    if pilot_rows <= 0:
        raise ValueError("pilot_rows must be a positive integer")
    if max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")
    if save_steps <= 0:
        raise ValueError("save_steps must be a positive integer")
    if save_steps >= max_steps:
        raise ValueError("save_steps must be smaller than max_steps so resume can be verified")

    tokenizer = load_nllb_tokenizer(config)
    special_tokens_added = add_marker_special_tokens(tokenizer)
    target_language_token_id = tokenizer.convert_tokens_to_ids(config.language.target_code)
    if target_language_token_id is None or target_language_token_id < 0:
        raise ValueError(f"Tokenizer does not know target language code: {config.language.target_code}")

    prepared_examples = prepare_training_examples(config, limit=pilot_rows)
    tokenized_examples = tokenize_training_examples(config, tokenizer, prepared_examples)
    dataset = TorchTrainingDataset(tokenized_examples)

    from transformers import AutoModelForSeq2SeqLM

    training_device = resolve_training_device(device)
    precision_mode = resolve_trainer_precision(training_device)
    torch_dtype = "float32"
    if precision_mode != "fp32":
        torch_dtype = f"float32+{precision_mode}_trainer"

    model = AutoModelForSeq2SeqLM.from_pretrained(config.model.base_model)
    embedding_size_before = model.get_input_embeddings().num_embeddings
    model.resize_token_embeddings(len(tokenizer))
    embedding_size_after = model.get_input_embeddings().num_embeddings
    parameter_count = sum(parameter.numel() for parameter in model.parameters())

    pilot_output_dir = resolve_pilot_output_dir(config, output_dir)
    pilot_output_dir.mkdir(parents=True, exist_ok=False)

    first_trainer = build_trainer(
        model=model,
        dataset=dataset,
        output_dir=pilot_output_dir,
        max_steps=max_steps,
        use_cpu=training_device == "cpu",
        fp16=precision_mode == "fp16",
        bf16=precision_mode == "bf16",
        save_strategy="steps",
        save_steps=save_steps,
        save_total_limit=2,
        logging_strategy="steps",
        logging_steps=1,
        stop_after_steps=save_steps,
    )
    first_result = first_trainer.train()
    resume_checkpoint = find_latest_checkpoint(pilot_output_dir)
    if resume_checkpoint is None:
        raise RuntimeError(f"No checkpoint was created in {pilot_output_dir}")

    second_trainer = build_trainer(
        model=model,
        dataset=dataset,
        output_dir=pilot_output_dir,
        max_steps=max_steps,
        use_cpu=training_device == "cpu",
        fp16=precision_mode == "fp16",
        bf16=precision_mode == "bf16",
        save_strategy="steps",
        save_steps=save_steps,
        save_total_limit=2,
        logging_strategy="steps",
        logging_steps=1,
    )
    final_result = second_trainer.train(resume_from_checkpoint=str(resume_checkpoint))

    input_shape = shape_text([example.input_ids for example in tokenized_examples])
    label_shape = shape_text([example.labels for example in tokenized_examples])
    return RealModelPilotTrainingResult(
        config_path=config.path,
        segments_path=config.data.segments_path,
        glossary_path=config.data.glossary_path,
        model_name=config.model.base_model,
        output_dir=pilot_output_dir,
        source_code=config.language.source_code,
        target_code=config.language.target_code,
        target_language_token_id=int(target_language_token_id),
        special_tokens_added=special_tokens_added,
        tokenizer_vocab_size=len(tokenizer),
        embedding_size_before=embedding_size_before,
        embedding_size_after=embedding_size_after,
        parameter_count=parameter_count,
        device=training_device,
        cuda_device_name=cuda_device_name(training_device),
        cuda_memory_summary=cuda_memory_summary(training_device),
        torch_dtype=torch_dtype,
        max_length=config.tokenization.max_length,
        prepared_rows=len(prepared_examples),
        tokenized_rows=len(tokenized_examples),
        input_shape=input_shape,
        label_shape=label_shape,
        first_stage_steps=save_steps,
        final_max_steps=max_steps,
        save_steps=save_steps,
        resume_checkpoint=resume_checkpoint,
        checkpoint_paths=list_checkpoint_paths(pilot_output_dir),
        first_stage_loss=float(first_result.training_loss)
        if first_result.training_loss is not None
        else None,
        final_train_loss=float(final_result.training_loss)
        if final_result.training_loss is not None
        else None,
        final_global_step=int(second_trainer.state.global_step),
    )


def run_real_nllb_formal_training(
    config: TrainingConfig,
    run_dir: str | Path | None = None,
    run_name: str | None = None,
    row_limit: int | None = None,
    max_steps: int | None = None,
    save_steps: int | None = None,
    eval_steps: int | None = None,
    save_total_limit: int | None = None,
    logging_steps: int | None = None,
    gradient_accumulation_steps: int | None = None,
    learning_rate: float | None = None,
    warmup_ratio: float | None = None,
    weight_decay: float | None = None,
    max_grad_norm: float | None = None,
    device: str = "auto",
    resume_from_checkpoint: str | Path | None = None,
    command: Sequence[str] | None = None,
    repo_root: str | Path | None = None,
) -> FormalTrainingRunResult:
    resolved_max_steps = resolve_required_positive_int(
        "max_steps",
        max_steps,
        config.training.max_steps,
    )
    resolved_save_steps = resolve_positive_int(
        "save_steps",
        save_steps,
        config.training.save_steps,
        default=500,
    )
    resolved_eval_steps = resolve_positive_int(
        "eval_steps",
        eval_steps,
        config.training.eval_steps,
        default=resolved_save_steps,
    )
    resolved_save_total_limit = resolve_positive_int(
        "save_total_limit",
        save_total_limit,
        config.training.save_total_limit,
        default=2,
    )
    resolved_logging_steps = resolve_positive_int(
        "logging_steps",
        logging_steps,
        config.training.logging_steps,
        default=50,
    )
    resolved_gradient_accumulation_steps = resolve_positive_int(
        "gradient_accumulation_steps",
        gradient_accumulation_steps,
        config.training.gradient_accumulation_steps,
        default=1,
    )
    resolved_learning_rate = resolve_positive_float(
        "learning_rate",
        learning_rate,
        config.training.learning_rate,
    )
    resolved_warmup_ratio = resolve_non_negative_float(
        "warmup_ratio",
        warmup_ratio,
        config.training.warmup_ratio,
        default=0.0,
    )
    if resolved_warmup_ratio >= 1:
        raise ValueError("warmup_ratio must be >= 0 and < 1")
    resolved_weight_decay = resolve_non_negative_float(
        "weight_decay",
        weight_decay,
        config.training.weight_decay,
        default=0.0,
    )
    resolved_max_grad_norm = resolve_positive_float(
        "max_grad_norm",
        max_grad_norm,
        config.training.max_grad_norm,
    )

    if row_limit is not None and row_limit <= 0:
        raise ValueError("row_limit must be a positive integer when provided")

    output_dir = resolve_formal_run_dir(config, run_dir=run_dir, run_name=run_name)
    resolved_resume_checkpoint = resolve_resume_checkpoint(output_dir, resume_from_checkpoint)
    if resolved_resume_checkpoint is not None:
        resume_step = checkpoint_step(resolved_resume_checkpoint)
        if resume_step is not None and resume_step >= resolved_max_steps:
            raise ValueError(
                "resume checkpoint step must be smaller than max_steps: "
                f"{resolved_resume_checkpoint} >= {resolved_max_steps}"
            )
    if resolved_resume_checkpoint is not None:
        manifest_row_limit = read_manifest_row_limit(output_dir)
        row_limit = resolve_resume_row_limit(row_limit, manifest_row_limit)

    all_examples = read_training_examples(config)
    selected_examples = all_examples[:row_limit] if row_limit is not None else all_examples
    if len(selected_examples) < 3:
        raise ValueError(
            "Formal training requires at least three selected rows for train/validation/test split"
        )

    train_examples, validation_examples, test_examples = split_examples(
        selected_examples,
        config.split.train_ratio,
        config.split.validation_ratio,
        config.split.test_ratio,
        config.split.seed,
    )
    if not validation_examples:
        raise ValueError("Formal training requires a non-empty validation split")
    if not test_examples:
        raise ValueError("Formal training requires a non-empty test split")

    prepare_run_output_dir(output_dir, resume=resolved_resume_checkpoint is not None)
    train_split_path, validation_split_path, test_split_path = write_split_artifacts(
        output_dir,
        train_examples,
        validation_examples,
        test_examples,
        id_column=config.data.id_column,
        source_column=config.data.source_column,
        target_column=config.data.target_column,
    )

    tokenizer = load_nllb_tokenizer(config)
    special_tokens_added = add_marker_special_tokens(tokenizer)
    target_language_token_id = tokenizer.convert_tokens_to_ids(config.language.target_code)
    if target_language_token_id is None or target_language_token_id < 0:
        raise ValueError(f"Tokenizer does not know target language code: {config.language.target_code}")

    marked_train_examples = apply_optional_terminology_markers(train_examples, config)
    marked_validation_examples = apply_optional_terminology_markers(validation_examples, config)
    tokenized_train_examples = tokenize_training_examples(config, tokenizer, marked_train_examples)
    tokenized_validation_examples = tokenize_training_examples(config, tokenizer, marked_validation_examples)
    train_dataset = TorchTrainingDataset(tokenized_train_examples)
    validation_dataset = TorchTrainingDataset(tokenized_validation_examples)

    from transformers import AutoModelForSeq2SeqLM

    training_device = resolve_training_device(device)
    precision_mode = resolve_trainer_precision(training_device)
    torch_dtype = "float32"
    if precision_mode != "fp32":
        torch_dtype = f"float32+{precision_mode}_trainer"

    model = AutoModelForSeq2SeqLM.from_pretrained(config.model.base_model)
    embedding_size_before = model.get_input_embeddings().num_embeddings
    model.resize_token_embeddings(len(tokenizer))
    embedding_size_after = model.get_input_embeddings().num_embeddings
    parameter_count = sum(parameter.numel() for parameter in model.parameters())

    trainer = build_trainer(
        model=model,
        dataset=train_dataset,
        output_dir=output_dir,
        max_steps=resolved_max_steps,
        use_cpu=training_device == "cpu",
        fp16=precision_mode == "fp16",
        bf16=precision_mode == "bf16",
        save_strategy="steps",
        save_steps=resolved_save_steps,
        save_total_limit=resolved_save_total_limit,
        logging_strategy="steps",
        logging_steps=resolved_logging_steps,
        eval_dataset=validation_dataset,
        eval_strategy="steps",
        eval_steps=resolved_eval_steps,
        per_device_train_batch_size=config.training.per_device_train_batch_size,
        per_device_eval_batch_size=config.training.per_device_eval_batch_size,
        gradient_accumulation_steps=resolved_gradient_accumulation_steps,
        learning_rate=resolved_learning_rate,
        warmup_ratio=resolved_warmup_ratio,
        weight_decay=resolved_weight_decay,
        max_grad_norm=resolved_max_grad_norm,
    )
    train_result = trainer.train(
        resume_from_checkpoint=str(resolved_resume_checkpoint)
        if resolved_resume_checkpoint is not None
        else None
    )
    eval_loss = find_last_log_value(trainer.state.log_history, "eval_loss")

    checkpoint_paths = list_checkpoint_paths(output_dir)
    input_shape = shape_text([example.input_ids for example in tokenized_train_examples])
    label_shape = shape_text([example.labels for example in tokenized_train_examples])
    manifest_path = output_dir / "run_manifest.json"
    result = FormalTrainingRunResult(
        config_path=config.path,
        segments_path=config.data.segments_path,
        glossary_path=config.data.glossary_path,
        model_name=config.model.base_model,
        output_dir=output_dir,
        manifest_path=manifest_path,
        train_split_path=train_split_path,
        validation_split_path=validation_split_path,
        test_split_path=test_split_path,
        source_code=config.language.source_code,
        target_code=config.language.target_code,
        target_language_token_id=int(target_language_token_id),
        special_tokens_added=special_tokens_added,
        tokenizer_vocab_size=len(tokenizer),
        embedding_size_before=embedding_size_before,
        embedding_size_after=embedding_size_after,
        parameter_count=parameter_count,
        device=training_device,
        cuda_device_name=cuda_device_name(training_device),
        cuda_memory_summary=cuda_memory_summary(training_device),
        torch_dtype=torch_dtype,
        max_length=config.tokenization.max_length,
        total_rows=len(all_examples),
        row_limit=row_limit,
        segments_sha256=hash_file(config.data.segments_path),
        split_seed=config.split.seed,
        train_ratio=config.split.train_ratio,
        validation_ratio=config.split.validation_ratio,
        test_ratio=config.split.test_ratio,
        train_rows=len(train_examples),
        validation_rows=len(validation_examples),
        test_rows=len(test_examples),
        tokenized_train_rows=len(tokenized_train_examples),
        tokenized_validation_rows=len(tokenized_validation_examples),
        input_shape=input_shape,
        label_shape=label_shape,
        max_steps=resolved_max_steps,
        save_steps=resolved_save_steps,
        eval_steps=resolved_eval_steps,
        save_total_limit=resolved_save_total_limit,
        logging_steps=resolved_logging_steps,
        gradient_accumulation_steps=resolved_gradient_accumulation_steps,
        learning_rate=resolved_learning_rate,
        warmup_ratio=resolved_warmup_ratio,
        weight_decay=resolved_weight_decay,
        max_grad_norm=resolved_max_grad_norm,
        resume_checkpoint=resolved_resume_checkpoint,
        checkpoint_paths=checkpoint_paths,
        train_loss=float(train_result.training_loss)
        if train_result.training_loss is not None
        else None,
        eval_loss=eval_loss,
        final_global_step=int(trainer.state.global_step),
    )
    write_run_manifest(
        result,
        command=command,
        repo_root=Path(repo_root) if repo_root is not None else None,
    )
    return result


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


def load_nllb_tokenizer(config: TrainingConfig) -> Any:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(config.model.base_model)
    configure_tokenizer_language_codes(tokenizer, config)
    return tokenizer


def add_marker_special_tokens(tokenizer: Any) -> int:
    marker_tokens = {"additional_special_tokens": ["<start>", "<end>"]}
    try:
        return tokenizer.add_special_tokens(
            marker_tokens,
            replace_additional_special_tokens=False,
        )
    except TypeError:
        return tokenizer.add_special_tokens(
            marker_tokens,
            replace_extra_special_tokens=False,
        )


def tokenize_training_examples(
    config: TrainingConfig,
    tokenizer: Any,
    examples: Sequence[TrainingExample],
) -> list[TokenizedTrainingExample]:
    if not examples:
        raise ValueError("No training examples to tokenize")

    source_texts = [example.source_text for example in examples]
    target_texts = [example.target_text for example in examples]
    source_batch = tokenize_source_target_texts(
        tokenizer,
        source_texts,
        target_texts,
        config,
    )
    input_ids = batch_list(source_batch, "input_ids")
    attention_mask = batch_list(source_batch, "attention_mask")
    if "labels" in source_batch:
        labels = batch_list(source_batch, "labels")
    else:
        target_batch = tokenize_texts(tokenizer, target_texts, config)
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


def tokenize_source_target_texts(
    tokenizer: Any,
    source_texts: Sequence[str],
    target_texts: Sequence[str],
    config: TrainingConfig,
) -> Any:
    try:
        return tokenizer(
            list(source_texts),
            text_target=list(target_texts),
            max_length=config.tokenization.max_length,
            padding=config.tokenization.padding,
            truncation=config.tokenization.truncation,
        )
    except TypeError:
        return tokenize_texts(tokenizer, source_texts, config)


def batch_list(batch: Any, field: str) -> list[list[int]]:
    if field not in batch:
        raise ValueError(f"Tokenizer output is missing '{field}'")
    value = batch[field]
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, list):
        raise ValueError(f"Tokenizer output field '{field}' must be a list")
    return [list(item) for item in value]


def build_trainer(
    model: Any,
    dataset: Any,
    output_dir: Path,
    max_steps: int,
    use_cpu: bool,
    fp16: bool,
    bf16: bool = False,
    save_strategy: str = "no",
    save_steps: int | None = None,
    save_total_limit: int | None = None,
    logging_strategy: str = "no",
    logging_steps: int | None = None,
    stop_after_steps: int | None = None,
    eval_dataset: Any | None = None,
    eval_strategy: str = "no",
    eval_steps: int | None = None,
    per_device_train_batch_size: int = 1,
    per_device_eval_batch_size: int = 1,
    gradient_accumulation_steps: int = 1,
    learning_rate: float | None = None,
    warmup_ratio: float = 0.0,
    weight_decay: float = 0.0,
    max_grad_norm: float | None = None,
) -> Any:
    from transformers import Trainer, TrainerCallback, TrainingArguments

    training_kwargs: dict[str, Any] = {
        "output_dir": str(output_dir),
        "max_steps": max_steps,
        "per_device_train_batch_size": per_device_train_batch_size,
        "per_device_eval_batch_size": per_device_eval_batch_size,
        "gradient_accumulation_steps": gradient_accumulation_steps,
        "warmup_ratio": warmup_ratio,
        "weight_decay": weight_decay,
        "report_to": "none",
        "save_strategy": save_strategy,
        "logging_strategy": logging_strategy,
        "disable_tqdm": True,
        "do_train": True,
        "optim": "adamw_torch",
        "use_cpu": use_cpu,
        "fp16": fp16,
        "bf16": bf16,
        "remove_unused_columns": False,
    }
    if save_steps is not None:
        training_kwargs["save_steps"] = save_steps
    if save_total_limit is not None:
        training_kwargs["save_total_limit"] = save_total_limit
    if logging_steps is not None:
        training_kwargs["logging_steps"] = logging_steps
    if learning_rate is not None:
        training_kwargs["learning_rate"] = learning_rate
    if max_grad_norm is not None:
        training_kwargs["max_grad_norm"] = max_grad_norm
    if eval_dataset is not None and eval_strategy != "no":
        training_kwargs["do_eval"] = True
        training_kwargs["eval_strategy"] = eval_strategy
    if eval_steps is not None:
        training_kwargs["eval_steps"] = eval_steps

    callbacks = []
    if stop_after_steps is not None:
        if stop_after_steps <= 0:
            raise ValueError("stop_after_steps must be a positive integer")

        class StopAfterStepCallback(TrainerCallback):
            def on_step_end(self, args: Any, state: Any, control: Any, **kwargs: Any) -> Any:
                if state.global_step >= stop_after_steps:
                    control.should_save = True
                    control.should_training_stop = True
                return control

        callbacks.append(StopAfterStepCallback())

    training_args = TrainingArguments(**training_kwargs)
    return Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        eval_dataset=eval_dataset,
        callbacks=callbacks,
    )


def resolve_pilot_output_dir(
    config: TrainingConfig,
    output_dir: str | Path | None = None,
) -> Path:
    if output_dir is not None:
        return Path(output_dir)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_dir = config.model.output_dir / "pilot" / f"run-{timestamp}"
    candidate = base_dir
    index = 2
    while candidate.exists():
        candidate = base_dir.with_name(f"{base_dir.name}-{index}")
        index += 1
    return candidate


def resolve_formal_run_dir(
    config: TrainingConfig,
    run_dir: str | Path | None = None,
    run_name: str | None = None,
) -> Path:
    if run_dir is not None:
        return Path(run_dir)

    runs_dir = config.model.output_dir / "runs"
    if run_name:
        return runs_dir / run_name

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_dir = runs_dir / f"run-{timestamp}"
    candidate = base_dir
    index = 2
    while candidate.exists():
        candidate = base_dir.with_name(f"{base_dir.name}-{index}")
        index += 1
    return candidate


def prepare_run_output_dir(output_dir: Path, resume: bool) -> None:
    if resume:
        if not output_dir.exists():
            raise ValueError(f"Cannot resume because run directory does not exist: {output_dir}")
        return

    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"Run directory already exists and is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)


def resolve_resume_checkpoint(
    output_dir: Path,
    resume_from_checkpoint: str | Path | None,
) -> Path | None:
    if resume_from_checkpoint is None:
        return None

    if str(resume_from_checkpoint) == "latest":
        checkpoint = find_latest_checkpoint(output_dir)
        if checkpoint is None:
            raise ValueError(f"No checkpoint found for resume in {output_dir}")
        return checkpoint

    checkpoint = Path(resume_from_checkpoint)
    if not checkpoint.is_absolute() and not checkpoint.exists():
        candidate = output_dir / checkpoint
        if candidate.exists():
            checkpoint = candidate
    if not checkpoint.exists() or not checkpoint.is_dir():
        raise ValueError(f"Resume checkpoint does not exist or is not a directory: {checkpoint}")
    return checkpoint


def checkpoint_step(checkpoint_path: Path) -> int | None:
    if not checkpoint_path.name.startswith("checkpoint-"):
        return None
    step_text = checkpoint_path.name[len("checkpoint-") :]
    try:
        return int(step_text)
    except ValueError:
        return None


def read_manifest_row_limit(output_dir: Path) -> int | None:
    manifest_path = output_dir / "run_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    row_limit = data.get("data", {}).get("row_limit")
    if isinstance(row_limit, bool):
        return None
    if isinstance(row_limit, int) and row_limit > 0:
        return row_limit
    return None


def resolve_resume_row_limit(
    requested_row_limit: int | None,
    manifest_row_limit: int | None,
) -> int | None:
    if requested_row_limit is None:
        return manifest_row_limit
    if manifest_row_limit is not None and requested_row_limit != manifest_row_limit:
        raise ValueError(
            "resume row_limit must match the existing run manifest: "
            f"{requested_row_limit} != {manifest_row_limit}"
        )
    return requested_row_limit


def write_split_artifacts(
    output_dir: Path,
    train_examples: Sequence[TrainingExample],
    validation_examples: Sequence[TrainingExample],
    test_examples: Sequence[TrainingExample],
    id_column: str,
    source_column: str,
    target_column: str,
) -> tuple[Path, Path, Path]:
    split_dir = output_dir / "splits"
    split_dir.mkdir(parents=True, exist_ok=True)
    train_path = split_dir / "train.csv"
    validation_path = split_dir / "validation.csv"
    test_path = split_dir / "test.csv"
    write_examples_csv(train_path, train_examples, id_column, source_column, target_column)
    write_examples_csv(validation_path, validation_examples, id_column, source_column, target_column)
    write_examples_csv(test_path, test_examples, id_column, source_column, target_column)
    return train_path, validation_path, test_path


def write_examples_csv(
    path: Path,
    examples: Sequence[TrainingExample],
    id_column: str,
    source_column: str,
    target_column: str,
) -> None:
    fieldnames = [id_column, source_column, target_column]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for example in examples:
            writer.writerow(
                {
                    id_column: example.segment_id,
                    source_column: example.source_text,
                    target_column: example.target_text,
                }
            )


def hash_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def list_checkpoint_paths(output_dir: str | Path) -> list[Path]:
    path = Path(output_dir)
    if not path.exists():
        return []

    checkpoints: list[tuple[int, Path]] = []
    for child in path.iterdir():
        if not child.is_dir() or not child.name.startswith("checkpoint-"):
            continue
        step_text = child.name[len("checkpoint-") :]
        try:
            step = int(step_text)
        except ValueError:
            continue
        checkpoints.append((step, child))
    return [checkpoint for _, checkpoint in sorted(checkpoints)]


def find_latest_checkpoint(output_dir: str | Path) -> Path | None:
    checkpoints = list_checkpoint_paths(output_dir)
    if not checkpoints:
        return None
    return checkpoints[-1]


def resolve_training_device(device: str) -> str:
    if device not in {"auto", "cuda", "cpu"}:
        raise ValueError("device must be one of: auto, cuda, cpu")

    import torch

    cuda_available = torch.cuda.is_available()
    if device == "auto":
        return "cuda" if cuda_available else "cpu"
    if device == "cuda" and not cuda_available:
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is False")
    return device


def resolve_trainer_precision(device: str) -> str:
    if device != "cuda":
        return "fp32"

    import torch

    if hasattr(torch.cuda, "is_bf16_supported") and torch.cuda.is_bf16_supported():
        return "bf16"
    return "fp16"


def cuda_device_name(device: str) -> str:
    if device != "cuda":
        return "none"

    import torch

    return torch.cuda.get_device_name(0)


def cuda_memory_summary(device: str) -> str:
    if device != "cuda":
        return "none"

    import torch

    allocated = torch.cuda.memory_allocated(0) / (1024**3)
    reserved = torch.cuda.memory_reserved(0) / (1024**3)
    return f"allocated_gb={allocated:.2f};reserved_gb={reserved:.2f}"


class TorchTrainingDataset:
    def __init__(self, examples: Sequence[TokenizedTrainingExample]) -> None:
        if not examples:
            raise ValueError("TorchTrainingDataset requires at least one example")
        self.examples = list(examples)

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int) -> dict[str, Any]:
        import torch

        example = self.examples[index]
        return {
            "input_ids": torch.tensor(example.input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(example.attention_mask, dtype=torch.long),
            "labels": torch.tensor(example.labels, dtype=torch.long),
        }


def shape_text(batch: Sequence[Sequence[int]]) -> str:
    if not batch:
        return "0 x 0"
    return f"{len(batch)} x {len(batch[0])}"


def write_run_manifest(
    result: FormalTrainingRunResult,
    command: Sequence[str] | None = None,
    repo_root: Path | None = None,
) -> None:
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "command": list(command) if command is not None else [],
        "git": collect_git_info(repo_root),
        "config": {
            "path": str(result.config_path),
            "segments_path": str(result.segments_path),
            "glossary_path": str(result.glossary_path),
        },
        "data": {
            "total_rows": result.total_rows,
            "row_limit": result.row_limit,
            "segments_sha256": result.segments_sha256,
            "split_seed": result.split_seed,
            "split_ratios": {
                "train": result.train_ratio,
                "validation": result.validation_ratio,
                "test": result.test_ratio,
            },
            "train_rows": result.train_rows,
            "validation_rows": result.validation_rows,
            "test_rows": result.test_rows,
            "train_split_path": str(result.train_split_path),
            "validation_split_path": str(result.validation_split_path),
            "test_split_path": str(result.test_split_path),
        },
        "model": {
            "name": result.model_name,
            "output_dir": str(result.output_dir),
            "parameter_count": result.parameter_count,
            "embedding_size_before": result.embedding_size_before,
            "embedding_size_after": result.embedding_size_after,
        },
        "language": {
            "source_code": result.source_code,
            "target_code": result.target_code,
            "target_language_token_id": result.target_language_token_id,
        },
        "tokenization": {
            "max_length": result.max_length,
            "special_tokens_added": result.special_tokens_added,
            "tokenizer_vocab_size": result.tokenizer_vocab_size,
            "input_shape": result.input_shape,
            "label_shape": result.label_shape,
        },
        "checkpoint_policy": {
            "save_strategy": "steps",
            "save_steps": result.save_steps,
            "eval_strategy": "steps",
            "eval_steps": result.eval_steps,
            "save_total_limit": result.save_total_limit,
            "resume_from_checkpoint": str(result.resume_checkpoint)
            if result.resume_checkpoint is not None
            else None,
            "checkpoint_paths": [str(path) for path in result.checkpoint_paths],
        },
        "training": {
            "max_steps": result.max_steps,
            "logging_steps": result.logging_steps,
            "gradient_accumulation_steps": result.gradient_accumulation_steps,
            "learning_rate": result.learning_rate,
            "warmup_ratio": result.warmup_ratio,
            "weight_decay": result.weight_decay,
            "max_grad_norm": result.max_grad_norm,
            "final_global_step": result.final_global_step,
            "train_loss": result.train_loss,
            "eval_loss": result.eval_loss,
            "device": result.device,
            "cuda_device_name": result.cuda_device_name,
            "cuda_memory_summary": result.cuda_memory_summary,
            "torch_dtype": result.torch_dtype,
        },
        "dependencies": dependency_versions(
            [
                "torch",
                "transformers",
                "accelerate",
                "tokenizers",
                "sentencepiece",
            ]
        ),
    }
    result.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def collect_git_info(repo_root: Path | None) -> dict[str, str]:
    if repo_root is None:
        return {"branch": "unknown", "commit": "unknown"}
    return {
        "branch": run_git_text(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"]),
        "commit": run_git_text(repo_root, ["rev-parse", "HEAD"]),
    }


def run_git_text(repo_root: Path, args: Sequence[str]) -> str:
    safe_directory = str(repo_root).replace("\\", "/")
    try:
        completed = subprocess.run(
            ["git", "-c", f"safe.directory={safe_directory}", "-C", str(repo_root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def dependency_versions(names: Sequence[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not_installed"
    return versions


def find_last_log_value(log_history: Sequence[dict[str, Any]], key: str) -> float | None:
    for item in reversed(log_history):
        if key not in item:
            continue
        value = item[key]
        if isinstance(value, (int, float)):
            return float(value)
    return None


def resolve_required_positive_int(name: str, cli_value: int | None, config_value: int | None) -> int:
    value = cli_value if cli_value is not None else config_value
    if value is None:
        raise ValueError(f"Formal training requires {name} from config or CLI")
    return validate_positive_int(name, value)


def resolve_positive_int(
    name: str,
    cli_value: int | None,
    config_value: int | None,
    default: int,
) -> int:
    value = cli_value if cli_value is not None else config_value
    if value is None:
        value = default
    return validate_positive_int(name, value)


def resolve_positive_float(
    name: str,
    cli_value: float | None,
    config_value: float | None,
) -> float | None:
    value = cli_value if cli_value is not None else config_value
    if value is None:
        return None
    if value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return float(value)


def resolve_non_negative_float(
    name: str,
    cli_value: float | None,
    config_value: float | None,
    default: float,
) -> float:
    value = cli_value if cli_value is not None else config_value
    if value is None:
        value = default
    if value < 0:
        raise ValueError(f"{name} must be a non-negative number")
    return float(value)


def validate_positive_int(name: str, value: int) -> int:
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def split_examples(
    examples: Sequence[TrainingExample],
    train_ratio: float,
    validation_ratio: float,
    test_ratio: float,
    seed: int,
) -> tuple[list[TrainingExample], list[TrainingExample], list[TrainingExample]]:
    shuffled = list(examples)
    random.Random(seed).shuffle(shuffled)

    if not shuffled:
        return [], [], []

    validation_count = split_count(len(shuffled), validation_ratio)
    test_count = split_count(len(shuffled), test_ratio)
    if len(shuffled) >= 3:
        if validation_ratio > 0 and validation_count == 0:
            validation_count = 1
        if test_ratio > 0 and test_count == 0:
            test_count = 1
    while validation_count + test_count >= len(shuffled) and test_count > 0:
        test_count -= 1
    while validation_count + test_count >= len(shuffled) and validation_count > 0:
        validation_count -= 1

    validation_examples = shuffled[:validation_count]
    test_start = validation_count
    test_end = validation_count + test_count
    test_examples = shuffled[test_start:test_end]
    train_examples = shuffled[test_end:]
    return train_examples, validation_examples, test_examples


def split_count(total: int, ratio: float) -> int:
    if total <= 0 or ratio <= 0:
        return 0
    return int(total * ratio)


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
        f"test_rows={plan.test_rows}",
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


def format_nllb_trainer_smoke_test(result: NllbTrainerSmokeResult) -> str:
    lines = [
        "NLLB tokenizer / Trainer smoke-test result",
        f"config={result.config_path}",
        f"segments={result.segments_path}",
        f"glossary={result.glossary_path}",
        f"tokenizer={result.tokenizer_name}",
        f"output_dir={result.output_dir}",
        f"language_pair={result.source_code}->{result.target_code}",
        f"target_language_token_id={result.target_language_token_id}",
        f"special_tokens_added={result.special_tokens_added}",
        f"tokenizer_vocab_size={result.tokenizer_vocab_size}",
        f"max_length={result.max_length}",
        f"prepared_rows={result.prepared_rows}",
        f"tokenized_rows={result.tokenized_rows}",
        f"input_shape={result.input_shape}",
        f"label_shape={result.label_shape}",
        f"trainer_max_steps={result.trainer_max_steps}",
        f"train_loss={result.train_loss}",
    ]
    return "\n".join(lines)


def format_real_model_smoke_test(result: RealModelSmokeResult) -> str:
    lines = [
        "Real NLLB model Trainer smoke-test result",
        f"config={result.config_path}",
        f"segments={result.segments_path}",
        f"glossary={result.glossary_path}",
        f"model={result.model_name}",
        f"output_dir={result.output_dir}",
        f"language_pair={result.source_code}->{result.target_code}",
        f"target_language_token_id={result.target_language_token_id}",
        f"special_tokens_added={result.special_tokens_added}",
        f"tokenizer_vocab_size={result.tokenizer_vocab_size}",
        f"embedding_size_before={result.embedding_size_before}",
        f"embedding_size_after={result.embedding_size_after}",
        f"parameter_count={result.parameter_count}",
        f"device={result.device}",
        f"cuda_device_name={result.cuda_device_name}",
        f"cuda_memory_summary={result.cuda_memory_summary}",
        f"torch_dtype={result.torch_dtype}",
        f"max_length={result.max_length}",
        f"prepared_rows={result.prepared_rows}",
        f"tokenized_rows={result.tokenized_rows}",
        f"input_shape={result.input_shape}",
        f"label_shape={result.label_shape}",
        f"trainer_max_steps={result.trainer_max_steps}",
        f"train_loss={result.train_loss}",
    ]
    return "\n".join(lines)


def format_real_model_pilot_training(result: RealModelPilotTrainingResult) -> str:
    lines = [
        "Real NLLB model pilot training result",
        f"config={result.config_path}",
        f"segments={result.segments_path}",
        f"glossary={result.glossary_path}",
        f"model={result.model_name}",
        f"output_dir={result.output_dir}",
        f"language_pair={result.source_code}->{result.target_code}",
        f"target_language_token_id={result.target_language_token_id}",
        f"special_tokens_added={result.special_tokens_added}",
        f"tokenizer_vocab_size={result.tokenizer_vocab_size}",
        f"embedding_size_before={result.embedding_size_before}",
        f"embedding_size_after={result.embedding_size_after}",
        f"parameter_count={result.parameter_count}",
        f"device={result.device}",
        f"cuda_device_name={result.cuda_device_name}",
        f"cuda_memory_summary={result.cuda_memory_summary}",
        f"torch_dtype={result.torch_dtype}",
        f"max_length={result.max_length}",
        f"prepared_rows={result.prepared_rows}",
        f"tokenized_rows={result.tokenized_rows}",
        f"input_shape={result.input_shape}",
        f"label_shape={result.label_shape}",
        f"first_stage_steps={result.first_stage_steps}",
        f"final_max_steps={result.final_max_steps}",
        f"save_steps={result.save_steps}",
        f"resume_checkpoint={result.resume_checkpoint}",
        f"checkpoint_paths={';'.join(str(path) for path in result.checkpoint_paths)}",
        f"first_stage_loss={result.first_stage_loss}",
        f"final_train_loss={result.final_train_loss}",
        f"final_global_step={result.final_global_step}",
    ]
    return "\n".join(lines)


def format_formal_training_run(result: FormalTrainingRunResult) -> str:
    lines = [
        "Real NLLB formal training run result",
        f"config={result.config_path}",
        f"segments={result.segments_path}",
        f"glossary={result.glossary_path}",
        f"model={result.model_name}",
        f"output_dir={result.output_dir}",
        f"manifest={result.manifest_path}",
        f"train_split={result.train_split_path}",
        f"validation_split={result.validation_split_path}",
        f"test_split={result.test_split_path}",
        f"language_pair={result.source_code}->{result.target_code}",
        f"target_language_token_id={result.target_language_token_id}",
        f"special_tokens_added={result.special_tokens_added}",
        f"tokenizer_vocab_size={result.tokenizer_vocab_size}",
        f"embedding_size_before={result.embedding_size_before}",
        f"embedding_size_after={result.embedding_size_after}",
        f"parameter_count={result.parameter_count}",
        f"device={result.device}",
        f"cuda_device_name={result.cuda_device_name}",
        f"cuda_memory_summary={result.cuda_memory_summary}",
        f"torch_dtype={result.torch_dtype}",
        f"total_rows={result.total_rows}",
        f"row_limit={result.row_limit}",
        f"segments_sha256={result.segments_sha256}",
        f"split_seed={result.split_seed}",
        f"split_ratios={result.train_ratio}:{result.validation_ratio}:{result.test_ratio}",
        f"train_rows={result.train_rows}",
        f"validation_rows={result.validation_rows}",
        f"test_rows={result.test_rows}",
        f"tokenized_train_rows={result.tokenized_train_rows}",
        f"tokenized_validation_rows={result.tokenized_validation_rows}",
        f"input_shape={result.input_shape}",
        f"label_shape={result.label_shape}",
        f"max_steps={result.max_steps}",
        f"save_steps={result.save_steps}",
        f"eval_steps={result.eval_steps}",
        f"save_total_limit={result.save_total_limit}",
        f"logging_steps={result.logging_steps}",
        f"gradient_accumulation_steps={result.gradient_accumulation_steps}",
        f"learning_rate={result.learning_rate}",
        f"warmup_ratio={result.warmup_ratio}",
        f"weight_decay={result.weight_decay}",
        f"max_grad_norm={result.max_grad_norm}",
        f"resume_checkpoint={result.resume_checkpoint}",
        f"checkpoint_paths={';'.join(str(path) for path in result.checkpoint_paths)}",
        f"train_loss={result.train_loss}",
        f"eval_loss={result.eval_loss}",
        f"final_global_step={result.final_global_step}",
    ]
    return "\n".join(lines)
