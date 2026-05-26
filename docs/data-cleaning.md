# Data Cleaning Notes

This document explains the cleanup rules behind the final training files:

- `data/segments.csv`
- `data/glossary.csv`

Raw Excel/CSV inputs and local review CSVs are not committed. Review artifacts are generated under `data/review/` and are ignored by Git.

## Markup And Style Tags

Presentation tags add artificial English-like tokens that the translation model may learn to copy or translate.

Example:

```text
zh-CN: <c=green>2%</c>\n<c=purple>攻击</c>
ko:    <c=green>2%</c>\n<c=purple>공격</c>
```

Cleanup behavior:

- Remove style tags such as `<c=green>`, `</c>`, and `<hlgreen>`.
- Preserve wrapped text such as `2%`, `攻击`, and `공격`.
- Keep machine placeholders such as `{0}` and `<key1>` unless a specific rule says otherwise.

## Structured Strings

Some rows contain tuple-like UI strings instead of a single aligned sentence.

Example:

```text
zh-CN: {"标题","正文"}
ko:    {"제목","본문"}
```

Cleanup behavior:

- If both sides parse and have the same field count, split them into aligned child rows.
- If only one side parses, parsing fails, or field counts differ, remove the source row and export it to local review.

This avoids training one row that actually contains several unrelated UI fields.

## Non-Segment Fragments

`segments.csv` is a seq2seq training corpus. It should contain sentence-like or phrase-like translation units, not isolated fragments that cannot function as training examples.

Example:

```text
zh-CN: 艮
ko:    간
```

Cleanup behavior:

- Pure one-character CJK fragments are removed as `AUTO_REMOVE_NON_SEGMENT_FRAGMENT`.
- Two- or three-character pure CJK fragments from the historical mixed corpus were handled once as migration data: they were removed from `segments.csv`, and only non-conflicting enforceable pairs were added to `glossary.csv`.
- The two- or three-character migration is not a permanent pipeline rule. It was a one-time repair for historical term/segment mixing.

## Target-Language Contamination

The Korean target side must be Korean. Rows whose target still contains Chinese or contains no Hangul are not reliable seq2seq training examples.

Example:

```text
zh-CN: 六壬秘境85级
ko:    六壬秘境85级
```

Cleanup behavior:

- Remove rows where `ko` contains CJK characters.
- Remove rows where `ko` is non-empty but has no Hangul.
- This is intentionally strict for the current corpus; no placeholder, ID, or version-number whitelist is used.

## Glossary / Segment Cross Cleaning

Glossary and segment cleanup are linked. A glossary term that is not actually enforceable in real segment translations should not delete good sentence data; a strong enforceable term should not be contradicted by training rows.

Cleanup behavior:

- Scan `segments.csv` with longest-first, non-overlapping Chinese glossary matches.
- Check Korean preservation with exact and no-space exact matching.
- Remove glossary entries that are not enforceable in the current corpus.
- Remove segment rows that still miss retained enforceable glossary terms.
- Never auto-rewrite Korean translations.

Before full training or final held-out reporting, run:

```powershell
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check
```

The expected pre-training gate is:

```text
strict_current_mismatch_rows=0
```
