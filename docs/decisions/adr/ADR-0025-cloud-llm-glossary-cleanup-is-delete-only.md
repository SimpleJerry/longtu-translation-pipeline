# ADR-0025: Cloud LLM Glossary Cleanup Is Delete-Only

- Status: Accepted
- Date: 2026-05-26

## Context

Local glossary cleanup is preferred because it is reproducible and does not send company
terminology outside the local machine. However, remaining semantic noise—common words,
phrases, and bad pairs that survive deterministic rules—may require LLM-level judgment.

The user accepted cloud OpenAI-compatible LLM use for an aggressive purification pass, but
with a critical constraint: new translations would create unreviewed terminology conflicts in
`data/glossary.csv`.

## Decision

Optional cloud LLM glossary cleanup (`scripts/glossary_llm_cleanup_pipeline.py`) may classify
current `data/glossary.csv` rows, but it can **only delete rows**. It must not:
- Rewrite Korean values.
- Add new terms.
- Merge terms.
- Choose a hard-coded model from the repository.

Required environment variables: `OPENAI_API_KEY`, `LLM_MODEL`.
Optional: `OPENAI_BASE_URL`.

After any LLM deletion pass, rerun the strict glossary/segment gate (see [[ADR-0019]]) and
regenerate training splits before training.

## Consequences

- Glossary purification is one-directional: rows can only be removed, not modified.
- Review artifacts remain under ignored `data/review/llm_glossary_cleanup/`.
- The model name is a runtime parameter, not a committed constant.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entries: RF-014, RF-029
- Related code: `scripts/glossary_llm_cleanup_pipeline.py`
- Related document: `docs/architecture/data-cleaning-pipeline.md`
