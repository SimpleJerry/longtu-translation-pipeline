# T-A6 · RF-007-P4 · Final held-out test report on checkpoint-48000

> Status: PENDING | Blocked-by: T-A5 / RF-006-P13 (DONE) | Parallel-safe with: T-B*, T-C*, T-D*, T-E*, T-F1
> Touches: `docs/refactor/backlog.md` (RF-007-P4 Notes); ignored `data/review/inference/test/`, ignored `data/review/evaluation/test_report/`
> **Worktree: DO NOT use.** `fine-tuned-models/` is gitignored and lives only in the main working directory — a worktree checkout will not contain checkpoint-48000 and `--model-path` will fail. Run in the main working directory.

## Why

RF-006-P13 (`run-full-earlystop-v1`) trained with early stopping on the
composite metric and stopped at step 49000. Step 6b post-hoc
full-validation (6,626 rows) re-ranked the 3 retained checkpoints and
selected **checkpoint-48000** (Branch (ii): full-val best ≠ trainer
auto-best 44000; 48000 beat 44000 by 0.0033 > ε, and 48000 vs 49000 was
within ε so the earlier 48000 won the tie-break).

This task runs the held-out **test** split (seed 42, 6,626 rows, never
seen during training and never used for checkpoint selection) once
against checkpoint-48000 to produce the project's current headline
quality number, recorded as RF-007-P4. RF-007-P3 stays as the historical
baseline (different corpus SHA256 + different training method); RF-007-P4
becomes the current published result.

## Prerequisites

1. RF-006-P13 DONE and committed (`89b3e2d`). ✓
2. Selected checkpoint = `checkpoint-48000` (from RF-006-P13 Step 6c).
3. Run in the **main working directory** (not a worktree) so the local
   checkpoint is reachable.
4. `HF_HOME` cache populated; GPU available (inference, ~38 min for one
   full test generation).

## Shared context (read these first)

- [ADR-0023](../../decisions/adr/ADR-0023-formal-experiments-use-held-out-test-splits.md) — Formal Experiments Use Held-Out Test Splits (test is used once, after checkpoint selection; iterating on test = leakage)
- [docs/refactor/backlog.md](../backlog.md) RF-006-P13 (the training +
  Step 6b/6c selection record) and RF-007-P4 (this entry, to fill)
- [docs/refactor/backlog.md](../backlog.md) RF-007-P3 (historical
  baseline to compare against, with the caveat that corpus + method
  differ)

## Files to read first

- `docs/refactor/backlog.md` RF-006-P13 Notes — confirm checkpoint-48000
  is the selected checkpoint and read the full-validation composite of
  48000 (needed for the val-vs-test sanity check)
- `scripts/run_inference.py` — `--generate-test` flag
- `configs/evaluation/generation_report.json` — the report config (same
  one used for RF-007-P3, reuse for comparability)
- `fine-tuned-models/nllb-200-distilled-600M/zh2ko/runs/run-full-earlystop-v1/run_manifest.json` — confirm `segments_sha256` and the test split path

## Don't touch

- Training configs / scripts / data — no training in this task
- `data/segments.csv` / `data/glossary.csv`
- Other checkpoints — test runs on 48000 only; do NOT test 44000/49000
  to "see if they're better" (that is test-set leakage)
- RF-007-P3 entry — keep as historical record

## Execution recipe

```powershell
$env:HF_HOME = "D:\longtu-translation-pipeline\venv\hf_cache"
$run  = "fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-full-earlystop-v1"
$ckpt = "$run\checkpoint-48000"

# 1. Generate on the held-out TEST split (full, max_length=400 from inference config)
venv\Scripts\python.exe scripts\run_inference.py `
    --generate-test `
    --run-dir $run `
    --model-path $ckpt

# Output: data/review/inference/test/run-full-earlystop-v1/test_generated.csv

# 2. Evaluate (single run, no iteration)
venv\Scripts\python.exe scripts\evaluate_translation.py `
    --config configs\evaluation\generation_report.json `
    --checkpoint $ckpt

# Output: data/review/evaluation/test_report/run-full-earlystop-v1/checkpoint-48000/
#   evaluation_summary.csv, glossary_preservation_rows.csv,
#   sample_review.csv, report_manifest.json
```

## What to record in RF-007-P4 Notes

| Metric | Test (ckpt-48000) | Full-val (ckpt-48000, from RF-006-P13 Step 6b) | Δ (test − val) |
|--------|-------------------|------------------------------------------------|----------------|
| BLEU (whitespace) | FILL | FILL | FILL |
| glossary_preservation_rate (exact) | FILL | FILL | FILL |
| glossary_preservation_rate_nospace | FILL | FILL | FILL |
| empty_candidate_rows | FILL | FILL | FILL |

Plus:
- Selected checkpoint path
- `data/segments.csv` SHA256 at run time = `30D5C299828C10235AEE357E9333740913E55C291C5B07A45C0739E41818EA97` (must match run_manifest.json)
- Test rows (6,626) + sample review row count
- Comparison vs RF-007-P3 historical (ckpt-9000: BLEU 0.1979, preserv_nospace 0.7975) — **note explicitly that RF-007-P3 used a different corpus SHA256 (`1462B2E1…`) and the old fixed-10k training, so this is "current model vs historical baseline" not a controlled ablation**
- Sanity check: test and full-val should be in the same ballpark; if test is wildly different from val, investigate before declaring
- Statement: "RF-007-P4 supersedes RF-007-P3 as the current published result. Any future change to `data/segments.csv` SHA256 invalidates this report."

## Acceptance criteria

1. `data/review/evaluation/test_report/run-full-earlystop-v1/checkpoint-48000/` contains the four report files.
2. `report_manifest.json` records checkpoint-48000 and segments_sha256 `30D5C299…`.
3. Test generated exactly once on checkpoint-48000; no other checkpoint tested.
4. RF-007-P4 backlog Notes carry the test/val comparison table + the RF-007-P3 comparison + the supersede statement.
5. RF-007-P4 Status set to `DONE`.
6. No files added to Git beyond `docs/refactor/backlog.md`.

## Verification

```powershell
Get-Content "data\review\evaluation\test_report\run-full-earlystop-v1\checkpoint-48000\evaluation_summary.csv"
Get-Content "data\review\evaluation\test_report\run-full-earlystop-v1\checkpoint-48000\report_manifest.json" | ConvertFrom-Json | Format-List
git -c safe.directory=D:/longtu-translation-pipeline status --short
```

## Git workflow

- One commit, doc-only. Message: `Record RF-007-P4 final test report on checkpoint-48000`.
- Do not push without explicit user confirmation.
- After this, Track A is complete on the current corpus. Research
  extensions (T-F2/F3/F4/F5) can build on this baseline.
