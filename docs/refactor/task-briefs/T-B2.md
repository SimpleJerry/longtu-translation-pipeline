# T-B2 · RF-018 · Consolidate torch pinning in requirements

> Status: PENDING | Blocked-by: none | Parallel-safe with: all others except other requirements edits
> Touches: `requirements.txt`, `requirements-training.txt`, README files (torch mentions)
> Audit: P1-2 (2026-05-26)

## Why

Both `requirements.txt` and `requirements-training.txt` pin
`torch==2.12.0+cu132` and `torchvision==0.27.0+cu132`, plus the same
`--extra-index-url https://download.pytorch.org/whl/cu132`. Two
pinnings make upgrades non-atomic — if one file gets bumped and the
other doesn't, pip behavior becomes non-deterministic.

This task removes the duplicate pin from `requirements.txt` so torch
lives only in `requirements-training.txt`.

## Prerequisites

- None.

## Shared context (read these first)

- [docs/refactor/audit-2026-05-26.md](../audit-2026-05-26.md) §P1-2
- [docs/refactor/backlog.md](../backlog.md) RF-008 — original
  dependency split decision (keeps base/training separation lightweight)

## Files to read first

- `requirements.txt` (lines 1, 9, 10) — the duplicate pin and extra-index-url
- `requirements-training.txt` (lines 1, 2, 3) — same pin to keep here
- README files — any explicit `pip install` instruction that mentions
  torch

## Don't touch

- `venv/` — do not actually `pip install` anything; this is a file-only
  change. Users will rebuild env on their own schedule.
- Any other package pin.

## Modification surface

1. `requirements.txt`:
   - Remove `torch==2.12.0+cu132`
   - Remove `torchvision==0.27.0+cu132`
   - Remove the `--extra-index-url https://download.pytorch.org/whl/cu132`
     line (since the remaining packages don't need it)
2. `requirements-training.txt`:
   - Keep the existing torch/torchvision pins and the extra-index-url.
   - At the top, add a one-line comment: `# Install requirements.txt
     first, then this file: pip install -r requirements.txt -r
     requirements-training.txt`
3. Update README torch/install sections (search all three READMEs for
   "torch" or "cu132" mentions) to clarify the install order is:
   ```
   pip install -r requirements.txt
   pip install -r requirements-training.txt   # only if you need training
   ```

## Acceptance criteria

1. `requirements.txt` does not contain `torch`, `torchvision`, or
   `cu132`.
2. `requirements-training.txt` still contains the torch/torchvision
   pins and extra-index-url.
3. Three READMEs describe the install order consistently.
4. `python -m unittest discover -s tests` passes (no code change should
   affect tests).
5. Backlog entry RF-018 set to `DONE`.

## Verification

```powershell
rg -n "torch|cu132" requirements.txt
# Expect: no matches.
rg -n "torch==|torchvision==" requirements-training.txt
# Expect: both lines present.
rg -n -i "torch|cu132|extra-index-url" README.md README.en.md README.zh-CN.md
# Confirm the install order is documented in all three.
venv\Scripts\python.exe -m unittest discover -s tests
git -c safe.directory=D:/longtu-translation-pipeline diff --check
```

## Git workflow

- One commit, message: `Consolidate torch pin into requirements-training.txt (RF-018)`.
- Do not push.
- Update RF-018 status to `DONE` in the same commit.
