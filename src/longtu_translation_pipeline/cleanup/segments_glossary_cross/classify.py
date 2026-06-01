"""Corpus classification: term-level and row-level actions for cross-cleaning.

Extracted verbatim from the former ``scripts/segments_glossary_cross_cleaning_pipeline.py``
under ADR-0033. Decides which glossary terms are noise/strong/needs-review and
which segment rows conflict, including the strict pre-training gate (ADR-0019).
Delete-only: never rewrites Korean (ADR-0018).
"""

from __future__ import annotations

from typing import Any

from .matching import find_term_matches
from .models import CrossLexicons, GlossaryTerm, SegmentRow, TermMatch
from .scoring import score_domain, score_weak


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


def format_score(value: float) -> str:
    return f"{value:.6f}"
