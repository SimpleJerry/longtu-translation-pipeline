# ADR-0003: Phase-1 Architecture Decisions Log (Superseded)

- Status: Superseded by docs/decisions/adr/ (this ADR system)
- Date: 2026-05-17

## Context

The project needed a place to record confirmed architecture decisions and refactor principles
so they would not be re-decided in each task. A chronological single-file log was chosen as
the initial format.

## Decision

Confirmed architecture decisions and refactor principles were placed in a chronologically
ordered `decisions.md` log (in the original phase-1 refactor scaffolding; one `## YYYY-MM-DD:`
section per decision).

## Consequences

- Decisions were easy to find by date but hard to reference individually or link to precisely.
- As the number of decisions grew, navigating and linking to specific decisions became
  cumbersome for task-brief files and the backlog.
- This format has been superseded; the original `decisions.md` is archived in git history
  (tag: `phase-1-refactor-archive`). All decisions have been migrated to individual ADR files
  in `docs/decisions/adr/`.

## References

- Original entry: phase-1 refactor decisions log (archived; see ADR-0032 and git tag `phase-1-refactor-archive`)
- Superseded by: this `docs/decisions/adr/` directory
