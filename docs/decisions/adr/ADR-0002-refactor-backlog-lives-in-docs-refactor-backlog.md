# ADR-0002: Refactor Backlog as Single Source of Truth (Superseded by ADR-0032)

- Status: Accepted
- Date: 2026-05-17

## Context

The project needed a single authoritative location for systematic refactor tasks. Without a
dedicated location, refactor TODOs risk being scattered across README files, notebooks, and
ad-hoc comments—making it impossible for AI agents or human contributors to find and track
outstanding work.

## Decision

The refactor backlog was the single source of truth for systematic refactor TODOs (now retired; see ADR-0032).
Each backlog item includes: ID, status, scope, background/why, concrete scope, out-of-scope
notes, risks, acceptance criteria, recommended test commands, and notes.

## Consequences

- README and AGENTS files link to the backlog rather than carrying their own task lists
  (see [[ADR-0001]]).
- AI/Codex agents use the backlog to select work items.
- New refactor discoveries are added as backlog items, not folded into the current task.

## References

- Original entry: phase-1 refactor decisions log (archived; see ADR-0032 and git tag `phase-1-refactor-archive`)
- Related backlog entry: RF-009
