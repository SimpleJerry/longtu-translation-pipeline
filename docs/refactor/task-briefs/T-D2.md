# T-D2 · RF-021 · Archive deprecated notebooks

> Status: PENDING | Blocked-by: none | Parallel-safe with: all others (do not run alongside other notebook edits)
> Touches: `notebooks/main/` → `notebooks/archive/2023-legacy/`, `docs/notebooks/inventory.md`, README files
> Audit: P2-3 + P3-3 (2026-05-26)

## Why

Six notebooks under `notebooks/main/` are listed in
`docs/notebooks/inventory.md` and [ADR-0010](../../decisions/adr/ADR-0010-text-protection-uses-single-segment-term-markers.md) as
*deprecated*, but they still live in the active `main/` directory.
Anyone browsing `notebooks/main/` is misled into thinking these are
current. AGENTS.md "Do not leave docs implying an old behavior after
the code has changed" requires moving them to the archive.

## Prerequisites

- None.

## Shared context (read these first)

- [docs/refactor/audit-2026-05-26.md](../audit-2026-05-26.md) §P2-3 and §P3-3
- [ADR-0010](../../decisions/adr/ADR-0010-text-protection-uses-single-segment-term-markers.md) — Text Protection Uses Single-Segment Term Markers (T&N+R deprecated)
- [ADR-0009](../../decisions/adr/ADR-0009-notebook-deletion-requires-inventory-first.md) — Notebook Deletion Requires Inventory First
- [docs/notebooks/inventory.md](../../notebooks/inventory.md) —
  current per-notebook classification

## Files to read first

- `docs/notebooks/inventory.md` — find each deprecated notebook's row
  and its `Replacement Path`
- `notebooks/main/` directory listing — confirm the files are still
  there

## Files to move

Confirmed deprecated (move to `notebooks/archive/2023-legacy/`):

1. `notebooks/main/T&N+R method.ipynb`
2. `notebooks/main/T&N+R method code accuracy testing.ipynb`
3. `notebooks/main/T&N+R method glossary accuracy testing.ipynb`
4. `notebooks/main/T&N+R preprocess.ipynb`
5. `notebooks/main/nllb-fine-tune_all.ipynb` (replaced by
   `scripts/train_model.py`)
6. `notebooks/main/model-generation.ipynb` (replaced by
   `scripts/run_inference.py`)

Use `git mv` so history is preserved.

## Don't touch

- The notebook JSON contents — moves only, no internal edits.
- Other notebooks in `notebooks/main/` that are NOT in the above
  list.
- Notebooks in `notebooks/analysis/`.

## Modification surface

1. `git mv` each of the 6 notebooks from `main/` to
   `archive/2023-legacy/`.
2. `docs/notebooks/inventory.md`:
   - Update each row's "Location" column (or whatever the schema is)
   - Update each row's "Recommendation" column to reflect that the
     move has been done
3. Three READMEs (`README.md`, `README.en.md`, `README.zh-CN.md`):
   - Any link that explicitly points at `notebooks/main/<one of the
     moved files>` → update to `notebooks/archive/2023-legacy/...`
   - If there's a section listing "main flow notebooks", remove the
     moved files from that list (or describe them as archived)

## Acceptance criteria

1. None of the 6 notebooks remain in `notebooks/main/`.
2. All 6 are present under `notebooks/archive/2023-legacy/`.
3. `docs/notebooks/inventory.md` reflects the new locations.
4. Three READMEs are consistent.
5. `git log --follow` works on each moved notebook (i.e. git tracked
   the move as a rename, not delete + add).
6. `python -m unittest discover -s tests` passes (no test should
   reference these paths, but verify).
7. Backlog entry RF-021 set to `DONE`.

## Verification

```powershell
Get-ChildItem notebooks/main -Filter "*.ipynb" | Where-Object { $_.Name -like "*T&N+R*" -or $_.Name -in @('nllb-fine-tune_all.ipynb', 'model-generation.ipynb') }
# Expect: no output.
Get-ChildItem notebooks/archive/2023-legacy -Filter "*.ipynb" | Measure-Object
# Expect count: original count + 6.
rg -n "notebooks/main/T&N|notebooks/main/nllb-fine-tune_all|notebooks/main/model-generation" README.md README.en.md README.zh-CN.md docs/notebooks/inventory.md
# Expect: no matches.
venv\Scripts\python.exe -m unittest discover -s tests
git -c safe.directory=D:/longtu-translation-pipeline status --short
git -c safe.directory=D:/longtu-translation-pipeline diff --check
```

## Git workflow

- Two commits acceptable:
  1. `Archive deprecated T&N+R and replaced notebooks (RF-021)` —
     `git mv` only
  2. `Update notebook inventory and README links (RF-021)` — doc edits
- Or a single bundled commit if cleaner.
- Do not push.
- Update RF-021 status to `DONE` in the final commit.
