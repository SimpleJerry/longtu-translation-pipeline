"""Orchestration and CLI for glossary/segment cross-cleaning (ADR-0018, ADR-0019).

Cross-checks glossary terms against segment translations: removes glossary
entries that behave like weak/common words and are frequently not translated
with their glossary Korean form; removes segment rows that miss a strong
glossary term with enough preserved evidence elsewhere; and optionally enforces
a strict pre-training gate. Never rewrites Korean text.

Extracted from the former ``scripts/segments_glossary_cross_cleaning_pipeline.py``
under ADR-0033. The domain logic lives in the sibling modules (models, io,
matching, scoring, classify, review); this module keeps the run_pipeline
orchestration plus the argparse/main/print_result entry surface.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .classify import classify_corpus
from .io import (
    read_cross_lexicons,
    read_cross_rules,
    read_glossary_rows,
    read_segment_rows,
    write_check_summary,
    write_glossary,
    write_segments,
)
from .models import PipelineResult
from .review import write_review_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cross-clean glossary noise and segment terminology conflicts."
    )
    parser.add_argument("--segments", default="data/segments.csv")
    parser.add_argument("--glossary", default="data/glossary.csv")
    parser.add_argument("--config", default="configs/cross_cleaning/rules.json")
    parser.add_argument("--glossary-config-dir", default="configs/glossary")
    parser.add_argument(
        "--review-dir", default="data/review/segments_glossary_cross"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Write review CSVs only.")
    mode.add_argument("--apply", action="store_true", help="Rewrite final CSVs.")
    mode.add_argument(
        "--strict-dry-run",
        action="store_true",
        help="Plan strict glossary/segment consistency cleanup without rewriting files.",
    )
    mode.add_argument(
        "--strict-apply",
        action="store_true",
        help="Apply strict consistency cleanup and rewrite final CSVs.",
    )
    mode.add_argument(
        "--strict-check",
        action="store_true",
        help="Fail if any current segment misses any current glossary term.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = selected_cli_mode(args)
    result = run_pipeline(
        segments_path=Path(args.segments),
        glossary_path=Path(args.glossary),
        config_path=Path(args.config),
        glossary_config_dir=Path(args.glossary_config_dir),
        review_dir=Path(args.review_dir),
        mode=selected_mode,
    )
    print_result(result)
    if selected_mode == "strict-check" and result.strict_current_mismatch_rows:
        return 1
    return 0


def selected_cli_mode(args: argparse.Namespace) -> str:
    if args.apply:
        return "apply"
    if args.strict_dry_run:
        return "strict-dry-run"
    if args.strict_apply:
        return "strict-apply"
    if args.strict_check:
        return "strict-check"
    return "dry-run"


def run_pipeline(
    segments_path: Path,
    glossary_path: Path,
    config_path: Path,
    glossary_config_dir: Path,
    review_dir: Path,
    apply: bool = False,
    mode: str | None = None,
) -> PipelineResult:
    if mode is None:
        mode = "apply" if apply else "dry-run"
    rules = read_cross_rules(config_path)
    lexicons = read_cross_lexicons(glossary_config_dir)
    glossary_rows = read_glossary_rows(glossary_path)
    segment_rows = read_segment_rows(segments_path)

    term_summaries, row_audits = classify_corpus(
        segment_rows=segment_rows,
        terms=sorted(glossary_rows, key=lambda term: len(term.zh), reverse=True),
        lexicons=lexicons,
        rules=rules,
    )

    normal_removed_terms = {
        row["term_id"]
        for row in term_summaries
        if row["term_action"] == "AUTO_REMOVE_GLOSSARY_NOISE"
    }
    normal_removed_segment_ids = {
        row["original_segment_id"]
        for row in row_audits
        if row["row_action"] == "AUTO_REMOVE_SEGMENT_CONFLICT"
    }
    strict_removed_terms = {
        row["term_id"]
        for row in term_summaries
        if row["strict_term_action"] == "AUTO_REMOVE_GLOSSARY_UNENFORCEABLE"
    }
    strict_removed_segment_ids = {
        row["original_segment_id"]
        for row in row_audits
        if row["strict_row_action"] == "STRICT_REMOVE_SEGMENT_MISMATCH"
    }
    current_mismatch_rows = sum(1 for row in row_audits if row["missing_terms"])

    if mode in {"strict-dry-run", "strict-apply"}:
        removed_term_ids = strict_removed_terms
        removed_segment_ids = strict_removed_segment_ids
    elif mode == "strict-check":
        removed_term_ids = set()
        removed_segment_ids = set()
    else:
        removed_term_ids = normal_removed_terms
        removed_segment_ids = normal_removed_segment_ids

    removed_glossary_rows = [
        row for row in term_summaries if row["term_id"] in removed_term_ids
    ]
    removed_segment_rows = [
        row for row in row_audits if row["original_segment_id"] in removed_segment_ids
    ]
    strict_removed_glossary_rows = [
        row for row in term_summaries if row["term_id"] in strict_removed_terms
    ]
    strict_removed_segment_rows = [
        row
        for row in row_audits
        if row["original_segment_id"] in strict_removed_segment_ids
    ]

    review_dir.mkdir(parents=True, exist_ok=True)
    if mode == "strict-check":
        write_check_summary(review_dir / "strict_check_summary.csv", current_mismatch_rows)
    else:
        write_review_files(
            review_dir=review_dir,
            term_summaries=term_summaries,
            row_audits=row_audits,
            removed_glossary_rows=removed_glossary_rows,
            removed_segment_rows=removed_segment_rows,
            strict_removed_glossary_rows=strict_removed_glossary_rows,
            strict_removed_segment_rows=strict_removed_segment_rows,
            current_mismatch_rows=current_mismatch_rows,
        )

    output_glossary_rows = len(glossary_rows) - len(removed_term_ids)
    output_segment_rows = len(segment_rows) - len(removed_segment_ids)

    if mode in {"apply", "strict-apply"}:
        write_glossary(glossary_path, glossary_rows, removed_term_ids)
        write_segments(segments_path, segment_rows, removed_segment_ids)

    return PipelineResult(
        mode=mode,
        input_glossary_rows=len(glossary_rows),
        output_glossary_rows=output_glossary_rows,
        removed_glossary_noise_rows=len(removed_term_ids),
        input_segment_rows=len(segment_rows),
        output_segment_rows=output_segment_rows,
        removed_segment_conflict_rows=len(removed_segment_ids),
        review_dir=review_dir,
        term_action_counts=Counter(row["term_action"] for row in term_summaries),
        row_action_counts=Counter(row["row_action"] for row in row_audits),
        strict_current_mismatch_rows=current_mismatch_rows,
        strict_unenforceable_glossary_rows=len(strict_removed_terms),
        strict_removed_segment_mismatch_rows=len(strict_removed_segment_ids),
    )


def print_result(result: PipelineResult) -> None:
    print("Segments/glossary cross-cleaning pipeline completed.")
    print(f"mode={result.mode}")
    print(f"input_glossary_rows={result.input_glossary_rows}")
    print(f"output_glossary_rows={result.output_glossary_rows}")
    print(f"removed_glossary_noise_rows={result.removed_glossary_noise_rows}")
    print(f"input_segment_rows={result.input_segment_rows}")
    print(f"output_segment_rows={result.output_segment_rows}")
    print(f"removed_segment_conflict_rows={result.removed_segment_conflict_rows}")
    print(f"strict_current_mismatch_rows={result.strict_current_mismatch_rows}")
    print(
        "strict_unenforceable_glossary_rows="
        f"{result.strict_unenforceable_glossary_rows}"
    )
    print(
        "strict_removed_segment_mismatch_rows="
        f"{result.strict_removed_segment_mismatch_rows}"
    )
    for action, count in result.term_action_counts.most_common():
        print(f"term_action.{action}={count}")
    for action, count in result.row_action_counts.most_common():
        print(f"row_action.{action}={count}")
    print(f"review_dir={result.review_dir}")


if __name__ == "__main__":
    raise SystemExit(main())
