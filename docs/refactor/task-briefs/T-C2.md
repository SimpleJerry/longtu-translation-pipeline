# T-C2 · RF-016-P2 · Tests for `segments_cleaning_pipeline.py`

> Status: PENDING | Blocked-by: T-C1 recommended (cleaner foundation) but not required | Parallel-safe with: all others
> Touches: `tests/test_segments_cleaning_pipeline.py` (extend existing)
> Audit: P2-1 (2026-05-26)

## Why

`scripts/segments_cleaning_pipeline.py` is 1,150 LOC; the existing
`tests/test_segments_cleaning_pipeline.py` has 4 test methods / 10
assertions covering only fragment removal and target contamination.
Untested: markup stripping, symmetric wrapper unwrap, structured
tuple split, placeholder mismatch audit, semantic-noise scoring entry
points (the parts that don't need external models).

This task adds fixture-level tests for the *deterministic, pure-Python*
branches of those features. It does **not** introduce stanza / jieba /
kiwi / bge-m3 in tests.

## Prerequisites

- None (T-C1 helps but is not required).

## Shared context (read these first)

- [docs/refactor/audit-2026-05-26.md](../audit-2026-05-26.md) §P2-1
- [ADR-0013](../../decisions/adr/ADR-0013-segment-cleanup-is-review-first.md) — Segment Cleanup Is Review-First
- [ADR-0027](../../decisions/adr/ADR-0027-segment-fragments-and-target-contamination-are-training-noise.md) — Segment Fragments And Target Contamination Are Training Noise
- [docs/architecture/data-cleaning-pipeline.md](../../architecture/data-cleaning-pipeline.md) — markup, wrapper, structured tuple, placeholder rules

## Files to read first

- `scripts/segments_cleaning_pipeline.py` — focus on:
  - Markup stripping (presentation tags like `<c=red>...</c>`)
  - Symmetric wrapper unwrap (e.g., outer `{"..."}`)
  - Structured tuple split logic
  - Placeholder regex / mismatch detection
  - The `AUTO_REMOVE_NON_SEGMENT_FRAGMENT` and
    `AUTO_REMOVE_TARGET_LANGUAGE_CONTAMINATION` paths
- `tests/test_segments_cleaning_pipeline.py` — current 4 tests, match
  their style and use of fixtures
- `configs/segments/rules.json` — regex names used by the script

## Don't touch

- The pipeline implementation. If a test reveals a bug, file a
  separate RF item; don't bundle fix + test.
- `data/segments.csv` / `data/glossary.csv`.
- Anything that needs stanza / jieba / kiwi / bge-m3 / wordfreq — skip
  semantic *scoring* tests; only cover the rule-based branches.

## Modification surface

Extend **`tests/test_segments_cleaning_pipeline.py`** with at least:

### Markup stripping
- `<c=red>foo</c>` → `foo` (color tag stripped, content kept)
- nested `<size=12><b>foo</b></size>` → `foo`
- `2%` and percentage characters are preserved
- bare hex `<#ff0000>` style tags handled per `configs/segments/rules.json`

### Symmetric wrapper unwrap
- outer quotes `{"foo"}` → `foo`
- nested wrappers handled per rules
- asymmetric wrapper is NOT unwrapped

### Structured tuple split
- well-formed aligned tuple splits into N child rows with continuous IDs
- malformed/unaligned tuple is flagged for review, not split

### Placeholder mismatch
- source has `{0}{1}`, target has `{0}` → flagged
- source has `{0}`, target has `{0}{1}` → flagged
- source and target both `{0}{1}` → not flagged

### Non-segment fragment
- pure single-char CJK `艮` → removed
- single-char CJK with placeholder `艮{0}` → kept (placeholder makes
  it segment-shaped)
- the 2-3 char migration is **not** retested here (it's a one-time
  historical event, see decisions §2026-05-26)

### Target contamination
- `ko` contains CJK → removed
- `ko` has no Hangul at all → removed
- `ko` is empty → removed (existing behavior)
- `ko` is valid Hangul → kept

Target: end up with **at least 30 assertions** total in this file.

## Acceptance criteria

1. New test methods cover the five branches above.
2. No external model is loaded during the suite (run on a machine
   without GPU / without HF cache).
3. `python -m unittest tests.test_segments_cleaning_pipeline` passes
   in < 30 s.
4. `python -m unittest discover -s tests` total count goes up.
5. Backlog entry RF-016-P2 set to `DONE` with the new assertion
   count recorded.

## Verification

```powershell
venv\Scripts\python.exe -m unittest tests.test_segments_cleaning_pipeline -v
venv\Scripts\python.exe -m unittest discover -s tests
git -c safe.directory=D:/longtu-translation-pipeline diff --check
```

## Git workflow

- One commit, message: `Extend segments_cleaning_pipeline tests (RF-016-P2)`.
- Do not push.
- Update RF-016-P2 status to `DONE` in the same commit.
