"""LLM response parsing and validation for glossary cleanup.

Extracted verbatim from the former ``scripts/glossary_llm_cleanup_pipeline.py``
under ADR-0033. Glossary cleanup is strict (ADR-0025): an invalid action,
duplicate, unexpected, or missing term_id raises and triggers a whole-batch
retry rather than degrading to a review fallback.
"""

from __future__ import annotations

from typing import Any

from longtu_translation_pipeline.llm import parse_json_content

from .models import Decision, GlossaryRow, VALID_ACTIONS


def parse_and_validate_response(
    response: dict[str, Any], batch: list[GlossaryRow]
) -> list[Decision]:
    content = extract_message_content(response)
    payload = parse_json_content(content)
    results = payload.get("results")
    if not isinstance(results, list):
        raise RuntimeError("LLM response JSON must contain a 'results' list.")

    expected_ids = {row.term_id for row in batch}
    decisions: dict[str, Decision] = {}
    for index, item in enumerate(results, 1):
        if not isinstance(item, dict):
            raise RuntimeError(f"Result #{index} must be a JSON object.")
        term_id = str(item.get("term_id", "")).strip()
        action = str(item.get("action", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if term_id not in expected_ids:
            raise RuntimeError(f"Unexpected term_id in LLM result: {term_id}")
        if term_id in decisions:
            raise RuntimeError(f"Duplicate term_id in LLM result: {term_id}")
        if action not in VALID_ACTIONS:
            raise RuntimeError(f"Invalid action for term_id {term_id}: {action}")
        if not reason:
            raise RuntimeError(f"Missing reason for term_id {term_id}.")
        decisions[term_id] = Decision(term_id=term_id, action=action, reason=reason)

    missing = expected_ids - set(decisions)
    if missing:
        raise RuntimeError(f"LLM response is missing term_id values: {sorted(missing)}")
    return [decisions[row.term_id] for row in batch]


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
