# T-C1 · RF-016-P1 · Tests for `cleanup_common.py`

> Status: PENDING | Blocked-by: none | Parallel-safe with: all others
> Touches: `tests/test_cleanup_common.py` (new)
> Audit: P2-1 (2026-05-26)

## Why

`scripts/cleanup_common.py` is the foundational helper module
(60 LOC) shared by all five cleanup pipelines:
- `glossary_semantic_pipeline.py`
- `glossary_llm_cleanup_pipeline.py`
- `segments_cleaning_pipeline.py`
- `segments_glossary_cross_cleaning_pipeline.py`
- `segments_llm_cleanup_pipeline.py`

If any helper here regresses, all five pipelines silently break. It
currently has zero direct unit tests. This task adds fixture-level
tests covering happy path and error path for each helper, with no
external dependencies (no LLM, no embedding model, no stanza).

## Prerequisites

- None.

## Shared context (read these first)

- [docs/refactor/audit-2026-05-26.md](../audit-2026-05-26.md) §P2-1
- [AGENTS.md](../../../AGENTS.md) §Required Checks — `unittest
  discover` style
- Other tests in `tests/` — match their style (use stdlib `unittest`,
  `tempfile.TemporaryDirectory`, no external fixtures)

## Files to read first

- `scripts/cleanup_common.py` — all 60 lines. Helpers to test:
  - `sha256(path)` (lines 13-14)
  - `read_term_file(path, label)` (lines 17-37) — handles BOM,
    comments (`#`), empty lines, duplicates, empty result
  - `read_json_config(path)` (lines 40-47)
  - `compile_regexes(rules)` (lines 50-54)
  - `ensure_csv_columns(reader, required, path)` (lines 57-60)
- `tests/test_config.py` — example test style and use of
  `TemporaryDirectory`

## Don't touch

- `scripts/cleanup_common.py` — read-only for this task. If tests
  reveal a bug, file a separate RF; do not fix-and-test in one commit.
- Any pipeline script.

## Modification surface

Create **`tests/test_cleanup_common.py`** with at least:

### `sha256`
- known-content file produces known SHA256 (use a small fixed string)
- returns uppercase hex

### `read_term_file`
- happy path: 3 terms with BOM + trailing newline
- comments and blank lines are skipped
- duplicate term raises `RuntimeError` mentioning the line number
- empty file (after comment stripping) raises `RuntimeError`
- missing file raises `RuntimeError` mentioning the path

### `read_json_config`
- happy path: returns dict
- top-level JSON array raises `RuntimeError`
- missing file raises `RuntimeError`

### `compile_regexes`
- happy path: each pattern compiles to `re.Pattern`
- missing `regex` key raises
- empty `regex` dict raises

### `ensure_csv_columns`
- happy path: all required columns present, no exception
- missing column raises with the missing list and path

Use `tempfile.TemporaryDirectory()` for files. Use `io.StringIO` +
`csv.DictReader` for the `ensure_csv_columns` test (or write a small
real CSV file — either works).

## Acceptance criteria

1. `tests/test_cleanup_common.py` exists.
2. Each helper has at least one happy-path test and one error-path
   test (the suite should be ~12-15 test methods).
3. `python -m unittest tests.test_cleanup_common` passes.
4. `python -m unittest discover -s tests` total count goes up by the
   number of new tests; no existing test regresses.
5. Backlog entry RF-016-P1 set to `DONE`.

## Verification

```powershell
venv\Scripts\python.exe -m py_compile tests\test_cleanup_common.py
venv\Scripts\python.exe -m unittest tests.test_cleanup_common -v
venv\Scripts\python.exe -m unittest discover -s tests
git -c safe.directory=D:/longtu-translation-pipeline diff --check
```

## Git workflow

- One commit, message: `Add unit tests for scripts/cleanup_common (RF-016-P1)`.
- Do not push.
- Update RF-016-P1 status to `DONE` in the same commit.
