"""I/O helpers for the segments_cleaning pipeline (ADR-0033 step 8b)."""

from __future__ import annotations

import csv
from collections import OrderedDict
from pathlib import Path
from typing import Any

from longtu_translation_pipeline.cleanup.common import ensure_csv_columns

SEGMENT_SCHEMA = ["segment_id", "zh-CN", "ko"]
GLOSSARY_SCHEMA = ["term_id", "zh-CN", "ko"]

AUDIT_FIELDS = [
    "original_segment_id",
    "split_index",
    "action",
    "reason",
    "semantic_action",
    "semantic_term_score",
    "noun_score",
    "zh_noun_score",
    "ko_noun_score",
    "glossary_similarity",
    "term_seed_similarity",
    "sentence_like_score",
    "embedding_model",
    "embedding_device",
    "zh_pos",
    "ko_pos",
    "zh-CN",
    "ko",
]


def read_rows(path: Path, schema: list[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        ensure_csv_columns(reader, schema, path)
        return [{key: (row.get(key) or "").strip() for key in schema} for row in reader]


def read_glossary(path: Path) -> tuple[set[tuple[str, str]], list[str]]:
    rows = read_rows(path, GLOSSARY_SCHEMA)
    pairs = {(row["zh-CN"], row["ko"]) for row in rows if row["zh-CN"] and row["ko"]}
    terms = sorted({row["zh-CN"] for row in rows if row["zh-CN"]})
    return pairs, terms


def read_thresholds(rules: dict[str, Any]) -> dict[str, float]:
    thresholds = rules.get("thresholds")
    if not isinstance(thresholds, dict):
        raise RuntimeError("segments rules.json must contain a 'thresholds' object.")
    return {key: float(value) for key, value in thresholds.items()}


def read_weights(rules: dict[str, Any]) -> dict[str, float]:
    weights = rules.get("weights")
    if not isinstance(weights, dict):
        raise RuntimeError("segments rules.json must contain a 'weights' object.")
    return {key: float(value) for key, value in weights.items()}


def require_setting(values: dict[str, float], name: str) -> float:
    try:
        return values[name]
    except KeyError as exc:
        raise RuntimeError(f"Missing segments rule setting: {name}") from exc


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_segments(path: Path, kept_rows: list[dict[str, str]]) -> None:
    output = [
        {"segment_id": str(index), "zh-CN": row["zh-CN"], "ko": row["ko"]}
        for index, row in enumerate(kept_rows, 1)
    ]
    write_csv(path, SEGMENT_SCHEMA, output)


def write_review_outputs(
    review_dir: Path,
    *,
    audit: list[dict[str, str]],
    split_review: list[dict[str, str]],
    placeholder_review: list[dict[str, str]],
    normalized_markup: list[dict[str, str]],
    normalized_wrappers: list[dict[str, str]],
    markup_mismatch_review: list[dict[str, str]],
    removed_markup_only: list[dict[str, str]],
    summary: OrderedDict[str, str],
) -> None:
    write_csv(review_dir / "segments_cleaning_audit.csv", AUDIT_FIELDS, audit)

    removed_non_segment = [
        row for row in audit if row["action"] == "REMOVE_NON_SEGMENT_FRAGMENT"
    ]
    write_csv(
        review_dir / "removed_segment_non_segment_fragment.csv",
        AUDIT_FIELDS,
        removed_non_segment,
    )

    removed_target_contamination = [
        row for row in audit if row["action"] == "REMOVE_TARGET_LANGUAGE_CONTAMINATION"
    ]
    write_csv(
        review_dir / "removed_segment_target_language_contamination.csv",
        AUDIT_FIELDS,
        removed_target_contamination,
    )

    removed_term_like = [row for row in audit if row["action"] == "REMOVE_TERM_LIKE"]
    write_csv(review_dir / "removed_segment_term_like.csv", AUDIT_FIELDS, removed_term_like)

    semantic_review = [
        row for row in audit if row["semantic_action"] == "REVIEW_SEMANTIC_TERM_ENTITY"
    ]
    write_csv(
        review_dir / "segments_semantic_term_review.csv",
        AUDIT_FIELDS,
        semantic_review,
    )

    removed_structured = [
        row for row in audit if row["action"] == "REMOVE_STRUCTURED_UNPARSED"
    ]
    write_csv(
        review_dir / "removed_segment_structured_unparsed.csv",
        AUDIT_FIELDS,
        removed_structured,
    )

    markup_only_fields = [
        "original_segment_id",
        "original_zh-CN",
        "original_ko",
        "normalized_zh-CN",
        "normalized_ko",
    ]
    write_csv(
        review_dir / "removed_segment_markup_only.csv",
        markup_only_fields,
        removed_markup_only,
    )

    split_fields = [
        "original_segment_id",
        "split_index",
        "action",
        "reason",
        "semantic_action",
        "semantic_term_score",
        "noun_score",
        "glossary_similarity",
        "term_seed_similarity",
        "sentence_like_score",
        "zh-CN",
        "ko",
        "source_zh-CN",
        "source_ko",
    ]
    write_csv(review_dir / "split_segment_structured.csv", split_fields, split_review)

    placeholder_fields = [
        "original_segment_id",
        "zh_placeholders",
        "ko_placeholders",
        "zh-CN",
        "ko",
    ]
    write_csv(
        review_dir / "segments_placeholder_review.csv",
        placeholder_fields,
        placeholder_review,
    )

    markup_fields = [
        "original_segment_id",
        "zh_tag_count",
        "ko_tag_count",
        "original_zh-CN",
        "original_ko",
        "normalized_zh-CN",
        "normalized_ko",
    ]
    write_csv(
        review_dir / "normalized_segment_markup.csv",
        markup_fields,
        normalized_markup,
    )

    wrapper_fields = [
        "original_segment_id",
        "wrapper_type",
        "original_zh-CN",
        "original_ko",
        "normalized_zh-CN",
        "normalized_ko",
    ]
    write_csv(
        review_dir / "normalized_segment_wrappers.csv",
        wrapper_fields,
        normalized_wrappers,
    )

    mismatch_fields = [
        "original_segment_id",
        "mismatch_type",
        "zh_unknown_angle_tags",
        "ko_unknown_angle_tags",
        "original_zh-CN",
        "original_ko",
        "normalized_zh-CN",
        "normalized_ko",
    ]
    write_csv(
        review_dir / "segments_markup_mismatch_review.csv",
        mismatch_fields,
        markup_mismatch_review,
    )

    write_csv(
        review_dir / "segments_cleaning_summary.csv",
        ["metric", "value"],
        [{"metric": key, "value": value} for key, value in summary.items()],
    )
