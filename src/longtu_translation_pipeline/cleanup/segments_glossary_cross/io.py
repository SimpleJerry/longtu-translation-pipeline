"""CSV/config input and output for glossary/segment cross-cleaning.

Extracted verbatim from the former ``scripts/segments_glossary_cross_cleaning_pipeline.py``
under ADR-0033. Reads the cross-cleaning rules, glossary lexicons, and the
glossary/segment CSVs; writes the rewritten CSVs and the strict-check summary.
The CSV schemas (segment_id/zh-CN/ko, term_id/zh-CN/ko) are the data-schema
invariant (ADR-0004).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from longtu_translation_pipeline.cleanup.common import (
    ensure_csv_columns,
    read_json_config,
    read_term_file,
)

from .models import (
    CrossLexicons,
    GLOSSARY_SCHEMA,
    GlossaryTerm,
    SEGMENT_SCHEMA,
    SUMMARY_FIELDS,
    SegmentRow,
)


def read_cross_rules(path: Path) -> dict[str, Any]:
    rules = read_json_config(path)
    for section in ["thresholds", "scores"]:
        if not isinstance(rules.get(section), dict):
            raise RuntimeError(f"{path} must contain a '{section}' object.")
    return rules


def read_cross_lexicons(config_dir: Path) -> CrossLexicons:
    return CrossLexicons(
        general_words_zh=set(
            read_term_file(config_dir / "general_words_zh.txt", "general zh word")
        ),
        common_nouns_zh=set(
            read_term_file(config_dir / "common_nouns_zh.txt", "common zh noun")
        ),
        nonterm_exact=set(
            read_term_file(config_dir / "nonterm_exact.txt", "exact non-term")
        ),
        game_anchors=read_term_file(config_dir / "game_anchors.txt", "game anchor"),
        game_term_seeds=set(
            read_term_file(config_dir / "game_term_seeds.txt", "game term seed")
        ),
        acronym_whitelist=set(
            read_term_file(config_dir / "acronym_whitelist.txt", "acronym whitelist")
        ),
        noun_suffixes=read_term_file(config_dir / "noun_suffixes.txt", "noun suffix"),
        compound_suffixes=read_term_file(
            config_dir / "compound_suffixes.txt", "compound suffix"
        ),
    )


def read_glossary_rows(path: Path) -> list[GlossaryTerm]:
    rows = read_rows(path, GLOSSARY_SCHEMA)
    return [
        GlossaryTerm(row["term_id"], row["zh-CN"], row["ko"])
        for row in rows
        if row["term_id"] and row["zh-CN"] and row["ko"]
    ]


def read_segment_rows(path: Path) -> list[SegmentRow]:
    rows = read_rows(path, SEGMENT_SCHEMA)
    return [
        SegmentRow(row["segment_id"], row["zh-CN"], row["ko"])
        for row in rows
        if row["segment_id"] and row["zh-CN"] and row["ko"]
    ]


def read_rows(path: Path, schema: list[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        ensure_csv_columns(reader, schema, path)
        return [{key: (row.get(key) or "").strip() for key in schema} for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_check_summary(path: Path, current_mismatch_rows: int) -> None:
    write_csv(
        path,
        SUMMARY_FIELDS,
        [{"metric": "strict_current_mismatch_rows", "value": str(current_mismatch_rows)}],
    )


def write_glossary(
    path: Path, rows: list[GlossaryTerm], removed_term_ids: set[str]
) -> None:
    output: list[dict[str, str]] = []
    for new_id, row in enumerate(
        [row for row in rows if row.term_id not in removed_term_ids], 1
    ):
        output.append({"term_id": str(new_id), "zh-CN": row.zh, "ko": row.ko})
    write_csv(path, GLOSSARY_SCHEMA, output)


def write_segments(
    path: Path, rows: list[SegmentRow], removed_segment_ids: set[str]
) -> None:
    output: list[dict[str, str]] = []
    for new_id, row in enumerate(
        [row for row in rows if row.segment_id not in removed_segment_ids], 1
    ):
        output.append({"segment_id": str(new_id), "zh-CN": row.zh, "ko": row.ko})
    write_csv(path, SEGMENT_SCHEMA, output)
