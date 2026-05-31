"""Cross-check glossary terms against segment translations.

This pipeline sits between the standalone glossary cleanup and segment cleanup
passes.  It uses the current final CSVs only: raw source files are not required
or committed.  The goal is deliberately narrow:

* remove glossary entries that behave like weak/common words and are frequently
  not translated with their glossary Korean form;
* remove segment rows that miss a strong glossary term which has enough
  preserved evidence elsewhere in the corpus.
* optionally enforce a strict pre-training gate: after removing glossary terms
  that are not enforceable, every remaining glossary match in every segment
  must preserve the glossary Korean form.

The script never rewrites Korean text.  Replacing a translation fragment can
break grammar, so strong conflicts are exported for review and optionally
removed from the training corpus with ``--apply``.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from longtu_translation_pipeline.cleanup.common import (  # noqa: E402
    ensure_csv_columns,
    read_json_config,
    read_term_file,
)


SEGMENT_SCHEMA = ["segment_id", "zh-CN", "ko"]
GLOSSARY_SCHEMA = ["term_id", "zh-CN", "ko"]

TERM_SUMMARY_FIELDS = [
    "term_id",
    "term_zh-CN",
    "expected_ko",
    "term_action",
    "occurrence_count",
    "preserved_count",
    "missing_count",
    "missing_rate",
    "preserved_rate",
    "domain_score",
    "weak_score",
    "strict_term_action",
    "strict_enforceability_reason",
]

ROW_AUDIT_FIELDS = [
    "original_segment_id",
    "row_action",
    "matched_terms",
    "missing_terms",
    "missing_strong_terms",
    "missing_glossary_noise_terms",
    "strict_row_action",
    "strict_missing_terms",
    "zh-CN",
    "ko",
]

REMOVED_GLOSSARY_FIELDS = [
    "original_term_id",
    "term_zh-CN",
    "expected_ko",
    "occurrence_count",
    "preserved_count",
    "missing_count",
    "missing_rate",
    "preserved_rate",
    "domain_score",
    "weak_score",
    "remove_reason",
]

REMOVED_SEGMENT_FIELDS = [
    "removed_id",
    "original_segment_id",
    "zh-CN",
    "ko",
    "missing_strong_terms",
    "term_level_stats",
    "remove_reason",
]

SUMMARY_FIELDS = ["metric", "value"]

STRICT_REMOVED_GLOSSARY_FIELDS = [
    "original_term_id",
    "term_zh-CN",
    "expected_ko",
    "occurrence_count",
    "preserved_count",
    "missing_count",
    "missing_rate",
    "preserved_rate",
    "domain_score",
    "weak_score",
    "remove_reason",
]

STRICT_REMOVED_SEGMENT_FIELDS = [
    "removed_id",
    "original_segment_id",
    "zh-CN",
    "ko",
    "strict_missing_terms",
    "remove_reason",
]


@dataclass(frozen=True)
class GlossaryTerm:
    term_id: str
    zh: str
    ko: str


@dataclass(frozen=True)
class SegmentRow:
    segment_id: str
    zh: str
    ko: str


@dataclass(frozen=True)
class TermMatch:
    term: GlossaryTerm
    start: int
    end: int
    preserved: bool


@dataclass(frozen=True)
class CrossLexicons:
    general_words_zh: set[str]
    common_nouns_zh: set[str]
    nonterm_exact: set[str]
    game_anchors: list[str]
    game_term_seeds: set[str]
    acronym_whitelist: set[str]
    noun_suffixes: list[str]
    compound_suffixes: list[str]


@dataclass(frozen=True)
class PipelineResult:
    mode: str
    input_glossary_rows: int
    output_glossary_rows: int
    removed_glossary_noise_rows: int
    input_segment_rows: int
    output_segment_rows: int
    removed_segment_conflict_rows: int
    review_dir: Path
    term_action_counts: Counter[str]
    row_action_counts: Counter[str]
    strict_current_mismatch_rows: int
    strict_unenforceable_glossary_rows: int
    strict_removed_segment_mismatch_rows: int


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


def classify_corpus(
    segment_rows: list[SegmentRow],
    terms: list[GlossaryTerm],
    lexicons: CrossLexicons,
    rules: dict[str, Any],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    term_stats: dict[str, dict[str, Any]] = {
        term.term_id: {
            "term": term,
            "occurrence_count": 0,
            "preserved_count": 0,
            "missing_count": 0,
        }
        for term in terms
    }
    raw_row_matches: list[tuple[SegmentRow, list[TermMatch]]] = []

    for row in segment_rows:
        matches = find_term_matches(row.zh, row.ko, terms)
        raw_row_matches.append((row, matches))
        for match in matches:
            stats = term_stats[match.term.term_id]
            stats["occurrence_count"] += 1
            if match.preserved:
                stats["preserved_count"] += 1
            else:
                stats["missing_count"] += 1

    term_summaries = build_term_summaries(term_stats, lexicons, rules)
    action_by_term = {row["term_id"]: row["term_action"] for row in term_summaries}
    summary_by_term = {row["term_id"]: row for row in term_summaries}
    row_audits = [
        build_row_audit(row, matches, action_by_term, summary_by_term)
        for row, matches in raw_row_matches
    ]
    return term_summaries, row_audits


def build_term_summaries(
    term_stats: dict[str, dict[str, Any]],
    lexicons: CrossLexicons,
    rules: dict[str, Any],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    thresholds = rules["thresholds"]
    for term_id in sorted(term_stats, key=lambda value: int_or_text(value)):
        stats = term_stats[term_id]
        term: GlossaryTerm = stats["term"]
        occurrence_count = stats["occurrence_count"]
        preserved_count = stats["preserved_count"]
        missing_count = stats["missing_count"]
        missing_rate = missing_count / occurrence_count if occurrence_count else 0.0
        preserved_rate = preserved_count / occurrence_count if occurrence_count else 0.0
        domain_score = score_domain(term.zh, lexicons, rules)
        weak_score = score_weak(term.zh, domain_score, lexicons, rules)
        action = classify_term(
            occurrence_count=occurrence_count,
            preserved_count=preserved_count,
            missing_rate=missing_rate,
            domain_score=domain_score,
            weak_score=weak_score,
            thresholds=thresholds,
        )
        strict_action, strict_reason = classify_strict_term(
            occurrence_count=occurrence_count,
            preserved_count=preserved_count,
            missing_count=missing_count,
            missing_rate=missing_rate,
            preserved_rate=preserved_rate,
            domain_score=domain_score,
            weak_score=weak_score,
            thresholds=thresholds,
        )
        rows.append(
            {
                "term_id": term.term_id,
                "term_zh-CN": term.zh,
                "expected_ko": term.ko,
                "term_action": action,
                "occurrence_count": str(occurrence_count),
                "preserved_count": str(preserved_count),
                "missing_count": str(missing_count),
                "missing_rate": format_score(missing_rate),
                "preserved_rate": format_score(preserved_rate),
                "domain_score": format_score(domain_score),
                "weak_score": format_score(weak_score),
                "strict_term_action": strict_action,
                "strict_enforceability_reason": strict_reason,
            }
        )
    return rows


def classify_term(
    occurrence_count: int,
    preserved_count: int,
    missing_rate: float,
    domain_score: float,
    weak_score: float,
    thresholds: dict[str, Any],
) -> str:
    if (
        occurrence_count >= thresholds["min_term_occurrences"]
        and missing_rate >= thresholds["glossary_noise_missing_rate"]
        and weak_score >= thresholds["weak_score_min"]
        and domain_score < thresholds["strong_domain_score_min"]
    ):
        return "AUTO_REMOVE_GLOSSARY_NOISE"
    if (
        domain_score >= thresholds["strong_domain_score_min"]
        and preserved_count >= thresholds["segment_conflict_preserved_min"]
        and missing_rate <= thresholds["segment_conflict_missing_rate_max"]
    ):
        return "STRONG_GLOSSARY_TERM"
    return "TERM_NEEDS_REVIEW"


def classify_strict_term(
    occurrence_count: int,
    preserved_count: int,
    missing_count: int,
    missing_rate: float,
    preserved_rate: float,
    domain_score: float,
    weak_score: float,
    thresholds: dict[str, Any],
) -> tuple[str, str]:
    if missing_count == 0:
        return "STRICT_CLEAN", "no_missing_terms"

    is_weak = weak_score >= thresholds["weak_score_min"]
    domain_enforceable = (
        domain_score >= thresholds["strong_domain_score_min"]
        and preserved_count >= thresholds["domain_enforce_preserved_min"]
        and missing_rate <= thresholds["domain_enforce_missing_rate_max"]
    )
    if domain_enforceable:
        return "STRICT_RETAIN_AND_ENFORCE", "domain_preserved_evidence"

    empirical_enforceable = (
        preserved_count >= thresholds["empirical_enforce_preserved_min"]
        and preserved_rate >= thresholds["empirical_enforce_preserved_rate_min"]
        and not is_weak
    )
    if empirical_enforceable:
        return "STRICT_RETAIN_AND_ENFORCE", "empirical_stable_translation"

    return "AUTO_REMOVE_GLOSSARY_UNENFORCEABLE", "not_enforceable_in_segments"


def build_row_audit(
    row: SegmentRow,
    matches: list[TermMatch],
    action_by_term: dict[str, str],
    summary_by_term: dict[str, dict[str, str]],
) -> dict[str, str]:
    missing_matches = [match for match in matches if not match.preserved]
    missing_strong = [
        match
        for match in missing_matches
        if action_by_term[match.term.term_id] == "STRONG_GLOSSARY_TERM"
    ]
    missing_noise = [
        match
        for match in missing_matches
        if action_by_term[match.term.term_id] == "AUTO_REMOVE_GLOSSARY_NOISE"
    ]
    if missing_strong:
        action = "AUTO_REMOVE_SEGMENT_CONFLICT"
    elif missing_matches and len(missing_matches) == len(missing_noise):
        action = "KEEP_AFTER_GLOSSARY_NOISE_REMOVAL"
    elif missing_matches:
        action = "ROW_NEEDS_REVIEW"
    else:
        action = "KEEP"

    # action_by_term is the normal action map; strict removal is injected below
    # by checking term summaries directly to keep the default RF-011 behavior
    # independent from the strict pre-training gate.
    strict_missing = [
        match
        for match in missing_matches
        if summary_by_term[match.term.term_id]["strict_term_action"]
        != "AUTO_REMOVE_GLOSSARY_UNENFORCEABLE"
    ]
    if strict_missing:
        strict_action = "STRICT_REMOVE_SEGMENT_MISMATCH"
    elif missing_matches:
        strict_action = "STRICT_KEEP_AFTER_GLOSSARY_REMOVAL"
    else:
        strict_action = "STRICT_KEEP"

    return {
        "original_segment_id": row.segment_id,
        "row_action": action,
        "matched_terms": serialize_matches(matches),
        "missing_terms": serialize_matches(missing_matches),
        "missing_strong_terms": serialize_matches(missing_strong),
        "missing_glossary_noise_terms": serialize_matches(missing_noise),
        "strict_row_action": strict_action,
        "strict_missing_terms": serialize_matches(strict_missing),
        "zh-CN": row.zh,
        "ko": row.ko,
        "_term_level_stats": serialize_term_stats(missing_strong, summary_by_term),
    }


def find_term_matches(
    source: str, target: str, terms: list[GlossaryTerm]
) -> list[TermMatch]:
    matches: list[TermMatch] = []
    occupied: list[tuple[int, int]] = []
    for term in terms:
        start = source.find(term.zh)
        while start >= 0:
            end = start + len(term.zh)
            if not overlaps_any(start, end, occupied):
                occupied.append((start, end))
                matches.append(
                    TermMatch(
                        term=term,
                        start=start,
                        end=end,
                        preserved=contains_exact_or_no_space(target, term.ko),
                    )
                )
            start = source.find(term.zh, start + 1)
    return sorted(matches, key=lambda match: (match.start, match.end))


def contains_exact_or_no_space(text: str, expected: str) -> bool:
    if expected in text:
        return True
    normalized_text = normalize_no_space(text)
    normalized_expected = normalize_no_space(expected)
    return bool(normalized_expected and normalized_expected in normalized_text)


def normalize_no_space(text: str) -> str:
    return re.sub(r"\s+", "", text)


def overlaps_any(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(not (end <= span_start or start >= span_end) for span_start, span_end in spans)


def score_domain(
    zh: str,
    lexicons: CrossLexicons,
    rules: dict[str, Any],
) -> float:
    scores = rules["scores"]
    upper = zh.upper()
    candidates = [0.0]
    if zh in lexicons.game_term_seeds:
        candidates.append(scores["game_seed"])
    if any(anchor and anchor in zh for anchor in lexicons.game_anchors):
        candidates.append(scores["domain_anchor"])
    if any(acronym and acronym.upper() in upper for acronym in lexicons.acronym_whitelist):
        candidates.append(scores["acronym"])
    if any(suffix and zh.endswith(suffix) for suffix in lexicons.compound_suffixes):
        candidates.append(scores["compound_suffix"])
    if any(suffix and zh.endswith(suffix) for suffix in lexicons.noun_suffixes):
        candidates.append(scores["noun_suffix"])
    length = cjk_len(zh)
    if length >= 6:
        candidates.append(scores["length_six_plus"])
    elif length >= 4:
        candidates.append(scores["length_four_plus"])
    return min(max(candidates), 1.0)


def score_weak(
    zh: str,
    domain_score: float,
    lexicons: CrossLexicons,
    rules: dict[str, Any],
) -> float:
    scores = rules["scores"]
    candidates = [0.0]
    if zh in lexicons.nonterm_exact:
        candidates.append(scores["weak_exact"])
    if zh in lexicons.general_words_zh or zh in lexicons.common_nouns_zh:
        candidates.append(scores["common_word"])
    if cjk_len(zh) <= 2 and domain_score < rules["thresholds"]["strong_domain_score_min"]:
        candidates.append(scores["short_weak"])
    return min(max(candidates), 1.0)


def cjk_len(text: str) -> int:
    return sum(1 for char in text if "\u4e00" <= char <= "\u9fff")


def int_or_text(value: str) -> tuple[int, str]:
    try:
        return (int(value), value)
    except ValueError:
        return (10**12, value)


def serialize_matches(matches: list[TermMatch]) -> str:
    return "|".join(
        f"{match.term.term_id}:{match.term.zh}=>{match.term.ko}"
        for match in matches
    )


def serialize_term_stats(
    matches: list[TermMatch], summary_by_term: dict[str, dict[str, str]]
) -> str:
    parts: list[str] = []
    for match in matches:
        summary = summary_by_term[match.term.term_id]
        parts.append(
            ";".join(
                [
                    f"term_id={match.term.term_id}",
                    f"occ={summary['occurrence_count']}",
                    f"preserved={summary['preserved_count']}",
                    f"missing={summary['missing_count']}",
                    f"missing_rate={summary['missing_rate']}",
                    f"domain_score={summary['domain_score']}",
                ]
            )
        )
    return "|".join(parts)


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


def format_score(value: float) -> str:
    return f"{value:.6f}"


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
