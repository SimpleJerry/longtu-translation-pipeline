# ADR-0004: CSV In Git, Raw XLSX Outside Normal Git Tracking

- Status: Accepted
- Date: 2026-05-17

## Context

The repository originally tracked raw Excel files (`.xlsx`). Binary Excel files are large,
produce unintelligible diffs, and cannot be reviewed in pull requests. The project needed
a data governance policy that allows review-friendly snapshots while keeping raw source
files out of the repository.

Alternatives considered:
- Keep tracking xlsx files as-is (rejected: no reviewability).
- Store both CSV and xlsx (rejected: duplication, unclear authority).
- CSV only, xlsx outside Git (chosen).

## Decision

Store normalized CSV snapshots in Git and move raw xlsx files out of normal Git tracking
(`.gitignore`). The committed CSV files are the authoritative training data representation.

Rules:
- Multi-sheet workbooks must preserve workbook and sheet identity when converted to CSV.
- Formula cells export the workbook's saved cached values, not the formulas.
- Raw xlsx files live locally outside Git; their paths are documented but not committed.

## Consequences

- `data/segments.csv` and `data/glossary.csv` are fully reviewable in PRs.
- Regenerating the corpus from raw xlsx requires local files that are not in the repository.
- RF-010 executed the initial conversion; the conversion script was subsequently removed
  as an intermediate artifact.

## References

- Original entry: `docs/refactor/decisions.md` (historical archive)
- Related backlog entries: RF-002, RF-010
- Related code: `scripts/export_xlsx_to_csv.py` (removed post-RF-010)
