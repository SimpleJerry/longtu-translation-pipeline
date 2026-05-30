# ADR-0016: Inference Output Stays RF-007-Compatible

- Status: Accepted
- Date: 2026-05-25

## Context

The project needed generation output that could flow directly into the existing BLEU and
glossary-preservation evaluator without losing the link back to `data/segments.csv`. Two
schema options were considered: using the evaluator's existing `source,references,candidates`
columns directly, or adding a `segment_id` for row traceability.

## Decision

Checkpoint inference writes CSVs with schema `segment_id,source,references,candidates`.
RF-007 evaluation reads the `source`, `references`, and `candidates` columns; `segment_id`
provides row traceability.

Generated inference CSVs are local artifacts under ignored `data/review/inference/`.

## Consequences

- Generation output from `scripts/run_inference.py` can be piped directly into
  `scripts/evaluate_translation.py` without transformation.
- `segment_id` allows row-level debugging and sample review without data loss.
- Full validation generation and fixed split selection belong to later RF-006/RF-007 phases.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entries: RF-006-P6, RF-007-P2
- Related code: `src/longtu_translation_pipeline/inference.py`, `scripts/run_inference.py`
