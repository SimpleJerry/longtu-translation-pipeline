# ADR-0020: Formal Training Runs Require Split Artifacts And Manifests

- Status: Accepted
- Date: 2026-05-25

## Context

Pilot training (see [[ADR-0015]]) proved checkpoint save and resume, but it did not provide
enough metadata or split stability for a future full run to be reproducible. Without fixed
split artifacts, each training resumption could silently use a different data subset.

## Decision

Formal training (`scripts/train_model.py --train`) must:
1. Write fixed `splits/train.csv`, `splits/validation.csv`, and `splits/test.csv` inside
   an ignored `fine-tuned-models/.../runs/run-*` directory.
2. Record `run_manifest.json` with: command, split ratios, split seed, row counts, split
   paths, `data/segments.csv` SHA256, checkpoint policy, dependency versions, loss, and
   git metadata.

Resume guards:
- Explicit `--limit-rows` must match the existing manifest row limit.
- Checkpoint steps must be smaller than the requested `max_steps`.

## Consequences

- Validation generation reads `splits/validation.csv` from the manifest (see [[ADR-0021]]).
- Final test reports read `splits/test.csv` from the manifest (see [[ADR-0023]]).
- Run directories with mismatched manifests (e.g., from pre-correction two-way splits) are
  treated as obsolete engineering artifacts.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entries: RF-006-P7, RF-006-P10
- Related code: `scripts/train_model.py`, `src/longtu_translation_pipeline/training.py`
