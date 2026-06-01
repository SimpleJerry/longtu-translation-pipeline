"""Audit and summary row builders for glossary LLM cleanup.

Extracted verbatim from the former ``scripts/glossary_llm_cleanup_pipeline.py``
under ADR-0033. Pure transformations from decisions to review-CSV rows; the
actual file writes live in :mod:`.io` and the orchestrator.
"""

from __future__ import annotations

from longtu_translation_pipeline.llm import ClientConfig

from .models import Decision, GlossaryRow, KEEP_ACTION


def build_audit_rows(
    rows: list[GlossaryRow], decisions: dict[str, Decision]
) -> list[dict[str, str]]:
    audit_rows: list[dict[str, str]] = []
    for row in rows:
        decision = decisions[row.term_id]
        audit_rows.append(
            {
                "original_term_id": row.term_id,
                "action": decision.action,
                "keep": "YES" if decision.action == KEEP_ACTION else "NO",
                "reason": decision.reason,
                "zh-CN": row.zh,
                "ko": row.ko,
            }
        )
    return audit_rows


def build_summary_rows(
    mode: str,
    rows: list[GlossaryRow],
    audit_rows: list[dict[str, str]],
    client_config: ClientConfig,
    total_usage: dict[str, int],
) -> list[dict[str, str]]:
    kept = sum(1 for row in audit_rows if row["keep"] == "YES")
    removed = len(audit_rows) - kept
    summary = [
        {"metric": "mode", "value": mode},
        {"metric": "model", "value": client_config.model},
        {"metric": "input_rows", "value": str(len(rows))},
        {"metric": "kept_rows", "value": str(kept)},
        {"metric": "removed_rows", "value": str(removed)},
        {
            "metric": "prompt_tokens",
            "value": str(total_usage.get("prompt_tokens", 0)),
        },
        {
            "metric": "completion_tokens",
            "value": str(total_usage.get("completion_tokens", 0)),
        },
        {"metric": "total_tokens", "value": str(total_usage.get("total_tokens", 0))},
    ]
    counts: dict[str, int] = {}
    for row in audit_rows:
        counts[row["action"]] = counts.get(row["action"], 0) + 1
    for action in sorted(counts):
        summary.append({"metric": f"action.{action}", "value": str(counts[action])})
    return summary
