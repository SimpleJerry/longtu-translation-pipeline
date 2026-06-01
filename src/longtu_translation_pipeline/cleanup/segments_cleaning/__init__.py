"""Review-first deterministic segment cleanup core (ADR-0013, ADR-0027).

Extracted from the former ``scripts/segments_cleaning_pipeline.py`` under
ADR-0033 as a whole-module move (``git mv``): the entry script keeps only thin
wiring and this package holds the logic. As with glossary_semantic (ADR-0033
step 3b), the fine-grained module split is deferred to a later increment that
first adds test coverage for the untested heavy paths (Stanza/embedding/jieba/
kiwi scoring, ``main`` orchestration), so the move stays provably
behavior-preserving.
"""

from __future__ import annotations

from .pipeline import main

__all__ = ["main"]
