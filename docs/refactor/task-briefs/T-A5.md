# T-A5 · RF-006-P13 · Early-stopping formal training with composite metric

> Status: PENDING | Blocked-by: none (data + previous baseline already exist) | Gates: T-A6 (new final test report) | Parallel-safe with: T-F1, T-F2, T-F5, T-B*, T-C*, T-D*, T-E*
> Touches: `src/longtu_translation_pipeline/config.py`, `src/longtu_translation_pipeline/training.py`, new `src/longtu_translation_pipeline/training_metrics.py`, new `configs/training/full_earlystop.json`, `tests/test_training_pipeline.py`, `docs/refactor/backlog.md` (RF-006-P13 Notes), ignored `fine-tuned-models/.../runs/run-full-earlystop-v1/`

## Why

`run-full-10k-llm-segments-v1` (RF-006-P11) used `max_steps=10000`, which
worked out to **0.189 of one epoch** on the 53,015-row train split. At
the end of that run:

- `eval_loss` was still decreasing (step 5000 → 10000: 0.0729 → 0.0672)
- Validation BLEU was monotonically rising (7000 → 10000: 0.1917 → 0.1969)
- Glossary preservation peaked at 8000/9000 then dipped slightly at 10000

The 10000-step ceiling was arbitrary; the model is almost certainly
under-fit but the existing config has no machinery to detect it. The
historical pattern of "save many checkpoints, pick best post-hoc" wastes
compute past the optimal point and provides no auto-stop.

This task replaces the arbitrary step count with a principled **early
stopping** loop driven by a **composite quality metric** (BLEU + glossary
preservation), so that:

- Training runs as many epochs as needed to genuinely plateau
- Auto-stops when the composite metric hasn't improved for `patience`
  consecutive evaluations
- The final loaded model is the best on the composite metric (not the
  last step)
- Future model selection is mechanical, not based on subjective trade-offs
  between BLEU vs preservation

## Prerequisites

1. `data/segments.csv` SHA256 = `1462B2E18CDB82B0FF1E9E3C80AC5AFF583227E396C54F5C6431FFD379F147BA`
   (must equal RF-006-P11's manifest; if it has changed, T-A1 was re-run
   and this brief needs the new hash before training)
2. GPU available (training runs to early stop, expected 2-6 hours)
3. RF-006-P11 retained as historical baseline; **do not touch
   `configs/training/full_10k.json` or `run-full-10k-llm-segments-v1/`**

## Shared context (read these first)

- [docs/refactor/decisions.md](../decisions.md) — pay attention to the
  newly added section on early stopping methodology; the existing
  decisions on seed 42 / split 8:1:1 / marker shape still hold
- [docs/refactor/backlog.md](../backlog.md) RF-006-P11 (the 10k baseline
  this run is compared against) and RF-006-P12 (the validation
  comparison table)
- [docs/refactor/audit-2026-05-26.md](../audit-2026-05-26.md) §P1-3 — the
  reason we have a separate `full_*.json` profile rather than editing
  `default.json`
- [src/longtu_translation_pipeline/training.py](../../../src/longtu_translation_pipeline/training.py) — current Trainer construction
- [src/longtu_translation_pipeline/evaluation.py](../../../src/longtu_translation_pipeline/evaluation.py) — `compute_corpus_bleu` and
  `compute_glossary_preservation` to be reused inside compute_metrics

## Files to read first

- `src/longtu_translation_pipeline/training.py:1006-1064` — current
  `Trainer` construction; this is what changes to `Seq2SeqTrainer`
- `src/longtu_translation_pipeline/config.py:55-69` — `TrainingArgumentsConfig`
  dataclass to extend
- `src/longtu_translation_pipeline/config.py:336-360` (approximate) — `load_training_arguments_config` loader
- `src/longtu_translation_pipeline/evaluation.py` — entire file; need
  `compute_corpus_bleu`, `compute_glossary_preservation`, and
  `strip_glossary_markers`
- `configs/training/full_10k.json` — the baseline profile to clone
- `tests/test_training_pipeline.py` — test style + Trainer-wiring tests

## Don't touch

