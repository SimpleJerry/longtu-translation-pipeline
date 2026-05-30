# T-F4 · RF-027 · Back-translation data augmentation

> Status: PENDING (optional research) | Blocked-by: T-A4 (baseline; also need a known ko→zh model) | Parallel-safe with: most others
> Touches: new augmentation script + augmented data file (gitignored), new training profile, backlog entry RF-027

## Why

Back-translation augments training data by translating real Korean
sentences (from any open ko corpus, or even the current `ko` column)
back to Chinese using a ko→zh model and pairing the result with the
original ko. Done carefully, it can improve zh→ko quality. Done
carelessly, it pollutes the train/validation/test contract.

This task introduces back-translation as a documented experiment
*after* the baseline is locked, with strict isolation of synthetic
data from the validation/test splits.

## Prerequisites

1. T-A4 committed (baseline locked).
2. A working ko→zh model (could be the same NLLB run reversed, or an
   off-the-shelf model).
3. User has authorized this experiment (synthetic data has known
   risks).

## Shared context (read these first)

- [ADR-0026](../../decisions/adr/ADR-0026-cloud-llm-segment-cleanup-may-rewrite-korean-with-local-guards.md) — Cloud LLM Segment Cleanup May Rewrite Korean With Local Guards (the closest precedent for synthetic data in this repo)
- [docs/refactor/backlog.md](../backlog.md) RF-006-P9, RF-006-P10 —
  the manifest schema and how `segments_sha256` enforces split
  consistency

## Files to read first

- `src/longtu_translation_pipeline/training.py` — `split_examples`
  and the manifest writer (to design how synthetic rows are tagged)
- `scripts/run_inference.py` — generation logic, reusable for ko→zh
- `data/segments.csv` schema

## Don't touch

- `data/segments.csv` — back-translation output goes into a
  **separate** file, e.g. `data/segments_synth_backtrans.csv`
  (gitignored or explicitly outside the corpus)
- Validation / test splits — synthetic data only ever joins
  **train**, never validation or test
- Seed / ratio
- The 600M baseline run

## Modification surface

1. New script `scripts/generate_back_translation.py`:
   - Reads a ko corpus (could be `data/segments.csv` `ko` column, or
     an external corpus)
   - Translates with a ko→zh model
   - Writes `data/segments_synth_backtrans.csv` with schema
     `synth_segment_id,zh-CN,ko,source_tag` where `source_tag` is
     always `synthetic_back_translation`
   - Skips any row whose Korean text already appears in the
     validation or test split (load those CSVs from the existing run
     manifest and use them as a blocklist)
2. Update `src/longtu_translation_pipeline/training.py` so a new
   training profile can specify a synthetic data file to **append to
   the train split only**, *after* the deterministic 8:1:1 split is
   computed on real data. The manifest must record:
   - real segments sha256 (unchanged)
   - synthetic file sha256
   - synthetic row count (so future runs can verify reproducibility)
3. New profile `configs/training/full_10k_with_backtrans.json` that
   references the synthetic file
4. New run directory naming: `run-full-10k-with-backtrans-v1`
5. Validation + test reports are run against the same
   `splits/validation.csv` and `splits/test.csv` as the baseline
   (they are not affected by the synthetic file)
6. Backlog RF-027 records the comparison vs. baseline

## Don't break

- The validation and test CSVs in the synthetic run **must be
  bit-identical** to the baseline's validation/test CSVs. Verify by
  SHA256.
- `segments_sha256` in the manifest still tracks the real
  `data/segments.csv`. The synthetic file gets its own field.

## Acceptance criteria

1. Synthetic data file exists outside `data/segments.csv`.
2. No row of the synthetic data leaks into validation or test
   splits.
3. New training run completes with a manifest that records both real
   and synthetic SHA256.
4. Test report (same held-out split as baseline) is recorded.
5. Comparison to T-A4 baseline is in backlog RF-027.
6. **No new file is checked into Git** beyond configs, scripts, and
   backlog. The synthetic data file is ignored.

## Verification

```powershell
# Confirm split CSVs match the baseline:
$baseline = "fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-full-10k-llm-segments-v1\splits"
$synth    = "fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-full-10k-with-backtrans-v1\splits"
Get-FileHash "$baseline\validation.csv","$synth\validation.csv" -Algorithm SHA256
Get-FileHash "$baseline\test.csv","$synth\test.csv" -Algorithm SHA256
# Expect: matching hashes for both pairs.

# Confirm no synth row in val/test:
venv\Scripts\python.exe -c @"
import csv
synth_ko = set()
with open('data/segments_synth_backtrans.csv', encoding='utf-8') as f:
    for r in csv.DictReader(f): synth_ko.add(r['ko'])
for path in [r'$synth\validation.csv', r'$synth\test.csv']:
    with open(path, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            assert r['ko'] not in synth_ko, f'Leak: {r[\"ko\"]}'
print('no leak')
"@

git -c safe.directory=D:/longtu-translation-pipeline status --short
```

## Git workflow

- Commits acceptable as separate logical units:
  1. Augmentation generator script
  2. Training profile + manifest extension
  3. Test report + RF-027 backlog entry
- Do not push.
- Update RF-027 status to `DONE` in the final commit.
