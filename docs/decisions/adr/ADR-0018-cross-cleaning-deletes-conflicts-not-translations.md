# ADR-0018: Cross Cleaning Deletes Strong Conflicts, Not Translations

- Status: Accepted
- Date: 2026-05-25

## Context

Glossary and segment cleanup cannot be fully independent. An exact glossary mismatch in a
segment can mean either: (a) the glossary term is noisy and should be removed, or (b) the
segment translation is too free for training purposes. Automatically rewriting Korean to
match the glossary would risk producing ungrammatical Korean; deleting the segment is the
safer fallback.

## Decision

Glossary/segments cross-consistency cleanup (`scripts/segments_glossary_cross_cleaning_pipeline.py`)
may:
- Delete high-confidence glossary noise (terms that are not enforceable across the corpus).
- Delete segment rows that miss strong retained glossary terms.

It must not:
- Auto-rewrite Korean segment translations.
- Delete glossary terms based on shortness alone (weak-term score threshold ≥ 0.85 required).

## Consequences

- Training runs after cross-cleaning must regenerate train/validation/test split artifacts
  from the cleaned `data/segments.csv`.
- Short proper names or equipment-like terms (e.g., `艾格`, `臂铠`) are sent to review
  rather than auto-deleted.
- Cross-cleaning is a blocking step before full training (see [[ADR-0019]]).

## References

- Original entry: phase-1 refactor decisions log (archived; see ADR-0032 and git tag `phase-1-refactor-archive`)
- Related backlog entries: RF-011, RF-012
- Related code: `scripts/segments_glossary_cross_cleaning_pipeline.py`, `configs/cross_cleaning/`
