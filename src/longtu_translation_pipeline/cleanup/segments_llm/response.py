"""LLM response parsing, validation, and truncation recovery.

Extracted verbatim from the former ``scripts/segments_llm_cleanup_pipeline.py``
under ADR-0033. Degrades gracefully on malformed or truncated output: an
unrecognised action or missing/duplicate segment_id becomes REVIEW_UNCERTAIN
rather than killing the whole micro-batch (discovered during the T-A1 run).
"""

from __future__ import annotations

import json
from typing import Any

from longtu_translation_pipeline.llm import parse_json_content

from .models import (
    Decision,
    REVIEW_ACTION,
    REWRITE_ACTION,
    SegmentRow,
    VALID_ACTIONS,
)


def _recover_truncated_results(content: str) -> dict[str, Any]:
    """Extract whatever complete result objects exist in a truncated JSON response.

    The model output is cut mid-array; we walk the content with a JSON decoder
    to collect every fully-formed object before the truncation point.
    """
    decoder = json.JSONDecoder()
    results: list[Any] = []
    start = content.find("[")
    if start == -1:
        return {"results": results}
    pos = start + 1
    while pos < len(content):
        tail = content[pos:].lstrip()
        if not tail or tail[0] == "]":
            break
        skip = len(content[pos:]) - len(tail)
        try:
            obj, end = decoder.raw_decode(tail)
        except json.JSONDecodeError:
            break
        if isinstance(obj, dict):
            results.append(obj)
        pos += skip + end
        while pos < len(content) and content[pos] in ", \t\n\r":
            pos += 1
    return {"results": results}


def parse_and_validate_response(
    response: dict[str, Any], batch: list[SegmentRow]
) -> list[Decision]:
    choices = response.get("choices") or []
    finish_reason = choices[0].get("finish_reason") if choices else None
    truncated = finish_reason == "length"

    content = extract_message_content(response)
    try:
        payload = parse_json_content(content)
    except RuntimeError:
        if truncated:
            payload = _recover_truncated_results(content)
        else:
            raise

    results = payload.get("results")
    if not isinstance(results, list):
        if truncated:
            results = []
        else:
            raise RuntimeError("LLM response JSON must contain a 'results' list.")

    expected_ids = {row.segment_id for row in batch}
    decisions: dict[str, Decision] = {}
    for index, item in enumerate(results, 1):
        if not isinstance(item, dict):
            if not truncated:
                raise RuntimeError(f"Result #{index} must be a JSON object.")
            continue
        segment_id = str(item.get("segment_id", "")).strip()
        action = str(item.get("action", "")).strip()
        reason = str(item.get("reason", "")).strip()
        corrected_ko = str(item.get("corrected_ko", "")).strip()
        if segment_id not in expected_ids:
            if not truncated:
                print(
                    f"WARNING: Unexpected segment_id {segment_id!r} in LLM result "
                    f"(finish_reason={finish_reason!r}); ignoring."
                )
            continue
        if segment_id in decisions:
            if not truncated:
                print(
                    f"WARNING: Duplicate segment_id {segment_id!r} in LLM result "
                    f"(finish_reason={finish_reason!r}); keeping first occurrence."
                )
            continue
        if action not in VALID_ACTIONS:
            if not truncated:
                print(
                    f"WARNING: Invalid action {action!r} for segment_id {segment_id!r} "
                    f"(finish_reason={finish_reason!r}); marking as {REVIEW_ACTION}."
                )
                action = REVIEW_ACTION
                reason = reason or f"invalid action {action!r} from LLM"
            else:
                continue
        if not reason:
            if not truncated:
                print(
                    f"WARNING: Missing reason for segment_id {segment_id!r} "
                    f"(finish_reason={finish_reason!r}); using placeholder."
                )
                reason = "no reason provided by LLM"
            else:
                continue
        if action == REWRITE_ACTION and not corrected_ko:
            # Model returned REWRITE_KO with empty corrected_ko — demote to REVIEW.
            if not truncated:
                print(
                    f"WARNING: REWRITE_KO missing corrected_ko for segment_id {segment_id!r}; "
                    f"demoting to {REVIEW_ACTION}."
                )
            action = REVIEW_ACTION
            reason = f"REWRITE_KO missing corrected_ko (original reason: {reason})"
        decisions[segment_id] = Decision(segment_id, action, reason, corrected_ko)

    missing = expected_ids - set(decisions)
    if missing:
        reason = (
            "response truncated by token limit"
            if truncated
            else "segment omitted from LLM response"
        )
        if not truncated:
            print(
                f"WARNING: LLM response missing segment_id(s) {sorted(missing)} "
                f"(finish_reason={finish_reason!r}); marking as {REVIEW_ACTION}."
            )
        for seg_id in missing:
            decisions[seg_id] = Decision(
                segment_id=seg_id,
                action=REVIEW_ACTION,
                reason=reason,
                corrected_ko="",
            )
    return [decisions[row.segment_id] for row in batch]


def extract_message_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("LLM response has no choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise RuntimeError("LLM response choice must be an object.")
    message = first.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("LLM response choice has no message object.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM response message content is empty.")
    return content.strip()
