"""Data models, action constants, and CSV field schemas for glossary LLM cleanup.

Extracted verbatim from the former ``scripts/glossary_llm_cleanup_pipeline.py``
under ADR-0033. Pure data and type definitions: no I/O, no orchestration.
This pipeline is delete-only (ADR-0025): the model may keep or remove rows but
never rewrites Korean, adds, or merges terms.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from longtu_translation_pipeline.llm import ClientConfig


GLOSSARY_SCHEMA = ["term_id", "zh-CN", "ko"]
SUMMARY_FIELDS = ["metric", "value"]
AUDIT_FIELDS = [
    "original_term_id",
    "action",
    "keep",
    "reason",
    "zh-CN",
    "ko",
]
REMOVED_FIELDS = [
    "removed_id",
    "original_term_id",
    "action",
    "reason",
    "zh-CN",
    "ko",
]

KEEP_ACTION = "KEEP_GAME_TERM"
REMOVE_ACTIONS = {
    "REMOVE_COMMON_WORD",
    "REMOVE_PHRASE_OR_SENTENCE",
    "REMOVE_FRAGMENT",
    "REMOVE_BAD_PAIR",
    "REMOVE_NOT_COMPANY_GAME_TERM",
}
VALID_ACTIONS = {KEEP_ACTION, *REMOVE_ACTIONS}


@dataclass(frozen=True)
class GlossaryRow:
    term_id: str
    zh: str
    ko: str


@dataclass(frozen=True)
class Decision:
    term_id: str
    action: str
    reason: str


@dataclass(frozen=True)
class CleanupResult:
    mode: str
    input_rows: int
    kept_rows: int
    removed_rows: int
    review_dir: Path
    model: str
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    action_counts: dict[str, int]


Client = Callable[[dict[str, Any], ClientConfig, float, int], dict[str, Any]]
