# T-C3 · RF-016-P3 · Tests for `glossary_semantic_pipeline.py`

> Status: PENDING | Blocked-by: T-C1 recommended (foundation) but not required | Parallel-safe with: all others
> Touches: `tests/test_glossary_semantic_pipeline.py` (new)
> Audit: P2-1 (2026-05-26)

## Why

`scripts/glossary_semantic_pipeline.py` is 1,502 LOC with **zero
unit tests** — the single largest untested module in the repo. It
combines Stanza / jieba / kiwi / bge-m3 / wordfreq with deterministic
rule-based filtering. Many of its decision branches are *pure Python*
(string/regex/list comprehension level) and testable without any of
those external dependencies.

This task adds a first wave of fixture-level tests for the pure logic
branches. It does **not** try to cover the embedding / POS / Zipf
scoring paths.

## Prerequisites

- None.

## Shared context (read these first)

- [docs/refactor/audit-2026-05-26.md](../audit-2026-05-26.md) §P2-1
- [ADR-0007](../../decisions/adr/ADR-0007-segment-evidence-not-sufficient-glossary-keep-signal.md) — Segment Evidence Is Not a Sufficient Glossary Keep Signal
- [ADR-0008](../../decisions/adr/ADR-0008-glossary-pipeline-uses-final-glossary-as-baseline.md) — Glossary Pipeline Uses Final Glossary As Baseline
- [docs/refactor/backlog.md](../backlog.md) RF-010 follow-up notes —
  history of what each rule was added for

## Files to read first

- `scripts/glossary_semantic_pipeline.py` — read end-to-end once,
  then focus on the **pure-logic** functions. Likely candidates:
  - Hard noise filters (numeric-only, Hangul in zh-CN column,
    structural noise like `+7`, `VIP等级不足`, Korean-only zh)
  - `enforce_strict_pairs` (or whatever enforces 1:1 zh-CN ↔ ko)
  - `classify_rows` (the dispatch that emits AUTO_KEEP /
    AUTO_REMOVE / KEEP_UNCERTAIN buckets, only the rule-driven
    branches)
  - `not_in_segments_redundant_for_current_corpus` decision (string
    presence check against segments.csv text — easy to fixture)
  - Config / seed file loading helpers
- `configs/glossary/rules.json`, `configs/glossary/*.txt` — what
  the pipeline reads
- `tests/test_segments_cleaning_pipeline.py` — borrow fixture style

## Don't touch

- The pipeline implementation. Any bug uncovered → separate RF.
- `data/glossary.csv` / `data/segments.csv`.
- The embedding / POS / Zipf code paths. Either skip them in tests
  or mock them; do **not** download or load real models.

## Modification surface

Create **`tests/test_glossary_semantic_pipeline.py`** with at least:

### Hard noise filters
- `+7 / 강화 +7` → flagged as structural noise (zh value is sign + digits)
- `VIP等级不足 / VIP 레벨 부족` → flagged or not depending on the
  current rule (read the code first; record the actual rule
  outcome — this is a regression lock, not a redesign)
- Korean-only `zh-CN` value → flagged as structural noise
- Hangul present in `zh-CN` column → flagged

### Strict 1:1 enforcement
- single zh-CN with one ko → kept
- single zh-CN with two different ko forms → conflict (whatever the
  current behavior is — lock it)
- single ko with two different zh-CN forms → conflict (lock it)
- duplicate identical (zh-CN, ko) pair → merged or deduped per
  current behavior

### Product-corpus evidence gate
- term whose `zh-CN` appears in segments → not removed for
  "not_in_segments"
- term whose neither side appears in segments → removed as
  `not_in_segments_redundant_for_current_corpus`

### Config / seed file loading
- helper that reads `configs/glossary/game_term_seeds.txt` returns
  the expected list (use a tiny temp file fixture, not the real one)
- helper raises clearly when a seed file is empty/missing (delegates
  to `cleanup_common.read_term_file` — confirm the wiring works)

### Boundary cases
- empty input glossary → returns empty result, no crash
- glossary with only header → returns empty result

## Mocking guidance

If a pure-logic function calls into an embedding/POS routine,
inject a tiny fake (lambda / `unittest.mock.patch`) that returns
fixed scores. Do **not** instantiate `SentenceTransformer`,
`stanza.Pipeline`, `jieba`, `kiwipiepy.Kiwi`, or `wordfreq.zipf_frequency`
in the test. If a target function is too tangled to fake cheaply,
skip it for this RF and note it in the backlog notes.

## Acceptance criteria

1. `tests/test_glossary_semantic_pipeline.py` exists with at least
   12 test methods covering the four buckets above.
2. The suite runs in < 30 s on a machine without GPU, without HF
   cache, without stanza_resources.
3. `python -m unittest discover -s tests` total count goes up; no
   regressions.
4. Backlog entry RF-016-P3 set to `DONE`. If any branch was too
   tangled to test, list it explicitly under Notes for future P4.

## Verification

```powershell
venv\Scripts\python.exe -m unittest tests.test_glossary_semantic_pipeline -v
venv\Scripts\python.exe -m unittest discover -s tests
git -c safe.directory=D:/longtu-translation-pipeline diff --check
```

## Git workflow

- One commit, message: `Add first-wave tests for glossary_semantic_pipeline (RF-016-P3)`.
- Do not push.
- Update RF-016-P3 status to `DONE` (or `PARTIAL` if some branches
  deferred) in the same commit.
