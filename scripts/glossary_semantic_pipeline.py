"""Local semantic glossary cleanup — thin entry point (ADR-0033).

All logic lives in ``longtu_translation_pipeline.cleanup.glossary_semantic``.
This script only wires sys.path to the src package and invokes ``main``.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.cleanup.glossary_semantic import main  # noqa: E402


if __name__ == "__main__":
    main()
