"""Glossary-level LLM cleanup core (ADR-0025, ADR-0030).

Extracted from the former ``scripts/glossary_llm_cleanup_pipeline.py`` under
ADR-0033. The entry script keeps only argparse + main wiring; all domain logic
(models, prompts, response parsing, resumable batch-state machine, I/O, review
reporting, and orchestration) lives in this package.

This is a pure behavior-preserving move: function bodies are unchanged from the
original single-file pipeline. The re-export below lets callers reach the public
surface as ``from longtu_translation_pipeline.cleanup.glossary_llm import ...``.
"""

from __future__ import annotations

from .models import (
    CleanupResult,
    Client,
    Decision,
    GlossaryRow,
    KEEP_ACTION,
    REMOVE_ACTIONS,
    VALID_ACTIONS,
)
from .pipeline import run_cleanup

__all__ = [
    "CleanupResult",
    "Client",
    "Decision",
    "GlossaryRow",
    "KEEP_ACTION",
    "REMOVE_ACTIONS",
    "VALID_ACTIONS",
    "run_cleanup",
]
