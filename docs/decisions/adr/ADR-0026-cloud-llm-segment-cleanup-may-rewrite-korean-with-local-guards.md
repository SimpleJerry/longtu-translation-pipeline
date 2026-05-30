# ADR-0026: Cloud LLM Segment Cleanup May Rewrite Korean With Local Guards

- Status: Accepted
- Date: 2026-05-26

## Context

Remaining segment noise may be too semantic for deterministic local rules alone. The user chose
full-corpus LLM review and allowed Korean rewrite for cases where the existing Korean target is
semantically incorrect. However, unvalidated synthetic translations are risky—applying LLM
rewrites without local checks could introduce grammatical errors, missing glossary terms, or
placeholder corruption.

## Decision

Optional cloud LLM segment cleanup (`scripts/segments_llm_cleanup_pipeline.py`) may:
- Delete segment rows.
- Rewrite only the Korean target—**but only after local validation passes**.

The LLM must not:
- Change Chinese source text.
- Add rows, split rows, or merge rows.
- Edit glossary.

The LLM prompt receives only raw row text, placeholders, and matched glossary constraints.
Local pre-judgment flags (target contamination, structured-string hints, length ratio,
repeated-output checks) run only in post-response validation.

Rewrite validation checks: Hangul presence, no Chinese CJK in target, placeholder preservation,
glossary preservation (exact or no-space), length ratio, and repetition/explanation-like output.

A full LLM segment cleanup invalidates existing split artifacts, checkpoints, and reports.

## Consequences

- Korean rewrite is accepted only when all local guards pass.
- Failed rewrites fall back to keeping the original row (or deleting if the original target
  is already contaminated).
- Review artifacts remain under ignored `data/review/llm_segments_cleanup/`.

## References

- Original entry: phase-1 refactor decisions log (archived; see ADR-0032 and git tag `phase-1-refactor-archive`)
- Related backlog entries: RF-015, RF-029
- Related code: `scripts/segments_llm_cleanup_pipeline.py`
- Related document: `docs/architecture/data-cleaning-pipeline.md`
