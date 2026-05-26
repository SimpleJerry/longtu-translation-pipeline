# T-A2 · RF-006-P11 · Re-run formal 10k training on cleaned segments

> Status: PENDING | Blocked-by: T-A1 | Gates: T-A3 | Parallel-safe with: T-B*, T-C*, T-D*, T-E*, T-F1 (chrF backfill on historical)
> Touches: nothing in Git (all artifacts go under ignored `fine-tuned-models/`); `docs/refactor/backlog.md` (RF-006-P11 Notes)
> Audit: RF-015 follow-up note states all prior splits/checkpoints/reports are stale

## Why

After T-A1 changes `data/segments.csv`, every previous training run
under `fine-tuned-models/.../runs/run-*/` is invalid. The current
`segments_sha256` no longer matches any saved manifest. This task
re-runs the formal 10k training pipeline on the new corpus.

This is a long GPU run (hours), so it deserves its own conversation.
It must not be bundled with any data-changing task.

## Prerequisites

1. T-A1 committed and pushed to local main (do not push to origin).
2. `data/segments.csv` strict-check passes
   (`strict_current_mismatch_rows=0`).
3. `HF_HOME` cache populated (or be prepared for an initial NLLB
   model download).
4. GPU available with enough VRAM for `facebook/nllb-200-distilled-600M`.

## Shared context (read these first)

- [docs/refactor/decisions.md](../decisions.md) §2026-05-25 "Formal
  Training Runs Require Split Artifacts And Manifests", "Full
  Training Uses Explicit Profiles", "Formal Experiments Use Held-Out
  Test Splits"
- [docs/refactor/backlog.md](../backlog.md) RF-006-P9, RF-006-P10 —
  the established formal training and held-out test split machinery
- [docs/refactor/task-briefs/T-A1.md](T-A1.md) — predecessor task

## Files to read first

- `scripts/train_model.py` — `--train` path, especially how
  `--run-name` and `--run-dir` are resolved and the manifest schema
- `src/longtu_translation_pipeline/training.py` —
  `run_real_nllb_formal_training`, manifest writer
- `configs/training/full_10k.json` — confirm `max_steps=10000`,
  `save_steps=1000`, `eval_steps=5000`, learning_rate `2e-5`,
  warmup_ratio `0.03`, batch sizes
- The previous run manifest (if a stale one still exists under
  `fine-tuned-models/`) for schema reference only — DO NOT reuse

## Don't touch

- `configs/training/full_10k.json` — keep the hyperparameters
  identical to the previous baseline for comparability. If you want a
  different profile, file a new RF.
- `data/segments.csv`, `data/glossary.csv` — read-only
- Anything else in the repo

## Execution recipe

```powershell
$env:HF_HOME = "D:\longtu-translation-pipeline\venv\hf_cache"

# Pick a fresh run name. Convention:
#   run-full-10k-llm-segments-v1   (first run on the LLM-cleaned corpus)
#   run-full-10k-llm-segments-v2   (if you re-run after an interruption)

venv\Scripts\python.exe scripts\train_model.py `
    --config configs\training\full_10k.json `
    --train `
    --run-name run-full-10k-llm-segments-v1
```

Monitor:
- Loss curve via the training logs (every `logging_steps=100`)
- Checkpoint files under
  `fine-tuned-models/nllb-200-distilled-600M/zh2ko/runs/run-full-10k-llm-segments-v1/`
  at every 1000 steps
- `run_manifest.json` (after the run completes)

### Resume after interruption

If the run is interrupted (power, OOM, etc.):

```powershell
venv\Scripts\python.exe scripts\train_model.py `
    --config configs\training\full_10k.json `
    --train `
    --run-name run-full-10k-llm-segments-v1 `
    --resume-from-checkpoint
```

The script enforces that resume only proceeds if the manifest's
`segments_sha256` still matches `data/segments.csv`. If they differ,
abort — the corpus changed under you and resuming would be unsafe.

## What to record in backlog RF-006-P11

Create a new RF-006-P11 entry (if T-A1 didn't already) with:
- Run name and full path
- Final loss
- Total checkpoints saved (`checkpoint-1000`, `-2000`, ..., up to
  `-10000`)
- `segments_sha256` from the manifest
- Wall-clock training time
- Any deviations from baseline hyperparameters (should be zero)
- A note that validation report (T-A3) and test report (T-A4) are
  the next steps

## Acceptance criteria

1. `fine-tuned-models/.../runs/run-full-10k-llm-segments-v1/` exists.
2. `run_manifest.json` inside it contains:
   - `split_seed: 42`
   - `split_ratios: [0.8, 0.1, 0.1]`
   - `segments_sha256` matching the current `data/segments.csv`
   - Row counts consistent with the corpus row count
3. Checkpoints at expected step intervals (`save_steps=1000`).
4. Final step is `10000` (or the run terminated cleanly with a
   completion record).
5. Loss decreased monotonically-ish over the run (sanity check, not a
   hard pass criterion — record the curve).
6. Backlog entry RF-006-P11 set to `DONE` with the above recorded.
7. **No files added to Git** beyond `docs/refactor/backlog.md` —
   confirm with `git status --short` after the run.

## Verification

```powershell
$run = "fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-full-10k-llm-segments-v1"
Get-ChildItem $run -Filter "checkpoint-*" | Measure-Object
# Expect: at least 10 entries (1000, 2000, ..., 10000)

Get-Content "$run\run_manifest.json" | ConvertFrom-Json | Format-List

Get-Content "$run\splits\train.csv" -TotalCount 1
# Expect: header segment_id,zh-CN,ko

git -c safe.directory=D:/longtu-translation-pipeline status --short
# Expect: empty (or only docs/refactor/backlog.md).
```

## Git workflow

- One commit, doc-only, after the run completes. Message:
  `Record RF-006-P11 formal 10k training run on LLM-cleaned segments`.
- Do not push.
- Update RF-006-P11 status to `DONE` in the same commit.
