"""Data models, action constants, and regexes for segment LLM cleanup.

Extracted verbatim from the former ``scripts/segments_llm_cleanup_pipeline.py``
under ADR-0033. Pure data and type definitions: no I/O, no orchestration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from longtu_translation_pipeline.llm import ClientConfig


SEGMENT_SCHEMA = ["segment_id", "zh-CN", "ko"]
GLOSSARY_SCHEMA = ["term_id", "zh-CN", "ko"]

KEEP_ACTION = "KEEP_SEGMENT"
REWRITE_ACTION = "REWRITE_KO"
REVIEW_ACTION = "REVIEW_UNCERTAIN"
REMOVE_ACTIONS = {
    "REMOVE_NON_SEGMENT",
    "REMOVE_BAD_PAIR",
    "REMOVE_TARGET_CONTAMINATION",
}
VALID_ACTIONS = {KEEP_ACTION, REWRITE_ACTION, REVIEW_ACTION, *REMOVE_ACTIONS}

HANGUL_RE = re.compile(r"[가-힣]")
CJK_RE = re.compile(r"[㐀-鿿]")
PLACEHOLDER_RE = re.compile(
    r"\{[A-Za-z0-9_]+\}|%[sdif]|%\d+\$[sdif]|\$\{[^}]+\}|<key\d+>|<[^>\s]+>"
)
STRUCTURED_RE = re.compile(r"^\s*[\{\[]\s*['\"].*['\"]\s*[\}\]]\s*$")
EXPLANATION_RE = re.compile(r"(translation|corrected|번역|수정|설명|理由|原因|改写)")


@dataclass(frozen=True)
class SegmentRow:
    segment_id: str
    zh: str
    ko: str


@dataclass(frozen=True)
class GlossaryTerm:
    term_id: str
    zh: str
    ko: str


@dataclass(frozen=True)
class SegmentFeatures:
    placeholders: list[str]
    glossary_terms: list[GlossaryTerm]
    target_contamination: bool
    structured_hint: bool


@dataclass(frozen=True)
class Decision:
    segment_id: str
    action: str
    reason: str
    corrected_ko: str
    batch_no: int = 0


@dataclass(frozen=True)
class RowOutcome:
    row: SegmentRow
    decision: Decision
    features: SegmentFeatures
    final_action: str
    validation_status: str
    validation_errors: list[str]
    final_ko: str


@dataclass(frozen=True)
class CleanupResult:
    mode: str
    input_rows: int
    output_rows: int
    kept_rows: int
    removed_rows: int
    rewritten_rows: int
    rewrite_failed_rows: int
    review_rows: int
    review_dir: Path
    model: str
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    action_counts: dict[str, int]


Client = Callable[[dict[str, Any], ClientConfig, float, int], dict[str, Any]]
