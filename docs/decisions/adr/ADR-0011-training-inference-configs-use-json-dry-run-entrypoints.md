# ADR-0011: Training and Inference Configs Use JSON Dry-Run Entrypoints

- Status: Accepted
- Date: 2026-05-24

## Context

Model paths, language pairs, batch sizes, and output directories were hard-coded in notebook
cells. The project needed reviewable configuration before adding heavyweight training
dependencies. Running a quick validation check should not require downloading NLLB weights.

## Decision

Training and inference settings live in JSON config files. RF-006 phase 1 entrypoints must
not load models during import or dry-run execution.

- `configs/training/default.json` — base training config
- `configs/inference/default.json` — base inference config
- `scripts/train_model.py --dry-run` and `scripts/run_inference.py --dry-run` validate
  config and data without loading models.

## Consequences

- Config is reviewable and version-controlled.
- CI/import-time checks are safe to run on any machine without GPU or model cache.
- Actual model loading, Trainer wiring, tokenization, and generation are added in later phases.
- Config drift is the primary risk; JSON profiles should be named after their purpose
  (see [[ADR-0022]]).

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entry: RF-006
- Related code: `configs/training/`, `configs/inference/`, `src/longtu_translation_pipeline/config.py`
