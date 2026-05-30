# ADR-0022: Full Training Uses Explicit Profiles

- Status: Accepted
- Date: 2026-05-25

## Context

Moving from engineering smoke tests to staged full-data training introduced a risk: if formal
`--train` inherited small-step defaults from smoke/pilot configs, it could waste GPU hours or
produce ambiguous manifests where it was unclear whether the run was a smoke or a real training
run.

## Decision

Formal full-data training must use an explicit config profile or CLI override for key training
parameters; `--train` must not inherit small-step smoke/pilot defaults.

The first staged profile:
- File: `configs/training/full_10k.json`
- `max_steps=10000`, `save_steps=1000`, `eval_steps=5000`, `save_total_limit=6`

Later longer runs or early-stopping runs add new named profiles (e.g., `full_earlystop.json`)
rather than relying on remembered CLI parameters. Old profiles are preserved as historical
baselines and must not be deleted.

## Consequences

- `--train` rejects configs that lack `max_steps` unless CLI provides it (for `full_10k`
  style profiles; `full_earlystop` uses `num_train_epochs` instead).
- `full_10k.json` is preserved as a historical baseline even after early-stopping replaced
  it as the default approach (see [[ADR-0031]]).
- `save_steps` and `eval_steps` are separate settings.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entries: RF-006-P9, RF-006-P11
- Related code: `configs/training/full_10k.json`, `configs/training/full_earlystop.json`
