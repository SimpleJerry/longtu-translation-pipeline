from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.config import load_evaluation_config  # noqa: E402
from longtu_translation_pipeline.evaluation import (  # noqa: E402
    evaluate_translation,
    format_evaluation_summary,
    write_evaluation_reports,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate translation CSV output.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "evaluation" / "default.json"))
    parser.add_argument("--input", help="Override translation-result CSV path.")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    config = load_evaluation_config(args.config, base_dir=ROOT)
    input_override = Path(args.input) if args.input else None
    result = evaluate_translation(config, input_override=input_override)
    print(format_evaluation_summary(result))
    if config.output.write_reports:
        write_evaluation_reports(result, config.output.report_dir)
        print(f"report_dir={config.output.report_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
