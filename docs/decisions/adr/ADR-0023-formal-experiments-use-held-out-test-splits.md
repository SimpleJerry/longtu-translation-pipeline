# ADR-0023: Formal Experiments Use Held-Out Test Splits (8:1:1, seed=42)

- Status: Accepted
- Date: 2026-05-25

## Context

The first 10k training run (RF-006-P9) reported metrics on the validation split. Validation
is for training-time checkpoint selection; reporting final model performance on validation data
is not acceptable because checkpoint selection can overfit to the validation set. A held-out
test split is the standard NMT practice for final model quality claims.

## Decision

Formal experiments use deterministic **train / validation / test = 8:1:1 splits** with
**seed 42**.

- Validation is for training-time eval and checkpoint observation.
- Test is reserved for **final performance reports only**.
- The 8:1:1 / seed=42 contract is locked for RF-006-P11 / RF-007-P3 reproducibility; changing
  splits requires a new task and new ADR.
- Test split is used **once per model**; iterating on test results to find a "better" checkpoint
  is data leakage.

## Consequences

- `configs/training/default.json` and `configs/training/full_10k.json` both use 8:1:1 / seed=42.
- Validation-only reports from RF-006-P9 are explicitly historical engineering artifacts.
- `scripts/run_inference.py --generate-test` reads the test split from the run manifest
  (see [[ADR-0020]]).

## References

- Original entry: phase-1 refactor decisions log (archived; see ADR-0032 and git tag `phase-1-refactor-archive`)
- Related backlog entries: RF-006-P10, RF-007-P3
- Related code: `src/longtu_translation_pipeline/training.py`, `scripts/run_inference.py`
