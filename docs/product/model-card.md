# Model Card — zh-CN → ko Translation

The current published model for the longtu-translation-pipeline project.
This card is the durable home for headline metrics and model lineage;
the constitution ([CLAUDE.md](../../CLAUDE.md)) and READMEs link here
instead of duplicating numbers that drift.

All metrics below are bound to a specific training corpus fingerprint.
Any change to `data/segments.csv` invalidates them and requires a fresh
evaluation (see [ADR-0023](../decisions/adr/ADR-0023-formal-experiments-use-held-out-test-splits.md)).

## Model

| Field | Value |
|-------|-------|
| Task | Simplified Chinese (`zh-CN`) → Korean (`ko`), game localization |
| Base model | `facebook/nllb-200-distilled-600M` |
| Fine-tuned run | `run-full-earlystop-v1`, `checkpoint-48000` |
| Training corpus | `data/segments.csv`, SHA256 `30D5C299828C10235AEE357E9333740913E55C291C5B07A45C0739E41818EA97` |
| Split | deterministic 8:1:1, seed 42; test = 6,626 held-out rows |
| Terminology markers | `<start>...<end>` applied to source at inference |

## Training Method

- Early stopping on a composite metric (`0.5 · BLEU + 0.5 · glossary-preservation-nospace`), evaluated on a validation subset; training stopped at step 49000 (~3.7 epochs). See [ADR-0031](../decisions/adr/ADR-0031-formal-training-uses-early-stopping-on-composite-metric.md).
- The published checkpoint was chosen by re-ranking the retained checkpoints on the **full** validation split, not by the trainer's in-loop auto-best; this selected `checkpoint-48000`.

## Inference Defaults

Decode configuration selected by a validation-only parameter sweep
([ADR-0006](../decisions/adr/ADR-0006-preserve-public-compatibility-by-default.md) governs changes to these defaults):

| Parameter | Value |
|-----------|-------|
| `num_beams` | 4 |
| `length_penalty` | 1.0 |
| `no_repeat_ngram_size` | 0 |
| `max_length` | 400 |

## Held-Out Test Results

Single evaluation on the held-out test split (6,626 rows, seed 42),
using the production decode defaults (beam search):

| Metric | Score |
|--------|-------|
| BLEU (whitespace) | 0.325 |
| chrF (max_n=6, β=2) | 0.590 |
| Glossary preservation (no-space) | 0.954 |
| Glossary preservation (exact) | 0.950 |
| Empty candidate rows | 0 |

Greedy decoding (`num_beams=1`) on the same test split scores BLEU ≈ 0.319;
beam search contributes the small remaining lift.

## Reference Points

- **Mid-training diagnostic (NOT a baseline):** an early 10k-step run was
  under-fit at BLEU ≈ 0.198 and was used only to confirm the under-fitting
  direction. It is not a baseline for measuring fine-tuning value.
- **Base-model baseline (RF-007-P5, done 2026-05-30):** the un-fine-tuned
  `facebook/nllb-200-distilled-600M` evaluated on the same held-out test
  split scores BLEU **0.009**, chrF **0.226**, glossary preservation
  (no-space) **0.323** at `num_beams=4`. The net value of fine-tuning +
  data cleaning is therefore **+0.316 BLEU (~34×)** and glossary
  preservation **+0.63** (≈32% → ≈95%) at matched decoding. The base
  model generates fluent-sounding Korean but completely misses
  game-specific terminology and character names; fine-tuning and the
  cleaned corpus together account for the full gap.

## Reproducibility

The run manifest (`run_manifest.json` inside the run directory) records the
corpus SHA256, split seed and ratios, row counts, and checkpoint paths.
Run directories, checkpoints, and evaluation reports are git-ignored
([ADR-0004](../decisions/adr/ADR-0004-csv-in-git-raw-xlsx-outside-git-tracking.md),
[ADR-0017](../decisions/adr/ADR-0017-generation-evaluation-reports-are-local-artifacts.md));
only the final corpora and configs are committed.
