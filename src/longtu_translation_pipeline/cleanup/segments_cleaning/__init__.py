"""Review-first deterministic segment cleanup core (ADR-0013, ADR-0027).

Extracted from the former ``scripts/segments_cleaning_pipeline.py`` under
ADR-0033 (step 8b: fine-grained module split).  Domain logic is split into
focused modules: io / normalize / nlp / scoring / classify; pipeline.py is the
thin entry-point re-exporting the public surface.
"""

from __future__ import annotations

from .pipeline import main

__all__ = ["main"]
