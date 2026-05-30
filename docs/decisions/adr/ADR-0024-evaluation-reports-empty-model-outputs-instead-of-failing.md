# ADR-0024: Evaluation Reports Empty Model Outputs Instead Of Failing

- Status: Accepted
- Date: 2026-05-25

## Context

The first 10k validation generation produced a small number of empty candidate rows. Treating
empty `candidates` cells as hard schema errors blocked the full-run evaluation report entirely
and hid a useful model-quality signal: empty candidates indicate model failure cases that
should be visible in the summary.

## Decision

Empty `candidates` cells in generated translation CSVs are valid model-output failures for
reporting, not schema errors.

Evaluation counts empty candidates as:
- Zero-length BLEU candidates.
- Glossary misses.
- `empty_candidate_rows` count in summary and report manifest.

Empty `source` and `references` remain hard errors because they indicate invalid evaluation
input rather than model behavior.

## Consequences

- `scripts/evaluate_translation.py` no longer fails on empty candidate cells.
- Full-run reports are always producible even when the model produces some empty outputs.
- Empty candidate rates are a visible quality signal in `report_manifest.json`.

## References

- Original entry: phase-1 refactor decisions log (archived; see ADR-0032 and git tag `phase-1-refactor-archive`)
- Related backlog entries: RF-007, RF-007-P2
- Related code: `src/longtu_translation_pipeline/evaluation.py`, `tests/test_evaluation.py`
