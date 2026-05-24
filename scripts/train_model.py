from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.config import load_training_config  # noqa: E402
from longtu_translation_pipeline.training import (  # noqa: E402
    build_training_dry_run,
    format_training_dry_run,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Training entry point for RF-006 phase 1.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "training" / "default.json"))
    parser.add_argument("--dry-run", action="store_true", help="Validate config and data without training.")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    if not args.dry_run:
        print("Actual model training is deferred to a later RF-006 phase. Re-run with --dry-run.")
        return 2

    config = load_training_config(args.config, base_dir=ROOT)
    plan = build_training_dry_run(config)
    print(format_training_dry_run(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
