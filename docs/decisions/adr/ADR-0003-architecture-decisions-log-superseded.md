# ADR-0003: Architecture Decisions Lived in docs/refactor/decisions.md

- Status: Superseded by docs/decisions/adr/ (this ADR system)
- Date: 2026-05-17

## Context

The project needed a place to record confirmed architecture decisions and refactor principles
so they would not be re-decided in each task. A chronological single-file log was chosen as
the initial format.

## Decision

Confirmed architecture decisions and refactor principles were placed in
`docs/refactor/decisions.md` as a chronologically ordered decision log (one `## YYYY-MM-DD:`
section per decision).

## Consequences

- Decisions were easy to find by date but hard to reference individually or link to precisely.
- As the number of decisions grew, navigating and linking to specific decisions became
  cumbersome for task-brief files and the backlog.
- This format has been superseded: `docs/refactor/decisions.md` is now a pointer file.
  All decisions have been migrated to individual ADR files in `docs/decisions/adr/`.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive — preserved as pointer)
- Superseded by: this `docs/decisions/adr/` directory
