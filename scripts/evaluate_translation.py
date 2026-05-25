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
    parser.add_argument("--checkpoint", help="Checkpoint path to record in report metadata.")
    parser.add_argument("--report-dir", help="Override evaluation report directory.")
    parser.add_argument(
        "--sample-review-rows",
        type=int,
        default=50,
        help="Number of rows to write to sample_review.csv.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    config = load_evaluation_config(args.config, base_dir=ROOT)
    input_override = resolve_cli_path(args.input)
    report_dir = resolve_cli_path(args.report_dir) or config.output.report_dir
    checkpoint_path = resolve_cli_path(args.checkpoint)
    result = evaluate_translation(config, input_override=input_override)
    print(format_evaluation_summary(result))
    if config.output.write_reports:
        write_evaluation_reports(
            result,
            report_dir,
            checkpoint_path=checkpoint_path,
            config_path=Path(args.config),
            sample_review_rows=args.sample_review_rows,
        )
        print(f"report_dir={report_dir}")
    return 0


def resolve_cli_path(value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
