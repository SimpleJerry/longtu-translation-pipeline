# T-F3 · RF-026 · NLLB-1.3B / 3.3B base model experiment

> Status: PENDING (optional research) | Blocked-by: T-A4 (baseline test report required for comparison) | Parallel-safe with: most others, but the GPU is the bottleneck
> Touches: new `configs/training/full_10k_nllb_1.3b.json` (and possibly `_3.3b.json`); `configs/inference/nllb_1.3b.json`; `docs/refactor/backlog.md` (RF-026 Notes)

## Why

After T-A4 establishes a baseline test report on the
`facebook/nllb-200-distilled-600M` model, the next question is whether
a larger base (1.3B / 3.3B) improves zh→ko quality enough to justify
the cost. This task runs the same training and evaluation pipeline
with a swapped base model, **keeping segments / split / seed / marker
shape identical** so the result is directly comparable.

## Prerequisites

1. T-A4 committed (baseline test numbers exist).
2. GPU with enough VRAM for `facebook/nllb-200-1.3B` (needs ~24 GB
   for full fine-tune; consider LoRA if not). For `nllb-200-3.3B`
   the requirement is steeper.
3. User has authorized the additional GPU time.

## Shared context (read these first)

- [ADR-0022](../../decisions/adr/ADR-0022-full-training-uses-explicit-profiles.md) — Full Training Uses Explicit Profiles (new named profiles are the right way to introduce model variants)
- [docs/refactor/backlog.md](../backlog.md) RF-006-P11 (the baseline
  600M run that this compares against)
- HuggingFace NLLB model cards for 1.3B/3.3B variants

## Files to read first

- `configs/training/full_10k.json` — the 600M profile to clone
- `src/longtu_translation_pipeline/training.py` — confirm
  `base_model` is plumbed through and `<start>/<end>` token-resize is
  base-model-agnostic
- `scripts/train_model.py` — confirm `--config` accepts a different
  profile
- `configs/inference/default.json` — confirm inference also reads
  `base_model` from the config

## Don't touch

- `configs/training/full_10k.json` — keep the 600M baseline intact
- `data/segments.csv`, `data/glossary.csv` — same corpus
- `seed`, `train_ratio`, `validation_ratio`, `test_ratio` — must
  stay 42 and 8:1:1
- Marker shape — must stay `<start>...<end>`
- Other model families — this RF is NLLB-only

## Modification surface

1. Create `configs/training/full_10k_nllb_1.3b.json`:
   - Same as `full_10k.json` except `"base_model":
     "facebook/nllb-200-1.3B"`
   - Optionally lower batch size and/or add gradient accumulation if
     VRAM-constrained
   - Same `max_steps=10000`; if compute-limited, document the
     deviation in the run notes
2. (Optional) `configs/training/full_10k_nllb_3.3b.json` analogous
3. Create `configs/inference/nllb_1.3b.json` pointing at the new run
   directory shape
4. Run the new training:
   ```powershell
   $env:HF_HOME = "D:\longtu-translation-pipeline\venv\hf_cache"
   venv\Scripts\python.exe scripts\train_model.py `
       --config configs\training\full_10k_nllb_1.3b.json `
       --train `
       --run-name run-full-10k-nllb-1.3b-v1
   ```
5. Validation + test (analogous to T-A3 + T-A4) on the new run
6. Record comparison in backlog RF-026:
   - Baseline 600M (from T-A4)
   - 1.3B (this run)
   - (Optional) 3.3B
   For each: BLEU, chrF, glossary preservation (exact +
   no-space), empty_candidate_rows, training time, peak VRAM, total
   parameters

## Acceptance criteria

1. New config file(s) under `configs/training/` and
   `configs/inference/`
2. New run directory under
   `fine-tuned-models/nllb-200-1.3B/zh2ko/runs/...` with
   `run_manifest.json` containing the same `segments_sha256` as the
   600M baseline (corpus must match)
3. Test report on the same held-out split (seed 42)
4. Backlog RF-026 contains the side-by-side comparison table
5. No regression to the 600M baseline (the 600M run is not touched)
6. **No data file** added to Git; only configs and backlog updates

## Verification

```powershell
# Confirm marker token resize works for the new base
venv\Scripts\python.exe scripts\train_model.py `
    --config configs\training\full_10k_nllb_1.3b.json `
    --nllb-smoke-test --smoke-rows 2

# After full training & evaluation:
$run_1_3b = "fine-tuned-models\nllb-200-1.3B\zh2ko\runs\run-full-10k-nllb-1.3b-v1"
Get-Content "$run_1_3b\run_manifest.json" | ConvertFrom-Json | Select segments_sha256, split_seed
# Expect: segments_sha256 matches the 600M run; split_seed=42.

git -c safe.directory=D:/longtu-translation-pipeline status --short
```

## Git workflow

- Two commits acceptable:
  1. `Add NLLB 1.3B training/inference config profiles (RF-026 setup)`
  2. `Record RF-026 NLLB-1.3B test report and baseline comparison`
- Do not push.
- Update RF-026 status to `DONE` in the final commit.
