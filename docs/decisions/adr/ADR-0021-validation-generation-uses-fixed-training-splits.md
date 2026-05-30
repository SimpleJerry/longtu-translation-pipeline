# ADR-0021: Validation Generation Uses Fixed Training Splits

- Status: Accepted
- Date: 2026-05-25

## Context

RF-006-P6 sample generation proved checkpoint loading and generation shape but generated
translations from the first N rows of `data/segments.csv` rather than from the deterministic
validation split written by the formal training run. Using an ad-hoc row slice instead of the
fixed split breaks reproducibility: the same segment can appear in both training and evaluation.

## Decision

Validation generation (`scripts/run_inference.py --generate-validation`) must read
`splits/validation.csv` from a formal run manifest (see [[ADR-0020]]) rather than taking the
first N rows from `data/segments.csv`.

The default checkpoint is the latest numeric checkpoint in the run directory; override with
`--checkpoint`.

Generated validation CSVs keep the RF-007-compatible `segment_id,source,references,candidates`
schema (see [[ADR-0016]]) and remain local ignored artifacts.

## Consequences

- Validation generation is deterministically tied to the training run's data split.
- The validation split is used for checkpoint selection (see [[ADR-0023]]).
- The test split is reserved for final held-out reports.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entries: RF-006-P8, RF-007-P3
- Related code: `scripts/run_inference.py`, `src/longtu_translation_pipeline/inference.py`
