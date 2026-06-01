"""Glossary/segment cross-cleaning core (ADR-0007, ADR-0018, ADR-0019).

Extracted from the former ``scripts/segments_glossary_cross_cleaning_pipeline.py``
under ADR-0033. The domain logic is split across models, io, matching, scoring,
classify, and review modules; this package re-exports the public entry surface.
The entry script keeps only thin sys.path + main wiring.
"""

from __future__ import annotations

from .models import (
    CrossLexicons,
    GlossaryTerm,
    PipelineResult,
    SegmentRow,
    TermMatch,
)
from .pipeline import main, run_pipeline

__all__ = [
    "CrossLexicons",
    "GlossaryTerm",
    "PipelineResult",
    "SegmentRow",
    "TermMatch",
    "main",
    "run_pipeline",
]
