# T-A3 · RF-006-P12 · Validation generation + report on T-A2 checkpoints

> Status: PENDING | Blocked-by: T-A2 | Gates: T-A4 | Parallel-safe with: T-B*, T-C*, T-D*, T-E*, T-F1
> Touches: nothing in Git (all artifacts under ignored `data/review/`); `docs/refactor/backlog.md` (RF-006-P12 Notes)

## Why

After T-A2 finishes, the run directory has multiple checkpoints
(`checkpoint-1000`, `-2000`, ..., `-10000`). Validation-split
generation on each gives a comparable BLEU + glossary-preservation
curve, which is the basis for selecting the final checkpoint in T-A4.

Validation **is not** the final quality claim. It is the engineering
signal used to pick the checkpoint that T-A4 will then evaluate on
the held-out test split.

## Prerequisites

1. T-A2 committed; run directory exists with `run_manifest.json` and
   at least one `checkpoint-*`.
2. `HF_HOME` populated.
3. GPU available (inference is faster than training but still needs
   GPU).

## Shared context (read these first)

- [ADR-0021](../../decisions/adr/ADR-0021-validation-generation-uses-fixed-training-splits.md) — Validation Generation Uses Fixed Training Splits
- [ADR-0016](../../decisions/adr/ADR-0016-inference-output-stays-rf007-compatible.md) — Inference Output Stays RF-007-Compatible
- [ADR-0028](../../decisions/adr/ADR-0028-inference-uses-source-terminology-markers.md) — Inference Uses Source Terminology Markers
- [ADR-0029](../../decisions/adr/ADR-0029-glossary-preservation-reports-exact-and-nospace-metrics.md) — Glossary Preservation Reports Exact And No-Space Metrics
- [docs/refactor/backlog.md](../backlog.md) RF-006-P8 (validation
  generation flow), RF-007, RF-007-P2

## Files to read first

- `scripts/run_inference.py` — `--generate-validation`, `--run-dir`
- `scripts/evaluate_translation.py` — `--checkpoint`,
  `--config configs/evaluation/generation_report.json`
- `configs/inference/default.json` — confirm
  `source_terminology_markers=true`
- `configs/evaluation/generation_report.json` — confirm sample row
  count and report layout
- `src/longtu_translation_pipeline/evaluation.py` — both exact and
  no-space glossary preservation are computed

## Don't touch

- Training configs, training scripts
- `data/segments.csv`, `data/glossary.csv`
- The run directory itself, beyond reading checkpoints

## Execution recipe

For each saved checkpoint (or a strategically picked subset — at
minimum the last 3-4):

```powershell
$run = "fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-full-10k-llm-segments-v1"

# 1. Generate validation CSV (one-shot per run; consumes splits/validation.csv)
venv\Scripts\python.exe scripts\run_inference.py `
    --generate-validation `
    --run-dir $run

# Output: data/review/inference/validation/run-full-10k-llm-segments-v1/validation_generated.csv
# This generates with the LATEST checkpoint by default. To target a
# specific checkpoint, also pass --model-path:
#   --model-path "$run\checkpoint-9000"

# 2. Evaluate per checkpoint:
foreach ($ckpt in @("checkpoint-7000", "checkpoint-8000", "checkpoint-9000", "checkpoint-10000")) {
    venv\Scripts\python.exe scripts\run_inference.py `
        --generate-validation --run-dir $run `
        --model-path "$run\$ckpt"
    venv\Scripts\python.exe scripts\evaluate_translation.py `
        --config configs\evaluation\generation_report.json `
        --checkpoint "$run\$ckpt"
}

# Each evaluation writes under
# data/review/evaluation/validation_report/run-full-10k-llm-segments-v1/<checkpoint>/
# including evaluation_summary.csv, glossary_preservation_rows.csv,
# sample_review.csv, report_manifest.json
```

## What to record in backlog RF-006-P12

A comparison table across checkpoints:

| Checkpoint | BLEU | glossary_preservation_rate | glossary_preservation_rate_nospace | empty_candidate_rows |
|-----------|------|----------------------------|------------------------------------|----------------------|
| 7000 | ... | ... | ... | ... |
| 8000 | ... | ... | ... | ... |
| 9000 | ... | ... | ... | ... |
| 10000 | ... | ... | ... | ... |

Note any anomalies (sudden BLEU drop, preservation regression,
spike in empty_candidate_rows).

## Acceptance criteria

1. Each evaluated checkpoint has a directory under
   `data/review/evaluation/validation_report/.../<checkpoint>/` with
   the four files.
2. `report_manifest.json` in each records checkpoint path, source
   CSV, eval config, sample count.
3. Backlog entry RF-006-P12 set to `DONE` with the comparison table.
4. **Validation is not declared as the model quality.** A note in
   RF-006-P12 explicitly says this is engineering signal for T-A4
   checkpoint selection.
5. **No files added to Git** beyond `docs/refactor/backlog.md`.

## Verification

```powershell
Get-ChildItem "data\review\evaluation\validation_report" -Recurse -Filter "evaluation_summary.csv"
# Expect: one per evaluated checkpoint.

# Sanity: BLEU and preservation are in [0, 1]
foreach ($file in Get-ChildItem "data\review\evaluation\validation_report" -Recurse -Filter "evaluation_summary.csv") {
    Get-Content $file.FullName
}

git -c safe.directory=D:/longtu-translation-pipeline status --short
```

## Git workflow

- One commit, doc-only. Message: `Record RF-006-P12 validation reports across 10k-run checkpoints`.
- Do not push.
- Update RF-006-P12 status to `DONE` in the same commit.
