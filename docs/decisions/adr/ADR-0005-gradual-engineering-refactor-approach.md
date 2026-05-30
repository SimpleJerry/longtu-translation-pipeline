# ADR-0005: Gradual Engineering Refactor Approach

- Status: Accepted
- Date: 2026-05-17

## Context

The repository was an experiment workspace consisting of Jupyter notebooks and one data
script. The project needed a refactor strategy: rewrite the whole project at once vs.
refactor incrementally.

Rewriting all at once risks breaking existing workflows, losing experiment history, and
producing a large unreviewed diff. The project was still actively used for manual research.

## Decision

Refactor incrementally ("渐进工程化") instead of rewriting the whole project at once.

- Keep notebooks as experiment records while extracting repeatable logic into modules
  and CLIs over time.
- Each refactor task targets one clearly bounded scope.
- Commit sizes are kept manageable for review.

## Consequences

- Historical notebooks are preserved and documented (see [[ADR-0009]]) rather than deleted.
- Reusable logic (terminology protection, training, inference, evaluation) is extracted
  module by module.
- The project is usable at each intermediate stage; there is no "flag day" rewrite.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entry: RF-009
