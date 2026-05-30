# T-D1 · RF-020 · Slim `src/longtu_translation_pipeline/__init__.py` public surface

> Status: PENDING | Blocked-by: none | Parallel-safe with: all others
> Touches: `src/longtu_translation_pipeline/__init__.py`
> Audit: P2-2 (2026-05-26)

## Why

The current `__init__.py` re-exports CLI-internal smoke / pilot
helpers (`run_real_nllb_pilot_training`, `run_real_nllb_model_smoke_test`,
`run_nllb_trainer_smoke_test`, `format_*_smoke_test`,
`format_real_model_pilot_training`) but does NOT export the real
training entry `run_real_nllb_formal_training`. Meanwhile
`scripts/train_model.py` imports `run_real_nllb_formal_training`
directly from the submodule.

The result is a public API surface that exposes engineering scaffolding
but hides the actual training entry — exactly inverted. Per audit
recommendation, *remove* the smoke/pilot/formal entry points from the
public API and keep only stable types and pure functions. CLI scripts
keep importing what they need directly from submodules.

## Prerequisites

- None.

## Shared context (read these first)

- [docs/refactor/audit-2026-05-26.md](../audit-2026-05-26.md) §P2-2
- [ADR-0006](../../decisions/adr/ADR-0006-preserve-public-compatibility-by-default.md) — Preserve Public Compatibility by Default (the high bar for breaking the public surface; removing items no external caller relies on, verified by audit, is acceptable)

## Files to read first

- `src/longtu_translation_pipeline/__init__.py` — all 105 lines, both
  the imports and `__all__`
- `scripts/train_model.py:12-25` — confirm CLI still works after
  removal (it imports directly from `.training`)
- `scripts/run_inference.py` and `scripts/evaluate_translation.py` —
  confirm same direct submodule imports

## Don't touch

- The submodules `training.py`, `inference.py`, `evaluation.py`,
  `text_protection.py`, `config.py` themselves — only the
  package's `__init__.py`.
- Anything in `scripts/`.

## Modification surface

Keep in `__init__.py` (stable public types + pure helpers):

- `EvaluationConfig`, `InferenceConfig`, `TrainingConfig` (and their
  loaders `load_evaluation_config`, `load_inference_config`,
  `load_training_config`)
- `BleuResult`, `EvaluationResult`, `GlossaryPreservationResult`
- `compute_corpus_bleu`, `compute_glossary_preservation`,
  `evaluate_translation`, `format_evaluation_summary`
- `GlossaryTerm`, `ProtectionResult`, `load_glossary_terms`,
  `protect_training_pair`, `strip_glossary_markers`
- `InferenceRecord`, `GeneratedTranslationRow`, `InferenceDryRunPlan`,
  `InferenceGenerationResult`, `build_inference_dry_run`,
  `format_inference_dry_run`, `format_inference_generation`,
  `generate_translations`
- `TrainingDryRunPlan`, `TrainingExample`, `TrainingSmokeTestPlan`,
  `TokenizedTrainingExample`, `build_training_dry_run`,
  `format_training_dry_run`, `build_training_smoke_test`,
  `format_training_smoke_test`, `prepare_training_examples`,
  `tokenize_training_examples`
  (these data-shape helpers are reusable; keep them)

Remove from `__init__.py` (CLI engineering scaffolding):

- `NllbTrainerSmokeResult`, `RealModelPilotTrainingResult`,
  `RealModelSmokeResult`
- `run_real_nllb_pilot_training`, `run_real_nllb_model_smoke_test`,
  `run_nllb_trainer_smoke_test`
- `format_nllb_trainer_smoke_test`, `format_real_model_pilot_training`,
  `format_real_model_smoke_test`
- The matching entries in `__all__`

CLI scripts will continue importing these from
`longtu_translation_pipeline.training` directly — that's a known and
acceptable internal coupling.

## Acceptance criteria

1. `from longtu_translation_pipeline import TrainingConfig,
   evaluate_translation` still works.
2. `from longtu_translation_pipeline import
   run_real_nllb_pilot_training` raises `ImportError`. Same for the
   other removed names.
3. `python scripts/train_model.py --config configs/training/default.json
   --dry-run` still works (CLI uses direct submodule import).
4. `python -m unittest discover -s tests` passes with no regressions.
5. Backlog entry RF-020 set to `DONE`.

## Verification

```powershell
venv\Scripts\python.exe -c "from longtu_translation_pipeline import TrainingConfig, evaluate_translation, protect_training_pair; print('public api ok')"
venv\Scripts\python.exe -c "from longtu_translation_pipeline import run_real_nllb_pilot_training" 2>&1
# Expect: ImportError
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --dry-run
venv\Scripts\python.exe -m unittest discover -s tests
git -c safe.directory=D:/longtu-translation-pipeline diff --check
```

## Git workflow

- One commit, message: `Slim public API surface in package __init__ (RF-020)`.
- Do not push.
- Update RF-020 status to `DONE` in the same commit.
