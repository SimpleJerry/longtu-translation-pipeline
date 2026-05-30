# ADR-0010: Text Protection Uses Single-Segment Term Markers

- Status: Accepted
- Date: 2026-05-24

## Context

Two terminology protection formats existed in the codebase:
1. **Single-segment**: `<start>term<end>` applied to both source and target sides independently.
2. **T&N+R**: `<start>source<middle>target<end>` — a triplet format for term-and-replace.
3. **Code/tag protection**: `<code_id=N>` for protecting UI tags and code spans.

The T&N+R format introduced complexity in tokenization, evaluation, and inference alignment.
The user decided to simplify the current mainline to a single unified format.

## Decision

Current terminology protection uses only `<start>...<end>` on both source and target sides.
The historical T&N+R format (`<middle>`) and `<code_id=N>` code/tag protection are deprecated
from the current engineering mainline.

Historical notebooks may still contain `<middle>` and `<code_id=N>` outputs as experiment
records, but new reusable code must not generate them unless a future task explicitly
reintroduces that behavior.

## Consequences

- `src/longtu_translation_pipeline/text_protection.py` provides the canonical `<start>...<end>`
  marker implementation.
- No current module, test, README, or config path relies on `<middle>` or `<code_id=N>`.
- Future RF-006/RF-007 work uses only the single-segment marker format.
- Train/inference marker alignment uses the same format (see [[ADR-0028]]).

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entry: RF-005
- Related code: `src/longtu_translation_pipeline/text_protection.py`, `tests/test_text_protection.py`
