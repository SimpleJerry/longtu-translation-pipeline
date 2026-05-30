# ADR-0013: Segment Cleanup Is Review-First

- Status: Accepted
- Date: 2026-05-24

## Context

Seq2seq segment cleaning has a higher false-positive risk than glossary cleaning. Short UI
labels, structured strings with machine placeholders, and phonetic game terms can look like
noise by simple heuristics while being valid training examples. Applying deletions without
a human review step could degrade the corpus silently.

## Decision

The segment cleanup pipeline (`scripts/segments_cleaning_pipeline.py`) defaults to dry-run
and rewrites `data/segments.csv` only when explicitly run with `--apply`.

Additional constraints:
- Term/entity-like deletion uses local semantic signals (Stanza POS, embedding similarity,
  game-domain seed proximity), not fixed text-length thresholds.
- Presentation tags (`<c=...>`) are stripped while preserving wrapped text.
- Symmetric outer wrappers are unwrapped; valid machine placeholders are audited, not deleted.
- Structured tuple-like strings are split when safely aligned; removed only when parsing fails.

## Consequences

- Every cleanup run writes review CSVs under `data/review/segments/` before any data changes.
- `--apply` is a deliberate operator decision, not a default.
- The rules in `configs/segments/` are configurable without code changes.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entries: RF-010, RF-013
- Related code: `scripts/segments_cleaning_pipeline.py`, `configs/segments/`
- Related document: `docs/architecture/data-cleaning-pipeline.md`
