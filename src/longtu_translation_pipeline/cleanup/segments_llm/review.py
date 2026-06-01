"""Review-artifact reporting for segment LLM cleanup (ADR-0026).

Extracted verbatim from the former ``scripts/segments_llm_cleanup_pipeline.py``
under ADR-0033. Writes the audit, removed, rewritten, rewrite-failed, balanced
sample-review, warning, and summary CSVs under the ignored review directory.
Also computes the reason-repetition and surface-feature warnings that flag
suspected bulk-rule behavior in the model's output.
"""

from __future__ import annotations

import re
from pathlib import Path

from longtu_translation_pipeline.llm import ClientConfig

from .io import write_csv
from .models import GlossaryTerm, REWRITE_ACTION, RowOutcome


AUDIT_FIELDS = [
    "original_segment_id",
    "final_action",
    "llm_action",
    "validation_status",
    "reason",
    "validation_errors",
    "placeholder_tokens",
    "glossary_terms",
    "target_contamination",
    "structured_hint",
    "zh-CN",
    "original_ko",
    "corrected_ko",
    "final_ko",
]
REMOVED_FIELDS = [
    "removed_id",
    "original_segment_id",
    "remove_reason",
    "llm_action",
    "reason",
    "zh-CN",
    "ko",
    "corrected_ko",
]
REWRITTEN_FIELDS = [
    "rewrite_id",
    "original_segment_id",
    "reason",
    "zh-CN",
    "original_ko",
    "corrected_ko",
    "glossary_terms",
]
REWRITE_FAILED_FIELDS = [
    "failed_id",
    "original_segment_id",
    "reason",
    "validation_errors",
    "zh-CN",
    "original_ko",
    "corrected_ko",
    "glossary_terms",
]
SUMMARY_FIELDS = ["metric", "value"]
WARNING_FIELDS = ["warning_type", "scope", "value", "count", "rate", "details"]
SAMPLE_REVIEW_FIELDS = [
    "sample_id",
    "original_segment_id",
    "final_action",
    "llm_action",
    "validation_status",
    "reason",
    "validation_errors",
    "zh-CN",
    "original_ko",
    "corrected_ko",
    "final_ko",
]

REASON_REPETITION_WARNING_RATE = 0.60
REASON_REPETITION_MIN_BATCH_ROWS = 5
SURFACE_FEATURE_WARNING_MIN_ROWS = 5


def write_review_files(
    review_dir: Path,
    outcomes: list[RowOutcome],
    total_usage: dict[str, int],
    client_config: ClientConfig,
    apply_changes: bool,
    sample_review_rows: int,
) -> None:
    audit_rows = [audit_row(outcome) for outcome in outcomes]
    removed = [outcome for outcome in outcomes if outcome.final_action == "REMOVE"]
    rewritten = [outcome for outcome in outcomes if outcome.final_action == "REWRITE"]
    rewrite_failed = [
        outcome for outcome in outcomes if outcome.validation_status.startswith("REWRITE_REJECTED")
    ]
    warnings = warning_rows(outcomes)
    write_csv(review_dir / "segments_llm_audit.csv", AUDIT_FIELDS, audit_rows)
    write_csv(review_dir / "removed_segments_llm.csv", REMOVED_FIELDS, removed_rows(removed))
    write_csv(review_dir / "rewritten_segments_llm.csv", REWRITTEN_FIELDS, rewritten_rows(rewritten))
    write_csv(
        review_dir / "rewrite_failed_segments_llm.csv",
        REWRITE_FAILED_FIELDS,
        rewrite_failed_rows(rewrite_failed),
    )
    write_csv(
        review_dir / "segments_llm_sample_review.csv",
        SAMPLE_REVIEW_FIELDS,
        sample_review(outcomes, sample_review_rows),
    )
    write_csv(review_dir / "segments_llm_warnings.csv", WARNING_FIELDS, warnings)
    write_csv(
        review_dir / "segments_llm_summary.csv",
        SUMMARY_FIELDS,
        summary_rows(outcomes, total_usage, client_config, apply_changes, warnings),
    )


def audit_row(outcome: RowOutcome) -> dict[str, str]:
    return {
        "original_segment_id": outcome.row.segment_id,
        "final_action": outcome.final_action,
        "llm_action": outcome.decision.action,
        "validation_status": outcome.validation_status,
        "reason": outcome.decision.reason,
        "validation_errors": ";".join(outcome.validation_errors),
        "placeholder_tokens": ";".join(outcome.features.placeholders),
        "glossary_terms": format_terms(outcome.features.glossary_terms),
        "target_contamination": "YES" if outcome.features.target_contamination else "NO",
        "structured_hint": "YES" if outcome.features.structured_hint else "NO",
        "zh-CN": outcome.row.zh,
        "original_ko": outcome.row.ko,
        "corrected_ko": outcome.decision.corrected_ko,
        "final_ko": outcome.final_ko,
    }


