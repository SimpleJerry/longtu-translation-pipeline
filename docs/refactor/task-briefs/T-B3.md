# T-B3 · RF-019 · Clarify training default config

> Status: PENDING | Blocked-by: none | Parallel-safe with: all others
> Touches: `configs/training/default.json` (or `scripts/train_model.py`), README files
> Audit: P1-3 (2026-05-26)

## Why

`configs/training/default.json` has no `max_steps`, so
`scripts/train_model.py --train --config configs/training/default.json`
fails with a non-obvious error. But the script's CLI default for
`--config` is exactly `configs/training/default.json`, so a first-time
user typing `--train` lands on this pitfall.

This task adds an unmistakable marker that `default.json` is a
**dry-run / smoke** profile, not a full-train profile.

## Prerequisites

- None.

## Shared context (read these first)

- [docs/refactor/audit-2026-05-26.md](../audit-2026-05-26.md) §P1-3
- [ADR-0022](../../decisions/adr/ADR-0022-full-training-uses-explicit-profiles.md) — Full Training Uses Explicit Profiles (locks the rule that `--train` must use an explicit `max_steps` profile)

## Files to read first

- `configs/training/default.json` — confirm `max_steps` absence
- `configs/training/full_10k.json` — confirm it carries `max_steps`
- `scripts/train_model.py` — look at `--config` default and how
  `--train` validates `max_steps`
- `src/longtu_translation_pipeline/config.py` — `load_training_arguments_config`
  to confirm `max_steps` is not required at config-load time (it's
  enforced later by formal training)

## Don't touch

- `configs/training/full_10k.json` — leave it as the formal profile
- Any other config
- The split / tokenization / language settings — those stay shared

## Modification surface

**Recommended (smaller, compatible) option:**

1. `configs/training/default.json` — add at the top level (before
   `"data"`) a JSON field:
   ```json
   "_comment": "Dry-run / smoke / nllb-smoke / real-model-smoke profile. For --train use configs/training/full_10k.json."
   ```
   The `_` prefix means downstream `load_training_*` ignores it.
2. README files — if any README example shows `--train` against
   `default.json`, fix it to use `full_10k.json`.

**Alternative (larger) option:**

Change `scripts/train_model.py` so that `--train` requires
`--config configs/training/full_10k.json` (or any non-default explicit
config) and prints a helpful error otherwise. This is a behavior
change — only choose this option after confirming with the user.

## Acceptance criteria

1. `configs/training/default.json` carries a top-level `_comment` field
   marking it dry-run / smoke only.
2. No README example pairs `--train` with `default.json`.
3. `--dry-run`, `--smoke-test`, `--nllb-smoke-test`,
   `--real-model-smoke-test` paths still load `default.json` without
   issue.
4. `python -m unittest discover -s tests` passes.
5. Backlog entry RF-019 set to `DONE`.

## Verification

```powershell
venv\Scripts\python.exe -c "import json; d=json.load(open('configs/training/default.json', encoding='utf-8')); print('_comment' in d)"
# Expect: True
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --dry-run
# Expect: runs as before; comment is ignored
venv\Scripts\python.exe -m unittest discover -s tests
rg -n "train.*default.json" README.md README.en.md README.zh-CN.md
# Confirm no --train + default.json pairings remain.
git -c safe.directory=D:/longtu-translation-pipeline diff --check
```

## Git workflow

- One commit, message: `Annotate default.json as dry-run/smoke only (RF-019)`.
- Do not push.
- Update RF-019 status to `DONE` in the same commit.
