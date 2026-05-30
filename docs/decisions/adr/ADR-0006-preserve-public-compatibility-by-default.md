# ADR-0006: Preserve Public Compatibility by Default

- Status: Accepted
- Date: 2026-05-17

## Context

The project contains research workflows that may still be used manually by the author. During
incremental refactoring (see [[ADR-0005]]), each task risks accidentally breaking documented
commands, public APIs, file formats, or token names that are in active use.

## Decision

Preserve documented commands, public APIs, file formats, token names, and notebook usability
unless a selected task explicitly requires a breaking change.

Breaking changes require:
1. Explicit scope in the backlog item.
2. README updates in the same commit.
3. Migration notes where appropriate.

## Consequences

- Individual refactor tasks can be executed without fear of silently breaking the overall
  workflow.
- Breaking changes are opt-in and documented, not accidental side effects.
- This constraint applies across: CLI design, module extraction, data conversion, and
  notebook migration.

## References

- Original entry: phase-1 refactor decisions log (archived; see ADR-0032 and git tag `phase-1-refactor-archive`)
- Related backlog entry: RF-009
