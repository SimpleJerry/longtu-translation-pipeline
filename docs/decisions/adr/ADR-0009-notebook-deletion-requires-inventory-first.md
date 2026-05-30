# ADR-0009: Notebook Deletion Requires Inventory First

- Status: Accepted
- Date: 2026-05-24

## Context

The repository originally held 2023 experiment notebooks in the root directory. Their original
order and purpose were no longer obvious from filenames alone after a long gap since active
use. Deleting them without documentation would have lost irreplaceable experiment history.

## Decision

Historical notebooks are classified and archived before any deletion. The layout is:
- `notebooks/main/` — main workflow notebooks
- `notebooks/analysis/` — auxiliary analysis notebooks
- `notebooks/archive/2023-legacy/` — old experiments

`docs/notebooks/inventory.md` records purpose, timeline, dependency status, and
keep/archive/delete guidance for every tracked notebook.

Do not delete archived notebooks until the inventory has been reviewed and the replacement
module, config, or evaluation path is clear.

## Consequences

- No notebooks are deleted during the initial reorganization.
- Root directory is clean: no `.ipynb` files tracked there.
- Experiment history is preserved and documented for future reference.

## References

- Original entry: phase-1 refactor decisions log (archived; see ADR-0032 and git tag `phase-1-refactor-archive`)
- Related backlog entry: RF-004
- Related document: `docs/notebooks/inventory.md`
