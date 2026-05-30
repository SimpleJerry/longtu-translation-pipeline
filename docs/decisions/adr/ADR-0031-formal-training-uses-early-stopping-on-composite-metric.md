# ADR-0031: Formal Training Uses Early Stopping On Composite Metric

- Status: Accepted
- Date: 2026-05-27

## Context

RF-006-P11 used `max_steps=10000` (= 0.189 epoch). At step 10000, `eval_loss` was still
decreasing and validation BLEU was still rising, indicating the model was under-fit. A fixed
step ceiling has no mechanism to detect either under-fit (stops too early) or over-fit (stops
too late if validation quality degrades).

Alternatives surveyed: plain post-hoc best-checkpoint selection (no auto-halt), ReduceLROnPlateau
(loss-only, misses glossary preservation), smoothed early stopping, learning-curve extrapolation,
Bayesian HPO. The patience + composite-metric + best-checkpoint combination was chosen as the
standard NMT finetune practice that fits this project's stage.

## Decision

New formal training runs use `Seq2SeqTrainer` with `EarlyStoppingCallback` (patience=5,
threshold=0.0) and `load_best_model_at_end=True`, driven by a composite metric:

```
eval_composite = 0.5 · eval_bleu + 0.5 · eval_glossary_preservation_nospace
```

- `num_train_epochs` is the ceiling (default 10); `max_steps` is left unset so the early-stop
  loop decides when to halt.
- The `full_10k.json` profile (`max_steps=10000`) is **preserved** as a historical baseline
  and must not be deleted.
- **In-loop eval uses a 1,000-row validation subset** (`metrics.eval_subset_rows=1000`) for
  performance: the full 6,626-row validation set took ~38 min per eval with
  `predict_with_generate=True`, making the 10-epoch ceiling prohibitive.
- The remaining 5,626 validation rows are reserved for post-hoc top-K (3) full-validation
  after early stopping triggers.
- `generation_max_length=256` for in-loop (p99.9 of ko output tokens = 225; ~0.06% truncation);
  `configs/inference/default.json` retains `max_length=400` for post-hoc and final inference.

Composite weights (currently 0.5/0.5 on BLEU and preservation_nospace) can only be revised
via a new RF, not silent edits.

The plain `Trainer` (non-Seq2Seq) path stays available for smoke/pilot/`full_10k.json` so
existing tests and old profiles keep working.

## Consequences

- Formal training auto-stops when the composite metric plateaus rather than at an arbitrary
  step count.
- Inference-time hyperparameter exploration (beam width, length penalty) is separate (RF-028),
  not part of this decision.
- In-loop eval uses a cheap 1k-row subset; final checkpoint selection uses full-validation
  post-hoc evaluation.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entries: RF-006-P13, T-A5
- Related code: `src/longtu_translation_pipeline/training.py`,
  `src/longtu_translation_pipeline/training_metrics.py`,
  `configs/training/full_earlystop.json`
