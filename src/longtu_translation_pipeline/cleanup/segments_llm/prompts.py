"""Prompt construction and JSON response schema (ADR-0026, ADR-0030).

Extracted verbatim from the former ``scripts/segments_llm_cleanup_pipeline.py``
under ADR-0033. The request carries only segment_id, zh-CN, ko, detected
placeholders, and matched glossary terms — never the local pre-judgment flags
(target contamination, structured hint), per ADR-0026. The response is
constrained by a strict ``json_schema`` (ADR-0030).
"""

from __future__ import annotations

import json
from typing import Any

from .features import build_features
from .models import GlossaryTerm, SegmentRow, VALID_ACTIONS


SYSTEM_PROMPT = (
    "You are a Chinese-to-Korean game localization segment reviewer. Review each "
    "row independently by its own meaning, not by applying a bulk rule to the "
    "whole batch. You may keep, remove, mark uncertain, or rewrite only the "
    "Korean target. The reason for every row must quote or name a specific "
    "Chinese term, Korean phrase, or structural pattern from that row — a generic "
    "verdict ('의미가 정확함', '语义准确', 'natural translation') is not acceptable. "
    "Never reference another row ('同上', 'same as above', '이전과 동일', '동일 이유'). "
    "Do not return code, pseudocode, rules, batch "
    "summaries, or explanations outside the required JSON. Never change Chinese "
    "source, add rows, split rows, merge rows, or edit glossary terms. Every "
    "row in the results array must include corrected_ko: an empty string for "
    "non-rewrite actions, never null."
)


def _segments_response_schema() -> dict[str, Any]:
    """JSON schema enforced via response_format=json_schema strict.

    Built lazily so VALID_ACTIONS (set ordering) is captured at call time.
    """
    return {
        "name": "segment_review_results",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["results"],
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "segment_id",
                            "action",
                            "reason",
                            "corrected_ko",
                        ],
                        "properties": {
                            "segment_id": {"type": "string"},
                            "action": {
                                "type": "string",
                                "enum": sorted(VALID_ACTIONS),
                            },
                            "reason": {"type": "string", "minLength": 1},
                            "corrected_ko": {"type": "string"},
                        },
                    },
                },
            },
        },
    }


def build_request_payload(
    model: str,
    batch: list[SegmentRow],
    glossary_sorted: list[GlossaryTerm],
    temperature: float,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in batch:
        features = build_features(row, glossary_sorted)
        rows.append(
            {
                "segment_id": row.segment_id,
                "zh-CN": row.zh,
                "ko": row.ko,
                "placeholder_tokens": features.placeholders,
                "glossary_terms": [
                    {"term_id": term.term_id, "zh-CN": term.zh, "ko": term.ko}
                    for term in features.glossary_terms
                ],
            }
        )

    user_payload = {
        "task": "Review every segment row independently and optionally rewrite only Korean.",
        "allowed_actions": sorted(VALID_ACTIONS),
        "policy": [
            "Judge each row by its own Chinese and Korean meaning; do not bulk-apply a surface rule across the batch.",
            "Use the glossary_terms only as required terminology constraints for this row.",
            "Use placeholder_tokens only to preserve machine placeholders; do not treat placeholders alone as a removal reason.",
            "Keep usable seq2seq sentence or phrase pairs, even if they are short UI text.",
            "Remove only when this row is not a trainable segment, is a bad semantic pair, or has unusable target-language content.",
            "Use REWRITE_KO only when a natural Korean target is clearly derivable from zh-CN and the glossary constraints.",
            "If uncertain, choose REVIEW_UNCERTAIN rather than guessing.",
            "The reason must name a concrete element from this row's own Chinese source or Korean target — e.g. '\"技能\" is correctly rendered as \"스킬\"' or '\"不分派别\" is wrongly translated as \"정사파\"'. Generic quality verdicts such as '의미가 정확함', '语义准确', or 'natural translation' are not acceptable. Never use cross-row references ('同上', 'same as above', 'see above').",
            "Do not change zh-CN, add rows, split rows, merge rows, or output explanations outside JSON.",
            "corrected_ko must always be a string; use \"\" (empty string, never null) when the action is not REWRITE_KO.",
        ],
        "output_schema": {
            "results": [
                {
                    "segment_id": "same string as input",
                    "action": "one allowed action",
                    "reason": "short reason",
                    "corrected_ko": "required only for REWRITE_KO, otherwise empty",
                }
            ]
        },
        "rows": rows,
    }
    payload: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        # Strict json_schema rejects malformed shapes server-side and lets
        # the local parser drop its regex fallback. Every row must include
        # corrected_ko as a string (empty for non-REWRITE actions).
        "response_format": {
            "type": "json_schema",
            "json_schema": _segments_response_schema(),
        },
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    }
    if max_output_tokens is not None:
        payload["max_tokens"] = max_output_tokens
    return payload
