# ADR-0028: Inference Uses Source Terminology Markers

- Status: Accepted
- Date: 2026-05-26

## Context

The 10k validation generation exposed a train/inference mismatch: training data had `<start>...<end>`
terminology markers applied to the Chinese source text (and Korean target), but inference was
feeding raw source text without markers. This meant the model was evaluated on inputs that
did not match the distribution it was trained on.

## Decision

Inference applies source-only `<start>...<end>` glossary markers before tokenization by default
(`terminology_markers=true` in inference config).

Generated CSVs keep the **raw source text** (without markers) in the `source` column for human
readability. Markers are applied internally before tokenization but are not reflected in the
output CSV's `source` field.

Candidate text is stripped of glossary markers before report output when
`strip_glossary_markers=true` in the evaluation config.

## Consequences

- Train/inference input distribution is aligned for `<start>...<end>` marker usage.
- Source text in output CSVs is still human-readable (marker-free).
- Generation summaries record `source_terminology_markers`, `marked_source_rows`, and
  `source_terms_marked` for auditability.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entry: RF-006-P8 (follow-up notes)
- Related code: `src/longtu_translation_pipeline/inference.py`, `configs/inference/default.json`
