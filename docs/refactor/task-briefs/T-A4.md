# T-A4 · RF-007-P3 · Held-out test report on selected checkpoint

> Status: PENDING | Blocked-by: T-A3 | Gates: T-F2..F5 | Parallel-safe with: T-B*, T-C*, T-D*, T-E*, T-F1
> Touches: nothing in Git (artifacts under ignored `data/review/`); `docs/refactor/backlog.md` (RF-007-P3 Notes)

## Why

After T-A3 produces validation reports, this task selects the best
checkpoint and runs the **test** split (the 10% held out at training
time, seed 42). The test report is the project's final model quality
claim for this `segments.csv` SHA256.

Per decisions, the test split is used **once** per model. Don't iterate
test-set results to find a "better" checkpoint after seeing test
numbers — that's data leakage. Pick the checkpoint from the
validation-curve evidence in T-A3, then run test once.

## Prerequisites

1. T-A3 committed; per-checkpoint validation reports exist.
2. User has confirmed the checkpoint to use (or the brief operator
   makes a defensible call from the validation table and gets it
   confirmed via plan or AskUserQuestion).

## Shared context (read these first)

- [ADR-0023](../../decisions/adr/ADR-0023-formal-experiments-use-held-out-test-splits.md) — Formal Experiments Use Held-Out Test Splits (8:1:1, seed=42)
- [ADR-0017](../../decisions/adr/ADR-0017-generation-evaluation-reports-are-local-artifacts.md) — Generation Evaluation Reports Are Local Engineering Artifacts (re-confirms that even the test report stays under ignored `data/review/`)
- [docs/refactor/backlog.md](../backlog.md) RF-006-P10 — test split
  generation flow, RF-007-P2 — sample-review + manifest

## Files to read first

- The validation report comparison table you wrote into RF-006-P12
  in T-A3
- `scripts/run_inference.py` — `--generate-test` flag
- `configs/evaluation/generation_report.json` — same config used for
  validation; reuse for consistency

## Don't touch

- Training configs / scripts / data
- Other checkpoints (no retroactive test reports after seeing this
  one)

## Execution recipe

```powershell
$run     = "fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-full-10k-llm-segments-v1"
$ckpt    = "$run\checkpoint-9000"   # whichever validation selected

# 1. Generate test CSV
venv\Scripts\python.exe scripts\run_inference.py `
    --generate-test `
    --run-dir $run `
    --model-path $ckpt

# Output: data/review/inference/test/run-full-10k-llm-segments-v1/test_generated.csv

# 2. Evaluate test
venv\Scripts\python.exe scripts\evaluate_translation.py `
    --config configs\evaluation\generation_report.json `
    --checkpoint $ckpt

# Output: data/review/evaluation/test_report/run-full-10k-llm-segments-v1/<checkpoint>/
#   evaluation_summary.csv, glossary_preservation_rows.csv,
#   sample_review.csv, report_manifest.json
```

## What to record in backlog RF-007-P3

The final report block in the backlog must include:

- The selected checkpoint path
- `data/segments.csv` SHA256 at run time (must match manifest)
- Test BLEU (corpus, with the configured tokenization)
- Test glossary_preservation_rate (exact)
- Test glossary_preservation_rate_nospace
- Test empty_candidate_rows
- Sample review row count
- Comparison vs. validation (for the same checkpoint), as a sanity
  check that test and validation are in the same ballpark

End with a sentence:
> Any future re-training on a different `segments.csv` SHA256
> invalidates this test report. Re-run T-A1 → T-A4 in order.

## Acceptance criteria

1. `data/review/evaluation/test_report/.../<checkpoint>/` exists with
   the four files.
2. `report_manifest.json` records the selected checkpoint and the
   corpus SHA256.
3. Backlog entry RF-007-P3 set to `DONE` with the final number block.
4. The test report is run **once** for the selected checkpoint, not
   iterated.
5. **No files added to Git** beyond `docs/refactor/backlog.md`.

## Verification

```powershell
Get-Content "data\review\evaluation\test_report\run-full-10k-llm-segments-v1\checkpoint-9000\evaluation_summary.csv"
Get-Content "data\review\evaluation\test_report\run-full-10k-llm-segments-v1\checkpoint-9000\report_manifest.json" | ConvertFrom-Json | Format-List
git -c safe.directory=D:/longtu-translation-pipeline status --short
```

## Git workflow

- One commit, doc-only. Message: `Record RF-007-P3 final test report on selected checkpoint`.
- Do not push.
- Update RF-007-P3 status to `DONE` in the same commit.

## After T-A4 finishes

Track A is complete. The repository now has a documented end-to-end
result for this `segments.csv` SHA256. T-F2..F5 can be picked up from
this baseline.
