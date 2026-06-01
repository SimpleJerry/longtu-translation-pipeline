"""Data models and CSV field schemas for glossary/segment cross-cleaning.

Extracted verbatim from the former ``scripts/segments_glossary_cross_cleaning_pipeline.py``
under ADR-0033. Pure data and type definitions: no I/O, no orchestration.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path


SEGMENT_SCHEMA = ["segment_id", "zh-CN", "ko"]
GLOSSARY_SCHEMA = ["term_id", "zh-CN", "ko"]

TERM_SUMMARY_FIELDS = [
    "term_id",
    "term_zh-CN",
    "expected_ko",
    "term_action",
    "occurrence_count",
    "preserved_count",
    "missing_count",
    "missing_rate",
    "preserved_rate",
    "domain_score",
    "weak_score",
    "strict_term_action",
    "strict_enforceability_reason",
]

ROW_AUDIT_FIELDS = [
    "original_segment_id",
    "row_action",
    "matched_terms",
    "missing_terms",
    "missing_strong_terms",
    "missing_glossary_noise_terms",
    "strict_row_action",
    "strict_missing_terms",
    "zh-CN",
    "ko",
]

REMOVED_GLOSSARY_FIELDS = [
    "original_term_id",
    "term_zh-CN",
    "expected_ko",
    "occurrence_count",
    "preserved_count",
    "missing_count",
    "missing_rate",
    "preserved_rate",
    "domain_score",
    "weak_score",
    "remove_reason",
]

REMOVED_SEGMENT_FIELDS = [
    "removed_id",
    "original_segment_id",
    "zh-CN",
    "ko",
    "missing_strong_terms",
    "term_level_stats",
    "remove_reason",
]

SUMMARY_FIELDS = ["metric", "value"]

STRICT_REMOVED_GLOSSARY_FIELDS = [
    "original_term_id",
    "term_zh-CN",
    "expected_ko",
    "occurrence_count",
    "preserved_count",
    "missing_count",
    "missing_rate",
    "preserved_rate",
    "domain_score",
    "weak_score",
    "remove_reason",
]

STRICT_REMOVED_SEGMENT_FIELDS = [
    "removed_id",
    "original_segment_id",
    "zh-CN",
    "ko",
    "strict_missing_terms",
    "remove_reason",
]


@dataclass(frozen=True)
class GlossaryTerm:
    term_id: str
    zh: str
    ko: str


@dataclass(frozen=True)
class SegmentRow:
    segment_id: str
    zh: str
    ko: str


@dataclass(frozen=True)
class TermMatch:
    term: GlossaryTerm
    start: int
    end: int
    preserved: bool


@dataclass(frozen=True)
class CrossLexicons:
    general_words_zh: set[str]
    common_nouns_zh: set[str]
    nonterm_exact: set[str]
    game_anchors: list[str]
    game_term_seeds: set[str]
    acronym_whitelist: set[str]
    noun_suffixes: list[str]
    compound_suffixes: list[str]


@dataclass(frozen=True)
class PipelineResult:
    mode: str
    input_glossary_rows: int
    output_glossary_rows: int
    removed_glossary_noise_rows: int
    input_segment_rows: int
    output_segment_rows: int
    removed_segment_conflict_rows: int
    review_dir: Path
    term_action_counts: Counter[str]
    row_action_counts: Counter[str]
    strict_current_mismatch_rows: int
    strict_unenforceable_glossary_rows: int
    strict_removed_segment_mismatch_rows: int
