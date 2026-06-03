"""Cross-check glossary terms against segment translations — thin entry point
(ADR-0033).

All logic lives in
``longtu_translation_pipeline.cleanup.segments_glossary_cross``. This script
only wires sys.path to the src package and invokes ``main``.
"""

from __future__ import annotations

from longtu_translation_pipeline.cleanup.segments_glossary_cross import main


if __name__ == "__main__":
    raise SystemExit(main())
