# T-F1 · RF-024 · Add chrF metric to evaluation report

> Status: PENDING | Blocked-by: none (can backfill on historical reports immediately) | Parallel-safe with: all others except other evaluation.py edits
> Touches: `src/longtu_translation_pipeline/evaluation.py`, `configs/evaluation/*.json`, `tests/test_evaluation.py`, README evaluation section

## Why

The project currently reports BLEU + glossary preservation (exact +
no-space). chrF (character n-gram F-score) is a complementary metric
that is known to correlate better with human judgment than BLEU on
morphologically rich languages like Korean. It needs no external
model — pure computation — so it can be added independently of any
training run, and can backfill historical generation CSVs.

## Prerequisites

- None for the implementation work.
- A historical generation CSV (e.g. from RF-006-P6 pilot or any
  validation report) is enough to verify the new metric on real data.

## Shared context (read these first)

- [docs/refactor/decisions.md](../decisions.md) §2026-05-24
  "Evaluation Uses BLEU and Glossary Preservation Only" — this task
  *expands* but does not replace the current contract
- [docs/refactor/backlog.md](../backlog.md) RF-007, RF-007-P2

## Files to read first

- `src/longtu_translation_pipeline/evaluation.py` —
  `compute_corpus_bleu`, `evaluate_translation`,
  `format_evaluation_summary`, the `EvaluationResult` dataclass
- `tests/test_evaluation.py` — test style for BLEU
- `configs/evaluation/default.json`,
  `configs/evaluation/generation_report.json` — where to add a
  switch like `"chrf_enabled": true`

## Don't touch

- BLEU implementation (don't change existing numbers)
- Glossary preservation logic
- Training, inference, data files

## Modification surface

1. In `evaluation.py`:
   - Add `compute_chrf(references, candidates, ...)` using the
     standard chrF formula (character n-grams n=6 by default, beta=2
     for chrF, beta=2 for chrF++; pick one — chrF is most common).
     A small pure-Python implementation (~30-50 lines) is fine; no
     dependency on `sacrebleu` unless the user is OK pinning it.
     Decide in your commit message.
   - Add `chrf` (and optionally `chrf_plus`) to `EvaluationResult`.
   - `format_evaluation_summary` writes a new row for chrF in
     `evaluation_summary.csv`.
2. In configs: add a `chrf` toggle / parameters (n, beta). Default
   on.
3. In `tests/test_evaluation.py`: add at least:
   - chrF on exact matches → 1.0
   - chrF on completely different strings → near 0
   - chrF on partial matches → between 0 and 1, with a known
     reference value for a small fixture (verify against an
     authoritative chrF reference)
4. README: brief mention of the new metric.

### Recommended: use sacrebleu

If the user is OK with adding `sacrebleu==2.x` to
`requirements.txt`, use `sacrebleu.metrics.CHRF` for correctness. Add
the dep in this same RF (clear and traceable). Run `python -m
sacrebleu --version` to confirm.

If pure-Python is preferred, the formula is well documented; just
make sure your test fixture matches an authoritative reference.

## Acceptance criteria

1. `evaluation_summary.csv` written by `evaluate_translation.py`
   contains a chrF row.
2. `compute_chrf` is unit-tested (3+ assertions).
3. Existing BLEU / glossary preservation numbers in existing reports
   are unchanged.
4. Backfill: at least one historical generation CSV is re-evaluated
   and the new report is dropped into
   `data/review/evaluation/<old-path>/chrf-backfill/` for reference.
5. `python -m unittest discover -s tests` passes.
6. Backlog entry RF-024 set to `DONE`.

## Verification

```powershell
venv\Scripts\python.exe -m unittest tests.test_evaluation -v
# Quick smoke: backfill on the pilot report
venv\Scripts\python.exe scripts\evaluate_translation.py `
    --config configs\evaluation\generation_report.json `
    --checkpoint fine-tuned-models\nllb-200-distilled-600M\zh2ko\pilot\run-20260525-093832\checkpoint-4
Get-Content "data\review\evaluation\generation_report\evaluation_summary.csv"
# Expect: chrF row present.

venv\Scripts\python.exe -m unittest discover -s tests
git -c safe.directory=D:/longtu-translation-pipeline diff --check
```

## Git workflow

- One commit, message: `Add chrF metric to evaluation (RF-024)`.
- If sacrebleu was added to requirements.txt, mention it in the
  commit body.
- Do not push.
- Update RF-024 status to `DONE` in the same commit.
