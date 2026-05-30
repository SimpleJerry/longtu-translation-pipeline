# ADR-0001: README and AGENTS Do Not Carry Long-Term Task Pools

- Status: Accepted
- Date: 2026-05-17

## Context

README files were beginning to accumulate long-running refactor TODO lists and task planning
content. AGENTS.md was similarly at risk of becoming a mixed working-rules-and-task-pool file.
These files are the primary entry point for human readers and AI agents; cluttering them with
task tracking degrades their signal-to-noise ratio and makes them hard to maintain.

## Decision

README files (`README.md`, `README.en.md`, `README.zh-CN.md`) stay focused on project
introduction, setup, basic usage, and navigation links. `AGENTS.md` stays focused on AI/Codex
working rules. Neither file carries long-term refactor TODOs or task pools.

Short navigation links pointing to `docs/refactor/backlog.md` (and now `docs/decisions/adr/`)
are acceptable; embedded task lists are not.

## Consequences

- All long-term refactor TODOs moved to `docs/refactor/backlog.md`.
- README files remain usable as user-facing documentation without noise from internal planning.
- New refactor work items must be added to the backlog, not to README or AGENTS.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entry: RF-009
