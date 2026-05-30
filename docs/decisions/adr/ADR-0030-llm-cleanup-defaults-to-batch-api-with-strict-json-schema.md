# ADR-0030: LLM Cleanup Defaults To Batch API With Strict JSON Schema

- Status: Accepted
- Date: 2026-05-27

## Context

T-A1 pricing review estimated ~7.3M input + ~2.3M output tokens for the remaining segments
corpus. The legacy synchronous `/v1/chat/completions` transport had no `response_format`
constraint and no `max_tokens` cap, requiring regex fallback for JSON parsing and providing
no cost discount.

OpenAI Batch API gives a 50% cost discount, and strict `json_schema` eliminates the regex
fallback by requiring the server to validate the JSON response schema. After pricing review,
`gpt-4.1-mini` + Batch API + strict schema was confirmed as the cost-optimal configuration
(estimated ~$1.5-3 for the remaining corpus vs. ~$2.5 sync at `gpt-4o-mini`).

## Decision

Both LLM cleanup pipelines (`scripts/segments_llm_cleanup_pipeline.py` and
`scripts/glossary_llm_cleanup_pipeline.py`) default `--batch-mode batch`, submitting one
OpenAI `/v1/batches` job for the whole corpus and downloading the JSONL result.

Every chat completion payload (sync or batch) carries:
- `response_format={"type":"json_schema","strict":true}`
- `parallel_tool_calls=false`
- `max_tokens=batch_size*45` (segments) or `batch_size*30` (glossary)

The legacy synchronous path is preserved behind `--batch-mode sync` for unit tests and
small ad-hoc debugging runs only.

Batch runs are resumable via `batch_state.json` (atomic write of phase ∈ {init,
input_written, uploaded, submitted, completed, downloaded} + IDs).

No new third-party dependency was added; multipart upload is hand-rolled in `llm_common.py`
to preserve the urllib-only audit surface (§P0-1).

## Consequences

- Batch API SLA is 24h; set `--max-wait-sec` accordingly.
- Sync mode receives the same strict `json_schema` validation, so legacy callers get
  equivalent server-side validation.
- Pipeline cost is bounded and predictable before submission.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entries: RF-029, T-A1
- Related code: `scripts/llm_common.py`, `scripts/segments_llm_cleanup_pipeline.py`,
  `scripts/glossary_llm_cleanup_pipeline.py`
