from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.config import load_inference_config  # noqa: E402
from longtu_translation_pipeline.inference import (  # noqa: E402
    build_inference_dry_run,
    format_inference_generation,
    format_inference_dry_run,
    format_validation_generation,
    generate_validation_translations,
    generate_translations,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inference entry point for RF-006.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "inference" / "default.json"))
    parser.add_argument("--dry-run", action="store_true", help="Validate config and data without inference.")
    parser.add_argument("--generate", action="store_true", help="Generate sample translations with a checkpoint.")
    parser.add_argument(
        "--generate-validation",
        action="store_true",
        help="Generate translations for a P7 run validation split.",
    )
    parser.add_argument("--model-path", help="Checkpoint path to load for generation.")
    parser.add_argument("--output", help="CSV output path for generation.")
    parser.add_argument("--run-dir", help="P7 training run directory for --generate-validation.")
    parser.add_argument(
        "--sample-rows",
        type=int,
        default=8,
        help="Number of input rows to generate during --generate.",
    )
    parser.add_argument(
        "--validation-rows",
        type=int,
        default=None,
        help="Optional number of validation split rows to generate.",
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cuda", "cpu"],
        default="auto",
        help="Device for --generate.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    if not args.dry_run and not args.generate and not args.generate_validation:
        print("Re-run with --dry-run, --generate, or --generate-validation.")
        return 2
    if args.generate and args.generate_validation:
        print("Choose only one of --generate or --generate-validation.")
        return 2
    if args.generate_validation and not args.run_dir:
        print("--run-dir is required with --generate-validation.")
        return 2

    config = load_inference_config(args.config, base_dir=ROOT)
    outputs: list[str] = []
    if args.dry_run:
        outputs.append(format_inference_dry_run(build_inference_dry_run(config)))
    if args.generate:
        result = generate_translations(
            config,
            model_path=resolve_cli_path(args.model_path),
            output_path=resolve_cli_path(args.output),
            sample_rows=args.sample_rows,
            device=args.device,
        )
        outputs.append(format_inference_generation(result))
    if args.generate_validation:
        result = generate_validation_translations(
            config,
            run_dir=resolve_cli_path(args.run_dir),
            model_path=resolve_cli_path(args.model_path),
            output_path=resolve_cli_path(args.output),
            validation_rows=args.validation_rows,
            device=args.device,
            repo_root=ROOT,
        )
        outputs.append(format_validation_generation(result))

    print("\n\n".join(outputs))
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
