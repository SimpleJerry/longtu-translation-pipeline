# ADR-0032: Retire Phase-1 Refactor Scaffolding

- Status: Accepted
- Date: 2026-05-30
- Supersedes: ADR-0002

## Context

The phase-1 engineering refactor (RF-001 through RF-022, plus follow-on RF-026–RF-031)
has concluded. All durable decisions have been migrated to individual ADR files
(ADR-0001–ADR-0031). Metrics and model lineage live in
[`docs/product/model-card.md`](../../product/model-card.md). Data-cleaning rules live
in [`docs/architecture/data-cleaning-pipeline.md`](../../architecture/data-cleaning-pipeline.md).
Invariants live in [`docs/architecture/invariants.md`](../../architecture/invariants.md).
Product scope lives in [`docs/product/scope.md`](../../product/scope.md).

`docs/refactor/` was the process scaffolding for that phase:

| File | Content | Status |
|------|---------|--------|
| `backlog.md` | RF-001–RF-031 task pool with per-task run logs | All tasks DONE or explicitly deferred |
| `decisions.md` | Pointer to ADR directory (already superseded by ADR-0003) | Superseded |
| `follow-up-tasks.md` | Parallel-track assignment map | No longer active |
| `audit-2026-05-26.md` | One-time repository audit snapshot | Historical only |
| `task-briefs/T-*.md` | Per-task implementation briefs (T-A1–T-F5) | Completed; process history only |

The only "承重" (load-bearing) content worth evaluating:

- **RF-006-P12 checkpoint comparison table**: intermediate validation data for a
  superseded 10k-step run. The headline numbers from the current model are in the model
  card; this table is process history. Not extracted.
- **RF-007-P5 base-model baseline**: already summarized in
  [`docs/product/model-card.md`](../../product/model-card.md) §Reference Points.
- **RF-016–RF-022 engineering decisions**: all ADR-ized (ADR-0014–ADR-0022 and ADR-0031).
- **`audit-2026-05-26.md`**: one-time audit snapshot; value was at audit time. Not extracted.

## Decision

Retire `docs/refactor/` by:

1. Creating an annotated git tag `phase-1-refactor-archive` pointing to the last commit
   that still contains the full scaffolding, so the history is recoverable at any time.
2. Running `git rm -r docs/refactor/` to remove the directory from the working tree and
   index.

ADR-0002 (which established `docs/refactor/backlog.md` as the single source of truth
for refactor tasks) is superseded by this decision — the backlog's role is concluded and
the directory is retired.

Future refactor or feature work should use either:
- This ADR system for durable decisions, or
- Ephemeral task documents (outside the repository, or as short-lived branches) for
  implementation tracking.

## Consequences

- `docs/refactor/` no longer exists in the working tree after this change.
- ADR-0002 is marked **Superseded by ADR-0032**.
- To review any historical task brief, backlog note, or audit finding, check out the tag:
  `git show phase-1-refactor-archive:docs/refactor/backlog.md`
- No code, config, test, or data file is affected — this is a documentation-only change.

## References

- Supersedes: [ADR-0002](ADR-0002-refactor-backlog-lives-in-docs-refactor-backlog.md)
- Related: [ADR-0003](ADR-0003-architecture-decisions-log-superseded.md) (decisions.md already superseded)
- Git tag: `phase-1-refactor-archive`
