# ADR-0027: Segment Fragments And Target Contamination Are Training Noise

- Status: Accepted
- Date: 2026-05-26

## Context

Validation sample review after the strict 10k diagnostic run surfaced two types of invalid
training rows:
1. Isolated one-character CJK fragments (e.g., `艮 -> 간`) that cannot function as seq2seq
   sentence pairs.
2. Korean targets that still contained Chinese characters or had no Hangul at all—not reliable
   translation examples.

These rows can degrade every future train/validation/test split if left in the corpus.

## Decision

High-confidence non-segment fragments and Korean-side target-language contamination are removed
from `data/segments.csv` before training.

Permanent rules:
- **Pure one-character CJK fragments** (`AUTO_REMOVE_NON_SEGMENT_FRAGMENT`): removed.
- **Target-language contamination** (`AUTO_REMOVE_TARGET_LANGUAGE_CONTAMINATION`): removed when
  `ko` contains CJK characters or `ko` is non-empty but has no Hangul.

The target contamination rule is intentionally strict for this corpus: no placeholder, ID, or
version-number whitelist is used.

Note: The one-time 2-3 character short-fragment migration from segments into glossary (RF-013)
was a historical repair for the mixed corpus and is **not a recurring pipeline step**.

## Consequences

- These deletion rules are permanent and apply on every `segments_cleaning_pipeline.py --apply`.
- The strict contamination policy may remove some ID-like or placeholder-only rows; the user
  accepted this trade-off for seq2seq training corpus quality.

## References

- Original entry: phase-1 refactor decisions log (archived; see ADR-0032 and git tag `phase-1-refactor-archive`)
- Related backlog entry: RF-013
- Related code: `scripts/segments_cleaning_pipeline.py`
- Related document: `docs/architecture/data-cleaning-pipeline.md`
