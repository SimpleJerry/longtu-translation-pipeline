# ADR-0019: Full Training Requires Strict Glossary Consistency Check

- Status: Accepted
- Date: 2026-05-25

## Context

Glossary/segment conflicts contaminate all downstream train, validation, and test splits if
they remain in the final corpus. If a segment source contains a retained glossary term but
the Korean target does not include the glossary Korean form, the model trains on inconsistent
signal for that term.

## Decision

Before full training or final held-out evaluation, `data/segments.csv` must pass a strict
glossary consistency check:

```powershell
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check
```

The expected pre-training gate is:
```
strict_current_mismatch_rows=0
```

Strict cleanup selects an **enforceable** glossary first by using real segment translations:
- Terms with natural phrase variation or unstable Korean forms are removed from the glossary
  rather than deleting good sentence data.
- `--strict-apply` may then remove remaining mismatching segment rows, but must not
  auto-rewrite Korean translations.

## Consequences

- `--strict-check` is the gate before every formal training run and held-out evaluation.
- Glossary quality is bounded by what can actually be enforced in the current corpus.
- Strict-apply may be run in multiple passes as term statistics change after each pass.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entries: RF-012, RF-013
- Related code: `scripts/segments_glossary_cross_cleaning_pipeline.py`
- Related document: `docs/architecture/data-cleaning-pipeline.md`
