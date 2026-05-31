"""Local semantic glossary cleanup core (ADR-0008, ADR-0018).

Extracted from the former ``scripts/glossary_semantic_pipeline.py`` under
ADR-0033 as a whole-module move (``git mv``): the entry script keeps only thin
wiring and this package holds the logic. Unlike the segments_llm extraction,
the fine-grained module split is intentionally deferred to a later increment
that first adds test coverage for the untested heavy paths (``classify_rows``,
``write_outputs``), so the move stays provably behavior-preserving.
"""

from __future__ import annotations

from .pipeline import load_pipeline_config, main

__all__ = ["load_pipeline_config", "main"]
