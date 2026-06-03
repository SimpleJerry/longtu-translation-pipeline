"""Review-first semantic cleanup for Chinese-Korean segment training data —
thin entry point (ADR-0033).

All logic lives in ``longtu_translation_pipeline.cleanup.segments_cleaning``.
This script only wires sys.path to the src package and invokes ``main``.
"""

from __future__ import annotations

from longtu_translation_pipeline.cleanup.segments_cleaning import main


if __name__ == "__main__":
    main()
