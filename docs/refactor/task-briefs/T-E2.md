# T-E2 · RF-023 · README tri-language sync mechanism

> Status: PENDING | Blocked-by: none | Parallel-safe with: all others (this one is the only task editing README content beyond a one-line link)
> Touches: `README.md`, `README.en.md`, `README.zh-CN.md`, optionally `scripts/check_readme_sync.py` (new)
> Audit: P3-2 (2026-05-26)
> **Priority: low.** Only do this if continued tri-language maintenance is committed.

## Why

`README.md` (zh-CN), `README.en.md`, `README.zh-CN.md` are 17-20 KB
each and carry overlapping numbers (row counts, split counts) and
command examples. Any data-state change requires manually editing
three files; the audit flagged drift risk.

This task introduces ONE of two sync strategies. Pick A by default.

## Prerequisites

- None.

## Shared context (read these first)

- [docs/refactor/audit-2026-05-26.md](../audit-2026-05-26.md) §P3-2
- [docs/refactor/decisions.md](../decisions.md) §2026-05-17 "README
  and AGENTS Do Not Carry Long-Term Task Pools" — confines README to
  intro/setup/usage/nav; corpus numbers belong in
  `docs/refactor/backlog.md`

## Files to read first

- All three README files end-to-end to inventory the duplicated
  content: row counts, split counts, command examples, file paths
- [docs/refactor/backlog.md](../backlog.md) — the canonical source
  of corpus numbers (RF-015 follow-up etc.)
- [docs/data-cleaning.md](../../data-cleaning.md) — canonical for
  cleaning rules

## Strategy A (recommended) — Centralize numbers

1. Identify every concrete number in the three READMEs (row counts,
   split counts, SHA256 values, etc.). Inventory them in a working
   note.
2. For each, replace the number with a brief reference like
   "current row count and gate state are recorded in
   [docs/refactor/backlog.md](docs/refactor/backlog.md) (RF-015)".
3. Keep structural prose (setup, workflow narrative) in each language;
   only numerical facts get centralized.

## Strategy B — Doc-sync check script

Create `scripts/check_readme_sync.py` that:
- Reads each README, extracts numeric tokens from a known set of
  context anchors (e.g. lines following "segments rows", "split
  counts")
- Compares them across the three READMEs and exits non-zero if any
  mismatch
- Designed to run in CI / as a pre-commit check

This is **not** a substitute for Strategy A; it just catches drift.
Choose B if the user wants to preserve current per-language numerical
prose.

## Don't touch

- Refactor backlog content — refer to it, don't duplicate it
- Code, configs, data
- AGENTS.md

## Acceptance criteria

### If Strategy A
1. The three READMEs no longer carry their own copy of corpus row
   counts, split counts, or SHA256 strings.
2. Each previously-numeric mention links to backlog.md (or
   data-cleaning.md) instead.
3. Setup / workflow prose in each language is preserved.
4. Backlog entry RF-023 set to `DONE`.

### If Strategy B
1. `scripts/check_readme_sync.py` exists and runs to completion.
2. Running it on the current trees exits with code `0`.
3. README content unchanged (Strategy B does not modify them).
4. Backlog entry RF-023 set to `DONE` with the check command recorded.

## Verification

```powershell
# Strategy A
rg -n "66,?385|3,?396|SHA256" README.md README.en.md README.zh-CN.md
# Expect: no concrete corpus numbers; only links to backlog.md.

# Strategy B
venv\Scripts\python.exe scripts\check_readme_sync.py
# Expect: exit 0.

# Both strategies
venv\Scripts\python.exe -m unittest discover -s tests
git -c safe.directory=D:/longtu-translation-pipeline diff --check
```

## Git workflow

- One commit, message reflects the strategy chosen:
  - Strategy A: `Centralize corpus numbers; link READMEs to backlog (RF-023)`
  - Strategy B: `Add README tri-language sync check (RF-023)`
- Do not push.
- Update RF-023 status to `DONE` in the same commit.