def removed_rows(outcomes: list[RowOutcome]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for removed_id, outcome in enumerate(outcomes, 1):
        rows.append(
            {
                "removed_id": str(removed_id),
                "original_segment_id": outcome.row.segment_id,
                "remove_reason": outcome.validation_status,
                "llm_action": outcome.decision.action,
                "reason": outcome.decision.reason,
                "zh-CN": outcome.row.zh,
                "ko": outcome.row.ko,
                "corrected_ko": outcome.decision.corrected_ko,
            }
        )
    return rows


def rewritten_rows(outcomes: list[RowOutcome]) -> list[dict[str, str]]:
    return [
        {
            "rewrite_id": str(index),
            "original_segment_id": outcome.row.segment_id,
            "reason": outcome.decision.reason,
            "zh-CN": outcome.row.zh,
            "original_ko": outcome.row.ko,
            "corrected_ko": outcome.final_ko,
            "glossary_terms": format_terms(outcome.features.glossary_terms),
        }
        for index, outcome in enumerate(outcomes, 1)
    ]


def rewrite_failed_rows(outcomes: list[RowOutcome]) -> list[dict[str, str]]:
    return [
        {
            "failed_id": str(index),
            "original_segment_id": outcome.row.segment_id,
            "reason": outcome.decision.reason,
            "validation_errors": ";".join(outcome.validation_errors),
            "zh-CN": outcome.row.zh,
            "original_ko": outcome.row.ko,
            "corrected_ko": outcome.decision.corrected_ko,
            "glossary_terms": format_terms(outcome.features.glossary_terms),
        }
        for index, outcome in enumerate(outcomes, 1)
    ]


def sample_review(outcomes: list[RowOutcome], limit: int) -> list[dict[str, str]]:
    if limit == 0:
        return []
    grouped: dict[str, list[RowOutcome]] = {
        "REMOVE": [],
        "REWRITE": [],
        "REVIEW": [],
        "KEEP": [],
    }
    for outcome in outcomes:
        grouped.setdefault(outcome.final_action, []).append(outcome)

    selected: list[RowOutcome] = []
    indexes = {action: 0 for action in grouped}
    order = ["REMOVE", "REWRITE", "REVIEW", "KEEP"]
    while len(selected) < limit:
        added = False
        for action in order:
            index = indexes[action]
            if index < len(grouped[action]):
                selected.append(grouped[action][index])
                indexes[action] += 1
                added = True
                if len(selected) >= limit:
                    break
        if not added:
            break

    rows: list[dict[str, str]] = []
    for sample_id, outcome in enumerate(selected, 1):
        rows.append(
            {
                "sample_id": str(sample_id),
                "original_segment_id": outcome.row.segment_id,
                "final_action": outcome.final_action,
                "llm_action": outcome.decision.action,
                "validation_status": outcome.validation_status,
                "reason": outcome.decision.reason,
                "validation_errors": ";".join(outcome.validation_errors),
                "zh-CN": outcome.row.zh,
                "original_ko": outcome.row.ko,
                "corrected_ko": outcome.decision.corrected_ko,
                "final_ko": outcome.final_ko,
            }
        )
    return rows


def warning_rows(outcomes: list[RowOutcome]) -> list[dict[str, str]]:
    return reason_repetition_warnings(outcomes) + surface_feature_action_warnings(outcomes)


def reason_repetition_warnings(outcomes: list[RowOutcome]) -> list[dict[str, str]]:
    by_batch: dict[int, list[RowOutcome]] = {}
    for outcome in outcomes:
        by_batch.setdefault(outcome.decision.batch_no, []).append(outcome)

    rows: list[dict[str, str]] = []
    for batch_no, batch_outcomes in sorted(by_batch.items()):
        if len(batch_outcomes) < REASON_REPETITION_MIN_BATCH_ROWS:
            continue
        counts: dict[str, int] = {}
        examples: dict[str, str] = {}
        for outcome in batch_outcomes:
            normalized = normalize_reason(outcome.decision.reason)
            counts[normalized] = counts.get(normalized, 0) + 1
            examples.setdefault(normalized, outcome.decision.reason)
        reason, count = max(counts.items(), key=lambda item: item[1])
        rate = count / len(batch_outcomes)
        if rate >= REASON_REPETITION_WARNING_RATE:
            rows.append(
                {
                    "warning_type": "batch_reason_repetition_warning",
                    "scope": f"batch-{batch_no}",
                    "value": examples[reason],
                    "count": str(count),
                    "rate": format_rate(rate),
                    "details": f"{count}/{len(batch_outcomes)} rows share the same normalized reason",
                }
            )
    return rows


def surface_feature_action_warnings(outcomes: list[RowOutcome]) -> list[dict[str, str]]:
    feature_groups: list[tuple[str, list[RowOutcome]]] = [
        (
            "target_contamination",
            [outcome for outcome in outcomes if outcome.features.target_contamination],
        ),
        ("structured_hint", [outcome for outcome in outcomes if outcome.features.structured_hint]),
        ("has_placeholders", [outcome for outcome in outcomes if outcome.features.placeholders]),
        ("has_glossary_terms", [outcome for outcome in outcomes if outcome.features.glossary_terms]),
    ]
    rows: list[dict[str, str]] = []
    for feature_name, group in feature_groups:
        if len(group) < SURFACE_FEATURE_WARNING_MIN_ROWS:
            continue
        final_actions = {outcome.final_action for outcome in group}
        if len(final_actions) == 1:
            action = next(iter(final_actions))
            rows.append(
                {
                    "warning_type": "surface_feature_single_final_action_warning",
                    "scope": feature_name,
                    "value": action,
                    "count": str(len(group)),
                    "rate": "1.000000",
                    "details": f"All rows with local feature {feature_name}=YES ended as {action}",
                }
            )
        llm_actions = {outcome.decision.action for outcome in group}
        if len(llm_actions) == 1:
            action = next(iter(llm_actions))
            rows.append(
                {
                    "warning_type": "surface_feature_single_llm_action_warning",
                    "scope": feature_name,
                    "value": action,
                    "count": str(len(group)),
                    "rate": "1.000000",
                    "details": f"All rows with local feature {feature_name}=YES received {action}",
                }
            )
    return rows


def normalize_reason(reason: str) -> str:
    return re.sub(r"\s+", " ", reason.strip().casefold())


def format_rate(value: float) -> str:
    return f"{value:.6f}"


def summary_rows(
    outcomes: list[RowOutcome],
    total_usage: dict[str, int],
    client_config: ClientConfig,
    apply_changes: bool,
    warnings: list[dict[str, str]],
) -> list[dict[str, str]]:
    counts: dict[str, int] = {}
    llm_counts: dict[str, int] = {}
    for outcome in outcomes:
        counts[outcome.final_action] = counts.get(outcome.final_action, 0) + 1
        llm_counts[outcome.decision.action] = llm_counts.get(outcome.decision.action, 0) + 1
    rewrite_requested = llm_counts.get(REWRITE_ACTION, 0)
    rewrite_accepted = counts.get("REWRITE", 0)
    rewrite_rejected = sum(
        1 for outcome in outcomes if outcome.validation_status.startswith("REWRITE_REJECTED")
    )
    max_reason_count, max_reason_rate = global_reason_repetition(outcomes)
    rows = [
        {"metric": "mode", "value": "apply" if apply_changes else "dry-run"},
        {"metric": "model", "value": client_config.model},
        {"metric": "input_rows", "value": str(len(outcomes))},
        {"metric": "output_rows", "value": str(counts.get("KEEP", 0) + counts.get("REWRITE", 0) + counts.get("REVIEW", 0))},
        {"metric": "kept_rows", "value": str(counts.get("KEEP", 0))},
        {"metric": "removed_rows", "value": str(counts.get("REMOVE", 0))},
        {"metric": "rewritten_rows", "value": str(counts.get("REWRITE", 0))},
        {"metric": "review_rows", "value": str(counts.get("REVIEW", 0))},
        {"metric": "rewrite_requested_rows", "value": str(rewrite_requested)},
        {"metric": "rewrite_accepted_rows", "value": str(rewrite_accepted)},
        {"metric": "rewrite_rejected_rows", "value": str(rewrite_rejected)},
        {"metric": "rewrite_accept_rate", "value": format_rate(rewrite_accepted / rewrite_requested) if rewrite_requested else "0.000000"},
        {"metric": "rewrite_reject_rate", "value": format_rate(rewrite_rejected / rewrite_requested) if rewrite_requested else "0.000000"},
        {"metric": "rewrite_failed_rows", "value": str(rewrite_rejected)},
        {"metric": "max_reason_repetition_count", "value": str(max_reason_count)},
        {"metric": "max_reason_repetition_rate", "value": format_rate(max_reason_rate)},
        {
            "metric": "reason_repetition_warning_batches",
            "value": str(
                sum(
                    1
                    for warning in warnings
                    if warning["warning_type"] == "batch_reason_repetition_warning"
                )
            ),
        },
        {
            "metric": "surface_feature_warning_rows",
            "value": str(
                sum(
                    1
                    for warning in warnings
                    if warning["warning_type"].startswith("surface_feature_")
                )
            ),
        },
        {"metric": "prompt_tokens", "value": str(total_usage.get("prompt_tokens", 0))},
        {"metric": "completion_tokens", "value": str(total_usage.get("completion_tokens", 0))},
        {"metric": "total_tokens", "value": str(total_usage.get("total_tokens", 0))},
    ]
    for action in sorted(counts):
        rows.append({"metric": f"final_action.{action}", "value": str(counts[action])})
    for action in sorted(llm_counts):
        rows.append({"metric": f"llm_action.{action}", "value": str(llm_counts[action])})
    return rows


def global_reason_repetition(outcomes: list[RowOutcome]) -> tuple[int, float]:
    if not outcomes:
        return 0, 0.0
    counts: dict[str, int] = {}
    for outcome in outcomes:
        normalized = normalize_reason(outcome.decision.reason)
        counts[normalized] = counts.get(normalized, 0) + 1
    max_count = max(counts.values(), default=0)
    return max_count, max_count / len(outcomes)


def format_terms(terms: list[GlossaryTerm]) -> str:
    return ";".join(f"{term.term_id}:{term.zh}->{term.ko}" for term in terms)
