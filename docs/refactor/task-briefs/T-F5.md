# T-F5 · RF-028 · Inference parameter sweep on selected checkpoint

> Status: PENDING (optional research) | Blocked-by: T-A4 (need selected checkpoint) | Parallel-safe with: T-F2/F3/F4 (different checkpoints) and T-B/C/D/E (no overlap)
> Touches: new sweep script (or extension to `run_inference.py`), backlog entry RF-028. No training.

## Why

After T-A4 selects a checkpoint, the next cheap quality lever is
inference hyperparameters: beam width, length penalty,
no_repeat_ngram_size, temperature, top_p (if sampling). Sweeping
these on the validation or test split can reveal a better operating
point without retraining.

This task does the sweep, records per-config BLEU + chrF (if T-F1
is done) + glossary preservation, and recommends an optimal set.

## Prerequisites

1. T-A4 committed; selected checkpoint identified.
2. T-F1 ideally done (chrF row in reports) — not required but useful.
3. GPU available for repeated generation.

## Shared context (read these first)

- [docs/refactor/backlog.md](../backlog.md) RF-006-P8 (validation
  generation), RF-007-P3 (selected checkpoint)
- HuggingFace `generate()` docs for the M2M100 / NLLB family
  (parameters: `num_beams`, `length_penalty`, `no_repeat_ngram_size`,
  `do_sample`, `temperature`, `top_p`, `top_k`)

## Files to read first

- `src/longtu_translation_pipeline/inference.py` — current
  `generate_translations` and how it consumes
  `configs/inference/*.json`
- `configs/inference/default.json` — current generation parameters

## Don't touch

- Training, training configs, segments.csv, glossary.csv
- The selected checkpoint
- Validation / test split CSVs

## Modification surface

1. New script `scripts/sweep_inference_params.py`:
   - CLI: `--run-dir`, `--model-path`, `--split {validation,test}`,
     `--output-dir`, and a `--grid` file pointing at a JSON describing
     the parameter grid
   - For each grid point: generate candidates, evaluate, append a row
     to `sweep_results.csv` with the params + metrics
   - **Important**: do the sweep on **validation**, then run the
     winning config once on **test** for the final number. Don't
     iterate on test.
2. Example grid file (commit it under `configs/inference/sweep_v1.json`):
   ```json
   {
     "num_beams": [1, 4, 8],
     "length_penalty": [0.8, 1.0, 1.2],
     "no_repeat_ngram_size": [0, 3],
     "do_sample": [false]
   }
   ```
   (12 combinations — keep the grid small; expand later if interesting)
3. Output under `data/review/inference/sweeps/.../sweep_results.csv`
   (gitignored)
4. Backlog RF-028 records:
   - Grid used
   - Top 3 configs by BLEU on validation
   - Top 3 by glossary preservation (exact)
   - Final test-set numbers for the winning config
   - Compared to T-A4 baseline (which used `configs/inference/default.json`)

## Acceptance criteria

1. Sweep script exists and works end-to-end on a small grid.
2. `sweep_results.csv` lists at least 6 parameter combinations.
3. The winning config (on validation) is identified and its test
   numbers are recorded.
4. Backlog RF-028 has the comparison vs. baseline.
5. **Test split is generated at most once per checkpoint per
   distinct parameter set**, and the final reported number is the
   first generated test run (no iteration).
6. No files added to Git beyond `scripts/sweep_inference_params.py`,
   `configs/inference/sweep_v1.json`, and `docs/refactor/backlog.md`.

## Verification

```powershell
venv\Scripts\python.exe scripts\sweep_inference_params.py `
    --run-dir fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-full-10k-llm-segments-v1 `
    --model-path fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-full-10k-llm-segments-v1\checkpoint-9000 `
    --split validation `
    --grid configs\inference\sweep_v1.json `
    --output-dir data\review\inference\sweeps\v1

Get-Content "data\review\inference\sweeps\v1\sweep_results.csv"
# Expect: header + N rows of grid points.

git -c safe.directory=D:/longtu-translation-pipeline status --short
```

## Git workflow

- One commit, message: `Add inference parameter sweep script and v1 grid (RF-028 setup)`.
- A second commit for the final winning configuration + test report:
  `Record RF-028 inference sweep results`.
- Do not push.
- Update RF-028 status to `DONE` in the final commit.
