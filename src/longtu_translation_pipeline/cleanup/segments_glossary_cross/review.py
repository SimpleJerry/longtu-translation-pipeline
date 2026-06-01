"""Review-artifact generation for glossary/segment cross-cleaning.

Extracted verbatim from the former ``scripts/segments_glossary_cross_cleaning_pipeline.py``
under ADR-0033. Writes the term-summary, row-audit, removed-glossary,
removed-segment, strict-removed, and summary CSVs under the ignored review
directory.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .io import write_csv
from .models import (
    REMOVED_GLOSSARY_FIELDS,
    REMOVED_SEGMENT_FIELDS,
    ROW_AUDIT_FIELDS,
    STRICT_REMOVED_GLOSSARY_FIELDS,
    STRICT_REMOVED_SEGMENT_FIELDS,
    SUMMARY_FIELDS,
    TERM_SUMMARY_FIELDS,
)


def write_review_files(
    review_dir: Path,
    term_summaries: list[dict[str, str]],
    row_audits: list[dict[str, str]],
    removed_glossary_rows: list[dict[str, str]],
    removed_segment_rows: list[dict[str, str]],
    strict_removed_glossary_rows: list[dict[str, str]],
    strict_removed_segment_rows: list[dict[str, str]],
    current_mismatch_rows: int,
) -> None:
    write_csv(review_dir / "cross_cleaning_term_summary.csv", TERM_SUMMARY_FIELDS, term_summaries)
    write_csv(
        review_dir / "cross_cleaning_row_audit.csv",
        ROW_AUDIT_FIELDS,
        [{key: row[key] for key in ROW_AUDIT_FIELDS} for row in row_audits],
    )
    write_csv(
        review_dir / "removed_glossary_cross_noise.csv",
        REMOVED_GLOSSARY_FIELDS,
        [removed_glossary_row(row) for row in removed_glossary_rows],
    )
    write_csv(
        review_dir / "removed_segment_terminology_conflicts.csv",
        REMOVED_SEGMENT_FIELDS,
        [
            removed_segment_row(index, row)
            for index, row in enumerate(removed_segment_rows, 1)
        ],
    )
    write_csv(
        review_dir / "strict_removed_glossary_unenforceable.csv",
        STRICT_REMOVED_GLOSSARY_FIELDS,
        [strict_removed_glossary_row(row) for row in strict_removed_glossary_rows],
    )
    write_csv(
        review_dir / "strict_removed_segment_glossary_mismatch.csv",
        STRICT_REMOVED_SEGMENT_FIELDS,
        [
            strict_removed_segment_row(index, row)
            for index, row in enumerate(strict_removed_segment_rows, 1)
        ],
    )
    summary_rows = build_summary_rows(
        term_summaries,
        row_audits,
        removed_glossary_rows,
        removed_segment_rows,
        strict_removed_glossary_rows,
        strict_removed_segment_rows,
        current_mismatch_rows,
    )
    write_csv(review_dir / "cross_cleaning_summary.csv", SUMMARY_FIELDS, summary_rows)
    write_csv(review_dir / "strict_summary.csv", SUMMARY_FIELDS, summary_rows)


def removed_glossary_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "original_term_id": row["term_id"],
        "term_zh-CN": row["term_zh-CN"],
        "expected_ko": row["expected_ko"],
        "occurrence_count": row["occurrence_count"],
        "preserved_count": row["preserved_count"],
        "missing_count": row["missing_count"],
        "missing_rate": row["missing_rate"],
        "preserved_rate": row["preserved_rate"],
        "domain_score": row["domain_score"],
        "weak_score": row["weak_score"],
        "remove_reason": "AUTO_REMOVE_GLOSSARY_NOISE",
    }


def removed_segment_row(index: int, row: dict[str, str]) -> dict[str, str]:
    return {
        "removed_id": str(index),
        "original_segment_id": row["original_segment_id"],
        "zh-CN": row["zh-CN"],
        "ko": row["ko"],
        "missing_strong_terms": row["missing_strong_terms"],
        "term_level_stats": row["_term_level_stats"],
        "remove_reason": "AUTO_REMOVE_SEGMENT_CONFLICT",
    }


def strict_removed_glossary_row(row: dict[str, str]) -> dict[str, str]:
    data = removed_glossary_row(row)
    data["remove_reason"] = row["strict_term_action"]
    return data


def strict_removed_segment_row(index: int, row: dict[str, str]) -> dict[str, str]:
    return {
        "removed_id": str(index),
        "original_segment_id": row["original_segment_id"],
        "zh-CN": row["zh-CN"],
        "ko": row["ko"],
        "strict_missing_terms": row["strict_missing_terms"],
        "remove_reason": row["strict_row_action"],
    }


def build_summary_rows(
    term_summaries: list[dict[str, str]],
    row_audits: list[dict[str, str]],
    removed_glossary_rows: list[dict[str, str]],
    removed_segment_rows: list[dict[str, str]],
    strict_removed_glossary_rows: list[dict[str, str]],
    strict_removed_segment_rows: list[dict[str, str]],
    current_mismatch_rows: int,
) -> list[dict[str, str]]:
    rows = [
        {"metric": "term_rows", "value": str(len(term_summaries))},
        {"metric": "row_audit_rows", "value": str(len(row_audits))},
        {
            "metric": "removed_glossary_noise_rows",
            "value": str(len(removed_glossary_rows)),
        },
        {
            "metric": "removed_segment_conflict_rows",
            "value": str(len(removed_segment_rows)),
        },
        {
            "metric": "strict_current_mismatch_rows",
            "value": str(current_mismatch_rows),
        },
        {
            "metric": "strict_removed_glossary_unenforceable_rows",
            "value": str(len(strict_removed_glossary_rows)),
        },
        {
            "metric": "strict_removed_segment_mismatch_rows",
            "value": str(len(strict_removed_segment_rows)),
        },
    ]
    for action, count in Counter(row["term_action"] for row in term_summaries).most_common():
        rows.append({"metric": f"term_action.{action}", "value": str(count)})
    for action, count in Counter(row["row_action"] for row in row_audits).most_common():
        rows.append({"metric": f"row_action.{action}", "value": str(count)})
    for action, count in Counter(row["strict_term_action"] for row in term_summaries).most_common():
        rows.append({"metric": f"strict_term_action.{action}", "value": str(count)})
    for action, count in Counter(row["strict_row_action"] for row in row_audits).most_common():
        rows.append({"metric": f"strict_row_action.{action}", "value": str(count)})
    return rows
