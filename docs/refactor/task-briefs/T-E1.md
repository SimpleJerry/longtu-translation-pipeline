# T-E1 · RF-022 · AGENTS.md unittest fix + RF-003 status update

> Status: PENDING | Blocked-by: none | Parallel-safe with: all others (avoid running alongside other AGENTS.md edits)
> Touches: `AGENTS.md`, `docs/refactor/backlog.md` (RF-003 section + RF-022 section)
> Audit: P3-1 + P2-4 (2026-05-26)

## Why

Two small, independent doc drift fixes bundled into one commit:

1. **P3-1**: `AGENTS.md` "Required Checks" tells agents to prefer
   `python -m pytest`, but the repo has no pytest config and all
   recommended test commands in `backlog.md` use
   `venv\Scripts\python.exe -m unittest discover -s tests`. Newcomers
   following AGENTS.md verbatim get an empty test run.
2. **P2-4**: `backlog.md` RF-003 (Data Pipeline Modularization) is
   `TODO`, but its Notes section already says the raw inputs and
   pipeline script are gone post-2026-05-19. Continuing to show
   `TODO` misleads task pickers.

## Prerequisites

- None.

## Shared context (read these first)

- [docs/refactor/audit-2026-05-26.md](../audit-2026-05-26.md) §P3-1 and §P2-4
- [AGENTS.md](../../../AGENTS.md) lines 51-55 — the pytest paragraph
- [docs/refactor/backlog.md](../backlog.md) RF-003 — the
  `Status: TODO` line + Notes paragraph

## Files to read first

- `AGENTS.md` end-to-end (it's short)
- `docs/refactor/backlog.md` lines 29-39 — RF-003

## Don't touch

- Any other section of AGENTS.md
- Any other RF in backlog.md (other than RF-003 and the new RF-022 entry)
- Code, configs, data

## Modification surface

### AGENTS.md — Required Checks paragraph
Replace the block:

```
When a full test suite exists, prefer:

    python -m pytest
```

with:

```
The full test suite uses Python's stdlib unittest:

    venv\Scripts\python.exe -m unittest discover -s tests

Individual tests can be run with `python -m unittest tests.<module>`.
```

### backlog.md — RF-003 status
Change `**Status:** TODO` to `**Status:** OBSOLETE`.

Append to RF-003 Notes:

> Closed on 2026-05-26 (RF-022): the raw xlsx inputs and the original
> `data/data-cleaning-and-merging.py` are not retained in this
> repository. A source-to-final data pipeline would only be useful if
> those raw inputs return; until then this item carries no actionable
> scope.

## Acceptance criteria

1. `AGENTS.md` "Required Checks" mentions `unittest discover`, not
   `pytest`.
2. `backlog.md` RF-003 status is `OBSOLETE` with the closing note.
3. `python -m unittest discover -s tests` still passes (no code
   change).
4. Backlog entry RF-022 (new) set to `DONE` with both edits recorded
   in its Notes.

## Verification

```powershell
rg -n "pytest" AGENTS.md
# Expect: no matches (or only in a comment explaining the legacy mention).
rg -n "unittest discover -s tests" AGENTS.md
# Expect: at least one match.
rg -n "^- \*\*Status:\*\* OBSOLETE" docs/refactor/backlog.md
# Expect: a match in the RF-003 section.
venv\Scripts\python.exe -m unittest discover -s tests
git -c safe.directory=D:/longtu-translation-pipeline diff --check
```

## Git workflow

- One commit, message: `Fix AGENTS.md test command + close RF-003 (RF-022)`.
- Do not push.
- Update RF-022 status to `DONE` in the same commit.