- `configs/training/full_10k.json` — RF-006-P11 baseline must remain reproducible
- `fine-tuned-models/nllb-200-distilled-600M/zh2ko/runs/run-full-10k-llm-segments-v1/` — historical checkpoints stay
- `data/segments.csv` / `data/glossary.csv` — same corpus as RF-006-P11
- The CLI surface of `scripts/train_model.py` — no new flags; everything goes through the new config profile
- `seed`, `split` ratios, marker shape — fixed contracts
- RF-007-P3 backlog entry — keep as historical record; new test goes to RF-007-P4

## Concrete scope

### Step 1 — Extend `TrainingArgumentsConfig` (config.py)

Add 6 fields with sensible defaults (all `None` / `False` so existing
configs keep working):

```python
load_best_model_at_end: bool = False
metric_for_best_model: str | None = None
greater_is_better: bool | None = None
early_stopping_patience: int | None = None
early_stopping_threshold: float = 0.0
lr_scheduler_type: str | None = None
```

Add a nested `MetricsConfig` for compute_metrics control:

```python
@dataclass(frozen=True)
class MetricsConfig:
    enabled: bool = False
    composite_weight_bleu: float = 0.5
    composite_weight_preservation_nospace: float = 0.5
    predict_with_generate: bool = False
    generation_max_length: int = 400
    generation_num_beams: int = 1
```

Wire it into `TrainingConfig` as an optional field
(`metrics: MetricsConfig | None`).

Update `load_training_arguments_config` to parse the new fields with the
existing `optional_*` helpers. Validate that
`composite_weight_bleu + composite_weight_preservation_nospace > 0`
(weights don't have to sum to 1 — they're relative).

### Step 2 — New module `training_metrics.py`

```python
"""compute_metrics factory for Seq2SeqTrainer."""

from typing import Callable
from .text_protection import strip_glossary_markers, GlossaryTerm
from .evaluation import compute_corpus_bleu, compute_glossary_preservation


def make_compute_metrics(
    tokenizer,
    glossary_terms: list[GlossaryTerm],
    weight_bleu: float,
    weight_preservation_nospace: float,
    bleu_tokenization: str = "whitespace",
    bleu_max_order: int = 4,
    bleu_smooth_value: float = 0.1,
) -> Callable:
    def compute_metrics(eval_pred):
        predictions, label_ids = eval_pred
        # predictions: token IDs from generate (Seq2SeqTrainer with predict_with_generate)
        # label_ids: token IDs of references (-100 padding)

        # Replace -100 with tokenizer.pad_token_id before decoding
        # Decode to text
        # Strip glossary markers from both candidates and references
        # Compute BLEU (use compute_corpus_bleu from evaluation.py)
        # Compute glossary preservation (compute_glossary_preservation) — nospace mode
        # Composite = w_bleu * bleu + w_pres * preservation_nospace (no normalization)
        # Return dict:
        #   {"bleu": ..., "glossary_preservation_exact": ...,
        #    "glossary_preservation_nospace": ..., "composite": ...}

    return compute_metrics
```

The function name `eval_<key>` will be auto-prefixed by Trainer (so
`metric_for_best_model="eval_composite"` matches `"composite"` from this
dict).

### Step 3 — Switch to `Seq2SeqTrainer` in training.py

In `run_real_nllb_formal_training` (or whichever function constructs the
Trainer for `--train` formal runs):

```python
from transformers import (
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    EarlyStoppingCallback,
)

# Build training_kwargs same as before, but using Seq2SeqTrainingArguments fields.
# Add when configured:
training_kwargs["load_best_model_at_end"] = ...
training_kwargs["metric_for_best_model"] = ...
training_kwargs["greater_is_better"] = ...
training_kwargs["predict_with_generate"] = metrics_config.predict_with_generate
training_kwargs["generation_max_length"] = metrics_config.generation_max_length
training_kwargs["generation_num_beams"] = metrics_config.generation_num_beams
training_kwargs["lr_scheduler_type"] = ...  # e.g. "cosine"

callbacks = [...]
if early_stopping_patience is not None:
    callbacks.append(EarlyStoppingCallback(
        early_stopping_patience=early_stopping_patience,
        early_stopping_threshold=early_stopping_threshold,
    ))

training_args = Seq2SeqTrainingArguments(**training_kwargs)
trainer = Seq2SeqTrainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    eval_dataset=eval_dataset,
    tokenizer=tokenizer,            # required for predict_with_generate + decoding
    compute_metrics=compute_metrics_fn,  # from training_metrics.make_compute_metrics
    callbacks=callbacks,
)
```

