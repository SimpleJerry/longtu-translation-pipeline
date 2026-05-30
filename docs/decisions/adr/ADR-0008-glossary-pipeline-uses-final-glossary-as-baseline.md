# ADR-0008: Glossary Pipeline Uses Final Glossary As Baseline

- Status: Accepted
- Date: 2026-05-24

## Context

Early versions of the glossary semantic pipeline read from a historical audit CSV as its
baseline. Historical audit baselines and raw source files are not committed because they
are intermediate or sensitive data. This made the pipeline non-reproducible for anyone
who only has the committed repository.

## Decision

The glossary semantic pipeline reads the current `data/glossary.csv` as its authoritative
baseline and writes audit CSVs only as local ignored artifacts under `data/review/`.

Additional constraints:
- Long business rule lists and thresholds live in `configs/glossary/` (not hard-coded).
- `segments.csv` SHA256 hashes are recorded in audit output for traceability, but must not
  be hard-coded as a required source-code gate.

## Consequences

- The pipeline is reproducible from the committed corpus without needing external baseline
  files.
- Audit CSVs under `data/review/glossary_*` are local artifacts that are regenerated on
  each pipeline run.
- Business rules are reviewable and configurable without code changes.

## References

- Original entry: phase-1 refactor decisions log (archived; see ADR-0032 and git tag `phase-1-refactor-archive`)
- Related backlog entries: RF-010, RF-011
- Related code: `scripts/glossary_semantic_pipeline.py`, `configs/glossary/`
