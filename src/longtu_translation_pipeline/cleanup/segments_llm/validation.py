"""Rewrite validation and outcome construction (ADR-0026).

Extracted verbatim from the former ``scripts/segments_llm_cleanup_pipeline.py``
under ADR-0033. A Korean rewrite is accepted only after all local guards pass:
Hangul present, no Chinese CJK, placeholders preserved, glossary terms kept
(exact or no-space), no copy/explanation, sane length ratio, no excessive
repetition. A failed rewrite keeps the original row, unless the original target
is contaminated, in which case the row is removed.
"""

from __future__ import annotations

import re

from .models import (
    CJK_RE,
    Decision,
    EXPLANATION_RE,
    HANGUL_RE,
    PLACEHOLDER_RE,
    REMOVE_ACTIONS,
    REVIEW_ACTION,
    REWRITE_ACTION,
    RowOutcome,
    SegmentFeatures,
    SegmentRow,
)


def build_outcome(
    row: SegmentRow, decision: Decision, features: SegmentFeatures
) -> RowOutcome:
    if decision.action in REMOVE_ACTIONS:
        return RowOutcome(
            row=row,
            decision=decision,
            features=features,
            final_action="REMOVE",
            validation_status="REMOVE_REQUESTED",
            validation_errors=[],
            final_ko="",
        )
    if decision.action == REWRITE_ACTION:
        errors = validate_rewrite(row, decision.corrected_ko, features)
        if not errors:
            return RowOutcome(
                row=row,
                decision=decision,
                features=features,
                final_action="REWRITE",
                validation_status="REWRITE_ACCEPTED",
                validation_errors=[],
                final_ko=decision.corrected_ko,
            )
        if features.target_contamination:
            return RowOutcome(
                row=row,
                decision=decision,
                features=features,
                final_action="REMOVE",
                validation_status="REWRITE_REJECTED_REMOVE_CONTAMINATED",
                validation_errors=errors,
                final_ko="",
            )
        return RowOutcome(
            row=row,
            decision=decision,
            features=features,
            final_action="KEEP",
            validation_status="REWRITE_REJECTED",
            validation_errors=errors,
            final_ko=row.ko,
        )
    if decision.action == REVIEW_ACTION:
        return RowOutcome(
            row=row,
            decision=decision,
            features=features,
            final_action="REVIEW",
            validation_status="REVIEW",
            validation_errors=[],
            final_ko=row.ko,
        )
    return RowOutcome(
        row=row,
        decision=decision,
        features=features,
        final_action="KEEP",
        validation_status="KEEP",
        validation_errors=[],
        final_ko=row.ko,
    )


def validate_rewrite(
    row: SegmentRow, corrected_ko: str, features: SegmentFeatures
) -> list[str]:
    errors: list[str] = []
    if not corrected_ko.strip():
        errors.append("empty_corrected_ko")
    if CJK_RE.search(corrected_ko):
        errors.append("corrected_ko_contains_cjk")
    if not HANGUL_RE.search(corrected_ko):
        errors.append("corrected_ko_has_no_hangul")
    expected_placeholders = set(features.placeholders)
    corrected_placeholders = set(PLACEHOLDER_RE.findall(corrected_ko))
    if expected_placeholders - corrected_placeholders:
        errors.append("placeholder_missing")
    if corrected_placeholders - expected_placeholders:
        errors.append("placeholder_extra")
    if any(not term_preserved(term.ko, corrected_ko) for term in features.glossary_terms):
        errors.append("glossary_term_missing")
    if looks_like_copy_or_explanation(row.zh, corrected_ko):
        errors.append("copy_or_explanation_like")
    if has_bad_length_ratio(row.ko, corrected_ko):
        errors.append("length_ratio_outlier")
    if has_excessive_repetition(corrected_ko):
        errors.append("excessive_repetition")
    return errors


def term_preserved(term_ko: str, text: str) -> bool:
    return term_ko in text or remove_spaces(term_ko) in remove_spaces(text)


def remove_spaces(text: str) -> str:
    return re.sub(r"\s+", "", text)


def looks_like_copy_or_explanation(source: str, corrected_ko: str) -> bool:
    if CJK_RE.search(corrected_ko):
        return True
    if source.strip() and corrected_ko.strip() == source.strip():
        return True
    return bool(EXPLANATION_RE.search(corrected_ko))


def has_bad_length_ratio(original_ko: str, corrected_ko: str) -> bool:
    original_len = max(len(original_ko.strip()), 1)
    corrected_len = len(corrected_ko.strip())
    return corrected_len > max(240, original_len * 4) or corrected_len < max(1, original_len // 8)


def has_excessive_repetition(text: str) -> bool:
    tokens = [token for token in re.split(r"\s+", text.strip()) if token]
    if len(tokens) >= 8:
        most_common = max(tokens.count(token) for token in set(tokens))
        return most_common / len(tokens) > 0.55
    return bool(re.search(r"(.{2,12})\1{4,}", text))