Backward compatibility: if `metrics_config` is None or
`predict_with_generate=False`, fall back to plain `Trainer` /
`TrainingArguments` so RF-006-P11 baseline (and any smoke tests) still
work.

### Step 4 — New `configs/training/full_earlystop.json`

```json
{
  "data": { ...same as full_10k.json... },
  "language": { ...same... },
  "model": { ...same... },
  "split": { "train_ratio": 0.8, "validation_ratio": 0.1, "test_ratio": 0.1, "seed": 42 },
  "tokenization": { "max_length": 400, "padding": "max_length", "truncation": true, "terminology_markers": true },
  "training": {
    "num_train_epochs": 10,
    "per_device_train_batch_size": 4,
    "per_device_eval_batch_size": 4,
    "gradient_accumulation_steps": 1,
    "learning_rate": 0.00002,
    "warmup_ratio": 0.03,
    "weight_decay": 0.01,
    "max_grad_norm": 1.0,
    "lr_scheduler_type": "cosine",
    "save_steps": 1000,
    "eval_steps": 1000,
    "save_total_limit": 3,
    "logging_steps": 100,
    "load_best_model_at_end": true,
    "metric_for_best_model": "eval_composite",
    "greater_is_better": true,
    "early_stopping_patience": 5,
    "early_stopping_threshold": 0.0
  },
  "metrics": {
    "enabled": true,
    "composite_weight_bleu": 0.5,
    "composite_weight_preservation_nospace": 0.5,
    "predict_with_generate": true,
    "generation_max_length": 400,
    "generation_num_beams": 1
  },
  "dry_run": { "preview_rows": 3 }
}
```

Notes:
- `max_steps` deliberately absent → `num_train_epochs=10` ceiling is the
  fallback if early stop never triggers
- `per_device_train_batch_size=4` (up from 1) for gradient stability
- `lr_scheduler_type=cosine` for smoother decay over a long-than-10k run
- `weight_decay=0.01` unchanged (early stopping IS the regularization)
- `generation_num_beams=1` (greedy) for eval-time speed; T-F5 still
  separately explores beam>1 at inference

### Step 5 — Tests

Add to `tests/test_training_pipeline.py`:

1. `test_training_args_config_parses_early_stopping_fields` — config loader picks up the 6 new fields
2. `test_training_args_config_parses_metrics_subsection` — MetricsConfig populated
3. `test_seq2seq_trainer_attaches_early_stopping_callback_when_configured` — uses tiny tokenizer/model, asserts EarlyStoppingCallback present in trainer.callback_handler
4. `test_seq2seq_trainer_load_best_model_plumbed_through` — assert `trainer.args.load_best_model_at_end is True`
5. `test_compute_metrics_returns_composite_dict` — make_compute_metrics with fixed pred/label arrays returns dict containing `bleu`, `glossary_preservation_exact`, `glossary_preservation_nospace`, `composite`; verifies composite math
6. `test_formal_training_falls_back_to_trainer_when_metrics_disabled` — backward compatibility for RF-006-P11 profile

All tests run on CPU, no real NLLB model load.

### Step 6 — Execute the training run

```powershell
$env:HF_HOME = "D:\longtu-translation-pipeline\venv\hf_cache"

# Smoke first to validate compute_metrics wiring:
venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_earlystop.json --dry-run

# Then full run:
venv\Scripts\python.exe scripts\train_model.py `
    --config configs\training\full_earlystop.json `
    --train `
    --run-name run-full-earlystop-v1
