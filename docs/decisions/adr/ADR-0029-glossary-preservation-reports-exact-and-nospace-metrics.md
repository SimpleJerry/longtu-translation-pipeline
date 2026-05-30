# ADR-0029: Glossary Preservation Reports Exact And No-Space Metrics

- Status: Accepted
- Date: 2026-05-26

## Context

Strict cleaning (see [[ADR-0019]]) accepts both exact and no-space-exact Korean preservation as
passing. However, the evaluation metric originally reported only exact preservation. This meant
valid translations like `추가피해` (no space) being scored as failures when the glossary entry
was `추가 피해` (with space)—creating misleading low preservation scores even for a well-cleaned
corpus.

## Decision

RF-007 reports **both** exact glossary preservation and no-space glossary preservation
side by side:

- `glossary_preservation_rate`: exact match (preserved for backward compatibility).
- `glossary_preservation_rate_nospace`: no-space exact match (avoids penalizing valid Korean
  spacing variation).

Use `glossary_preservation_rate_nospace` when judging term retention across Korean spacing
differences. Use `glossary_preservation_rate` when strict character-level equality is required.

## Consequences

- Evaluation reports carry both metrics.
- Early stopping (see [[ADR-0031]]) uses `eval_glossary_preservation_nospace` as one of
  the two composite metric components.
- Existing code that reads `glossary_preservation_rate` continues to work unchanged.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entries: RF-007 (follow-up notes), RF-006-P13
- Related code: `src/longtu_translation_pipeline/evaluation.py`
