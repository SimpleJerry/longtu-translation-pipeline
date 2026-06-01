"""Segment-level LLM cleanup core (ADR-0026, ADR-0030).

Extracted from the former ``scripts/segments_llm_cleanup_pipeline.py`` under
ADR-0033. The entry script keeps only argparse + main wiring; all domain logic
(models, features, prompts, response parsing, rewrite validation, resumable
batch-state machine, review reporting, and orchestration) lives in this package.

This is a pure behavior-preserving move: function bodies are unchanged from the
original single-file pipeline. The re-export below lets callers reach the public
surface as ``from longtu_translation_pipeline.cleanup.segments_llm import ...``.
"""

from __future__ import annotations

from .models import (
    CleanupResult,
    Client,
    Decision,
    GlossaryTerm,
    KEEP_ACTION,
    REMOVE_ACTIONS,
    REVIEW_ACTION,
    REWRITE_ACTION,
    RowOutcome,
    SegmentFeatures,
    SegmentRow,
    VALID_ACTIONS,
)
from .pipeline import run_cleanup

__all__ = [
    "CleanupResult",
    "Client",
    "Decision",
    "GlossaryTerm",
    "KEEP_ACTION",
    "REMOVE_ACTIONS",
    "REVIEW_ACTION",
    "REWRITE_ACTION",
    "RowOutcome",
    "SegmentFeatures",
    "SegmentRow",
    "VALID_ACTIONS",
    "run_cleanup",
]