```

Watch the logs for `eval_composite`, `eval_bleu`,
`eval_glossary_preservation_nospace` at each eval step.

### Step 7 — Record results in RF-006-P13 Notes

Append to RF-006-P13:
- Run name + full path
- segments_sha256 (must match baseline)
- Final epoch / global step where early stopping triggered
- Wall-clock training time
- Best `eval_composite` value + step at which it was achieved
- Whether `load_best_model_at_end` actually loaded an earlier checkpoint (it should)
- Full eval curve at each 1000-step interval as a table: step, eval_loss, eval_bleu, eval_preservation_exact, eval_preservation_nospace, eval_composite
- Comparison vs RF-006-P11 baseline (same metrics at ckpt-9000 from RF-006-P12)
- Note: held-out test report comes from T-A6 / RF-007-P4 (separate run)

## Acceptance criteria

1. `Seq2SeqTrainer` + `EarlyStoppingCallback` + `load_best_model_at_end` wired into formal training path, with backward-compat fallback for the old `Trainer` profile.
2. `make_compute_metrics` reuses existing `compute_corpus_bleu` and `compute_glossary_preservation` from `evaluation.py` (no duplicate metric code).
3. All 6 new unit tests pass; existing tests still pass (`python -m unittest discover -s tests` green).
4. `full_earlystop.json` loads via `load_training_config` without error.
5. Training run completes (either by early stopping or by hitting `num_train_epochs=10` ceiling) and the run directory contains `run_manifest.json` with the new metrics config + best_metric_value recorded.
6. Best checkpoint auto-loaded at end of training; `trainer.state.best_metric` and `trainer.state.best_model_checkpoint` present in `trainer_state.json`.
7. Backlog RF-006-P13 set to `DONE` with the comparison block above.
8. **No files added to Git** beyond `docs/refactor/backlog.md`, `configs/training/full_earlystop.json`, `src/longtu_translation_pipeline/config.py`, `src/longtu_translation_pipeline/training.py`, new `src/longtu_translation_pipeline/training_metrics.py`, and `tests/test_training_pipeline.py`.

## Risks and mitigations

- **Risk:** `predict_with_generate=True` makes each eval 5-20× slower than loss-only eval. With eval_steps=1000 and num_train_epochs=10 ceiling, eval cost could dominate. **Mitigation:** start with `generation_num_beams=1` (greedy) and `per_device_eval_batch_size=4`; if total wall-clock blows up beyond 8h, consider raising `eval_steps` to 2000.
- **Risk:** Composite metric noisy due to small validation subset relative to BLEU's sensitivity. **Mitigation:** `patience=5` (decision 2) gives enough buffer; if still spuriously stops, raise to 7 in a follow-up RF.
- **Risk:** Switching `Trainer` → `Seq2SeqTrainer` changes behavior for smoke / pilot paths. **Mitigation:** the new code path is opt-in via `metrics.predict_with_generate=true`; smoke and pilot configs leave it off, get the old `Trainer`.
- **Risk:** `load_best_model_at_end=True` requires `save_strategy` and `eval_strategy` to match — both must be `"steps"` with equal `save_steps` and `eval_steps`. **Mitigation:** the new config sets both to 1000 with strategy `"steps"`; the loader should validate this.

## Verification

```powershell
venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\config.py src\longtu_translation_pipeline\training.py src\longtu_translation_pipeline\training_metrics.py scripts\train_model.py
venv\Scripts\python.exe -m unittest tests.test_training_pipeline -v
venv\Scripts\python.exe -m unittest discover -s tests
venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_earlystop.json --dry-run
# (then the real --train command; see Step 6)
git -c safe.directory=D:/longtu-translation-pipeline status --short
git -c safe.directory=D:/longtu-translation-pipeline diff --check
```

## Git workflow

- Two commits acceptable, in this order:
  1. `Add early-stopping + composite-metric training path (RF-006-P13 setup)` — config + code + tests + new profile; landed before any real training
  2. `Record RF-006-P13 early-stopping training run results` — backlog notes after the run completes
- Do not push without explicit user confirmation.
- T-A6 (RF-007-P4, the new test report on the best checkpoint) is a **separate** brief and conversation — do not bundle.
