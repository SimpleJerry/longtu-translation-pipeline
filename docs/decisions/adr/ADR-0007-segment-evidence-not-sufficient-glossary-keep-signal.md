# ADR-0007: Segment Evidence Is Not a Sufficient Glossary Keep Signal

- Status: Accepted
- Date: 2026-05-22

## Context

`data/segments.csv` provides current product-corpus relevance evidence for glossary cleanup:
if a term's Chinese or Korean form appears in segments, the term is at least present in the
product. However, common words (e.g., "月亮/달" — moon) also appear frequently in product text
while being entirely unsuitable for a company game terminology table.

Using segment presence as a sufficient keep signal would have retained many common words and
generic phrases that do not belong in the glossary.

## Decision

Matching segment text is **not** by itself enough to keep a glossary term.

- Segment evidence can **remove** terms that are absent from the current corpus (marked
  `not_in_segments_redundant_for_current_corpus`).
- Segment evidence can be recorded for audit, but hard noise filters, termhood scoring,
  game-domain signals, POS shape, and semantic checks still decide whether a matched term
  should remain.

## Consequences

- The glossary semantic pipeline (`scripts/glossary_semantic_pipeline.py`) uses a multi-signal
  scoring approach: game-domain seeds, ordinary-noun seeds, embedding centroids, Stanza/Jieba
  POS shape, `wordfreq` frequency, and product-corpus presence.
- `product_score` is not included in the positive term score; acronym-component evidence
  only prevents false `not_in_segments` deletion for strong game acronym compounds.
- Glossary remains focused on genuine company game terminology.

## References

- Original entry: phase-1 refactor decisions log (archived; see ADR-0032 and git tag `phase-1-refactor-archive`)
- Related backlog entries: RF-010, RF-011
- Related code: `scripts/glossary_semantic_pipeline.py`, `configs/glossary/`
