"""Prompt construction and JSON response schema for glossary LLM cleanup.

Extracted verbatim from the former ``scripts/glossary_llm_cleanup_pipeline.py``
under ADR-0033. The response is constrained by a strict ``json_schema``
(ADR-0030); the prompt only ever asks the model to keep or delete a row.
"""

from __future__ import annotations

import json
from typing import Any

from .models import GlossaryRow, VALID_ACTIONS


SYSTEM_PROMPT = (
    "You are cleaning a Chinese-Korean glossary for one company's game "
    "localization project. Keep only entries that deserve to be enforced as "
    "game terminology: game systems, skills, equipment, attributes, currencies, "
    "proper names, monsters, maps, titles, item names, and established game "
    "acronyms. Remove ordinary dictionary words, UI phrases, sentence-like "
    "content, fragments, invalid pairs, or entries that should not be company "
    "game glossary terms. Do not rewrite Korean, do not add terms, and do not "
    "merge terms. Return strict JSON only."
)


def _glossary_response_schema() -> dict[str, Any]:
    return {
        "name": "glossary_review_results",
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
                        "required": ["term_id", "action", "reason"],
                        "properties": {
                            "term_id": {"type": "string"},
                            "action": {
                                "type": "string",
                                "enum": sorted(VALID_ACTIONS),
                            },
                            "reason": {"type": "string", "minLength": 1},
                        },
                    },
                },
            },
        },
    }


def build_request_payload(
    model: str,
    batch: list[GlossaryRow],
    temperature: float,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    rows = [
        {"term_id": row.term_id, "zh-CN": row.zh, "ko": row.ko}
        for row in batch
    ]
    user_payload = {
        "task": "Classify every row. Return one result for every input term_id.",
        "allowed_actions": sorted(VALID_ACTIONS),
        "aggressive_policy": "Only KEEP_GAME_TERM rows will remain in glossary.csv.",
        "output_schema": {
            "results": [
                {
                    "term_id": "same string as input",
                    "action": "one allowed action",
                    "reason": "short Chinese or English reason, no rewrite",
                }
            ]
        },
        "rows": rows,
    }
    payload: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "parallel_tool_calls": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": _glossary_response_schema(),
        },
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            },
        ],
    }
    if max_output_tokens is not None:
        payload["max_tokens"] = max_output_tokens
    return payload
