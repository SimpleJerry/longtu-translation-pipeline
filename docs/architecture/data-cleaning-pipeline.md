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

## LLM Glossary Cleanup

The local glossary cleanup pipeline is preferred because it is reproducible and does not send company terminology outside the local machine. If the remaining glossary noise is too semantic for local rules, the optional LLM cleanup pass can be used as an aggressive delete-only step.

Example candidates:

```text
KEEP:   暴击 -> 치명타
REMOVE: 月亮 -> 달
REMOVE: 感谢有你 -> 함께해 주셔서 감사합니다
```

Cleanup behavior:

- Send only `term_id`, `zh-CN`, and `ko` glossary rows to an OpenAI-compatible Chat Completions API.
- Keep rows only when the model returns `KEEP_GAME_TERM`.
- Delete rows classified as common words, phrase/sentence content, fragments, bad pairs, or not company game terms.
- Never allow the model to rewrite Korean translations, add terms, or merge entries.
- Write full audit files and raw batch envelopes under `data/review/llm_glossary_cleanup/`, which is ignored by Git.

Required environment:

```powershell
$env:OPENAI_API_KEY="<your-key>"
$env:LLM_MODEL="<your-model>"
# Optional: $env:OPENAI_BASE_URL="https://api.openai.com/v1"
venv\Scripts\python.exe scripts\glossary_llm_cleanup_pipeline.py --apply
```

After an LLM cleanup, rerun the strict glossary/segment gate before training:

```powershell
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check
```

## LLM Segment Cleanup

The segment LLM cleanup pass is for full-corpus review when local rules are no longer enough to separate usable training pairs from semantic noise. It can remove rows and can also accept a Korean rewrite, but only after local validation.

Example candidates:

```text
KEEP:   zh-CN: 挑战次数:{0}/{1}
        ko:    도전 횟수: {0}/{1}

REMOVE: zh-CN: 艮
        ko:    간

REWRITE zh-CN: 技能升级
        ko:    기술 강화
        corrected_ko: 스킬 강화
```

Cleanup behavior:

- Send only `segment_id`, `zh-CN`, `ko`, detected placeholders, and matched glossary terms to an OpenAI-compatible Chat Completions API.
- Do not send local pre-judgment fields such as target-contamination flags, structured-string hints, length-ratio flags, or repeated-output flags to the model; those checks run only after the model responds.
- Ask the model to review each row independently by semantic fit, with a row-specific reason rather than a bulk rule label.
- Allow the model to choose keep, remove, review, or Korean rewrite actions.
- Never allow the model to change Chinese source text, add rows, split rows, merge rows, or edit glossary.
- Apply a Korean rewrite only if it is non-empty, contains Hangul, contains no Chinese CJK, preserves placeholders, preserves matched glossary terms by exact or no-space matching, and passes basic length/repetition checks.
- If a rewrite fails validation, keep the original row for review unless the original Korean target is already contaminated; contaminated rows are removed.
- Record action distribution, repeated-reason warnings, surface-feature action warnings, rewrite accept/reject rates, and a balanced sample review under `data/review/llm_segments_cleanup/`.

Command:

```powershell
$env:OPENAI_API_KEY="<your-key>"
$env:LLM_MODEL="<your-model>"
venv\Scripts\python.exe scripts\segments_llm_cleanup_pipeline.py --dry-run
```

Use `--apply` only after reviewing `data/review/llm_segments_cleanup/`. A full segment LLM cleanup invalidates existing train/validation/test split artifacts and model reports.

Do not use the ChatGPT web UI as the authoritative full-file cleanup path. It may use file-analysis tools and code-like preprocessing, which makes it hard to prove that every row received semantic review. If the web UI is useful, use it only for small manual samples of about 50-100 pasted rows and ask it not to use tools; still treat the result as review evidence rather than a file that can directly overwrite the corpus.
