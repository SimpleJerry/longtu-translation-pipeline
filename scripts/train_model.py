from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.config import load_training_config  # noqa: E402
from longtu_translation_pipeline.training import (  # noqa: E402
    build_training_dry_run,
    build_training_smoke_test,
    format_training_dry_run,
    format_training_smoke_test,
    format_nllb_trainer_smoke_test,
    run_nllb_trainer_smoke_test,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Training entry point for RF-006.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "training" / "default.json"))
    parser.add_argument("--dry-run", action="store_true", help="Validate config and data without training.")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run a local tokenizer/dataset smoke test without loading NLLB.",
    )
    parser.add_argument(
        "--nllb-smoke-test",
        action="store_true",
        help="Run a real NLLB tokenizer plus tiny Trainer one-step smoke test.",
    )
    parser.add_argument(
        "--smoke-rows",
        type=int,
        default=3,
        help="Number of rows to tokenize during --smoke-test.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    if not args.dry_run and not args.smoke_test and not args.nllb_smoke_test:
        print(
            "Actual model training is deferred to a later RF-006 phase. "
            "Re-run with --dry-run, --smoke-test, or --nllb-smoke-test."
        )
        return 2

    config = load_training_config(args.config, base_dir=ROOT)
    outputs: list[str] = []
    if args.dry_run:
        outputs.append(format_training_dry_run(build_training_dry_run(config)))
    if args.smoke_test:
        tokenizer = build_local_smoke_tokenizer()
        plan = build_training_smoke_test(
            config,
            tokenizer,
            tokenizer_name="local-transformers-smoke-tokenizer",
            sample_rows=args.smoke_rows,
        )
        outputs.append(format_training_smoke_test(plan))
    if args.nllb_smoke_test:
        result = run_nllb_trainer_smoke_test(
            config,
            output_dir=ROOT / "data" / "review" / "training_smoke",
            sample_rows=args.smoke_rows,
        )
        outputs.append(format_nllb_trainer_smoke_test(result))

    print("\n\n".join(outputs))
    return 0


def build_local_smoke_tokenizer():
    """Build a tiny local tokenizer through transformers/tokenizers without downloads."""

    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from transformers import PreTrainedTokenizerFast

    vocab = {"[PAD]": 0, "[UNK]": 1, "<start>": 2, "<end>": 3}
    backend = Tokenizer(WordLevel(vocab=vocab, unk_token="[UNK]"))
    backend.pre_tokenizer = Whitespace()
    return PreTrainedTokenizerFast(
        tokenizer_object=backend,
        unk_token="[UNK]",
        pad_token="[PAD]",
        additional_special_tokens=["<start>", "<end>"],
    )


if __name__ == "__main__":
    raise SystemExit(main())
