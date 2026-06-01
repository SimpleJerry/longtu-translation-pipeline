"""Glossary/segment cross-cleaning core (ADR-0007, ADR-0018, ADR-0019).

Extracted from the former ``scripts/segments_glossary_cross_cleaning_pipeline.py``
under ADR-0033 as a whole-module move (``git mv``): the entry script keeps only
thin wiring and this package holds the logic. The fine-grained module split is
deferred to a later increment, consistent with the other git-mv extractions
(ADR-0033 steps 3b, 5), so the move stays provably behavior-preserving.
"""

from __future__ import annotations

from .pipeline import main, run_pipeline

__all__ = ["main", "run_pipeline"]
