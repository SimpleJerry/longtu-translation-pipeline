# ADR-0015: Pilot Training May Save Ignored Local Checkpoints

- Status: Accepted
- Date: 2026-05-25

## Context

One-step smoke tests (see [[ADR-0014]]) proved the backward pass but did not verify checkpoint
persistence, Trainer resume behavior, loss logging across runs, or the final output directory
shape. Before investing in a multi-hour full training run, the project needed a small pilot
that exercises the real checkpoint lifecycle.

## Decision

RF-006 pilot training (`--pilot-train`) may save checkpoints under ignored
`fine-tuned-models/.../pilot/run-*` and resume from them to validate the real training
lifecycle.

Pilot checkpoints are local engineering artifacts, not deliverables:
- Not committed to Git.
- Not used as quality checkpoints.
- Outputs remain under ignored directories.

## Consequences

- Full training duration, final checkpoint selection, generation, and RF-007 quality
  evaluation all require a later, longer training phase.
- Pilot parameters (row count, max steps) are small and do not represent final training
  hyperparameters.
- The pilot output confirms the manifest schema, checkpoint naming, and resume guard behavior.

## References

- Original entry: phase-1 refactor decisions log (archived; see ADR-0032 and git tag `phase-1-refactor-archive`)
- Related backlog entry: RF-006-P5
- Related code: `scripts/train_model.py`, `src/longtu_translation_pipeline/training.py`
