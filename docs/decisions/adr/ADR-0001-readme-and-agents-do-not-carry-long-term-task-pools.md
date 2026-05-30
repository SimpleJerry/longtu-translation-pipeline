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

Short navigation links pointing to `docs/decisions/adr/` and the model card are acceptable;
embedded task lists are not.

## Consequences

- All long-term refactor TODOs were tracked in a dedicated refactor backlog (now retired; see ADR-0032).
- README files remain usable as user-facing documentation without noise from internal planning.
- New refactor work items must be added to the backlog, not to README or AGENTS.

## References

- Original entry: phase-1 refactor decisions log (archived; see ADR-0032 and git tag `phase-1-refactor-archive`)
- Related backlog entry: RF-009
