"""Local semantic glossary cleanup core (ADR-0008, ADR-0018).

Extracted from the former ``scripts/glossary_semantic_pipeline.py`` under
ADR-0033 (step 9b: fine-grained module split).  Domain logic is split into
focused modules: config / io / nlp / scoring / classify / review; pipeline.py
is the thin entry-point re-exporting the public surface.
"""

from __future__ import annotations

from .pipeline import load_pipeline_config, main

__all__ = ["load_pipeline_config", "main"]
