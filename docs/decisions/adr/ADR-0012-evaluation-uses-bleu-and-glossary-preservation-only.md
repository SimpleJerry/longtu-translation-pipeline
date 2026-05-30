# ADR-0012: Evaluation Uses BLEU and Glossary Preservation Only

- Status: Accepted
- Date: 2026-05-24

## Context

Old evaluation notebooks used historical `<middle>` and `<code_id>` assumptions that no
longer match the RF-005 single-segment marker format. The project needed automated evaluation
before RF-006 could move into real training or generation. Code-token preservation evaluation
depended on the now-deprecated `<code_id=N>` format and was therefore out of scope.

Alternatives considered: include code-token preservation (rejected: depends on deprecated
format); include COMET now (rejected: ~1.5 GB dependency, complex to add alongside core
metrics); chrF now (rejected: deferred to T-F1 as a separate task).

## Decision

RF-007 evaluation automates corpus BLEU and glossary preservation for the `<start>...<end>`
marker policy. Code-token preservation is not part of the current evaluation mainline.

- BLEU defaults to Korean whitespace tokenization; character tokenization is a config option.
- Glossary preservation checks Korean term presence after stripping markers from candidates.
- Both exact and no-space exact metrics are reported (see [[ADR-0029]]).

Future metric additions (chrF via T-F1, COMET via T-F2) expand this contract; they do not
replace it.

## Consequences

- `scripts/evaluate_translation.py` and `src/longtu_translation_pipeline/evaluation.py`
  are the canonical evaluation entry points.
- Historical `<middle>` and `<code_id>` evaluation paths remain archived only.
- Expanding the metric set requires a new task and a new ADR.

## References

- Original entry: phase-1 refactor decisions log (archived; see ADR-0032 and git tag `phase-1-refactor-archive`)
- Related backlog entries: RF-007, RF-024 (chrF), RF-025 (COMET)
- Related code: `src/longtu_translation_pipeline/evaluation.py`, `configs/evaluation/`
