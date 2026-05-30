# ADR-0014: Engineering Smoke Tests Use Staged Model Loading

- Status: Accepted
- Date: 2026-05-25

## Context

The training chain involves multiple risky integration points: real NLLB tokenizer, language
code handling, marker tokens, tensor shapes, Trainer wiring, CUDA execution, and embedding
resize. Validating all of these in a single full model training run would make failures
hard to isolate and would be unnecessarily expensive.

Two intermediate smoke stages were established:

**Stage 1 (RF-006-P3):** Use the real NLLB tokenizer but a tiny *randomly initialized*
`M2M100ForConditionalGeneration` model. Validates: language codes, marker tokens, dataset
tensors, Trainer wiring — without downloading real weights.

**Stage 2 (RF-006-P4):** Use the real NLLB tokenizer and real `facebook/nllb-200-distilled-600M`
weights. Validates: actual model loading, embedding resize for `<start>/<end>`, CUDA execution,
FP16 autocast — without running a training epoch.

## Decision

Engineering smoke tests use staged model loading:
- `--nllb-smoke-test` (stage 1): real tokenizer + tiny random model, `max_steps=1`.
- `--real-model-smoke-test` (stage 2): real tokenizer + real weights, `max_steps=1`.

Both stages write outputs to ignored `data/review/training_smoke/`. Neither stage retains
checkpoints or constitutes a training run.

## Consequences

- Failed smoke tests can be diagnosed at the appropriate stage without wasting GPU time.
- Real model smoke confirms CUDA/embed path before pilot or full training.
- Stage 1 runs without downloading NLLB model weights (~600 MB), keeping the CI-safe path light.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive, two entries merged here)
- Related backlog entries: RF-006-P3, RF-006-P4
- Related code: `scripts/train_model.py`, `src/longtu_translation_pipeline/training.py`
