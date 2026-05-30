# ADR-0017: Generation Evaluation Reports Are Local Engineering Artifacts

- Status: Accepted
- Date: 2026-05-25

## Context

The project needed a fixed report shape for RF-006 generation outputs before running long
training or full validation. Without a stable format, each evaluation run would produce
differently structured output that could not be compared across checkpoints.

However, reports derived from pilot or smoke checkpoints are engineering-loop artifacts, not
quality evidence—treating them as committed documentation would be misleading.

## Decision

Generation evaluation reports live under ignored `data/review/evaluation/` and record:
checkpoint/generation metadata, BLEU, glossary preservation, and sample review rows—without
implying model quality.

The same report format is used for: pilot, validation, and future test outputs. This format
does not change based on checkpoint quality.

Full-run quality conclusions require: a real training run, a selected checkpoint, and a
held-out test report (see [[ADR-0023]]).

## Consequences

- Reports are regenerated locally on demand; they are not committed or pushed.
- The format is stable enough to compare reports across different checkpoints.
- Pilot/engineering reports must be explicitly labeled as engineering artifacts, not cited
  as model quality.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entries: RF-007-P2, RF-007-P3
- Related code: `configs/evaluation/generation_report.json`, `scripts/evaluate_translation.py`
