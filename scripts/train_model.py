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
    format_formal_training_run,
    format_training_dry_run,
    format_training_smoke_test,
    format_nllb_trainer_smoke_test,
    format_real_model_pilot_training,
    format_real_model_smoke_test,
    run_real_nllb_formal_training,
    run_real_nllb_pilot_training,
    run_real_nllb_model_smoke_test,
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
        "--real-model-smoke-test",
        action="store_true",
        help="Run a real NLLB model one-step Trainer smoke test.",
    )
    parser.add_argument(
        "--pilot-train",
        action="store_true",
        help="Run real NLLB pilot training with checkpoint and resume validation.",
    )
    parser.add_argument(
        "--train",
        action="store_true",
        help="Run a formal real-model training command with split artifacts and a run manifest.",
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cuda", "cpu"],
        default="auto",
        help="Device for real-model smoke and pilot training.",
    )
    parser.add_argument(
        "--smoke-rows",
        type=int,
        default=3,
        help="Number of rows to tokenize during --smoke-test.",
    )
    parser.add_argument(
        "--pilot-rows",
        type=int,
        default=64,
        help="Number of rows to use during --pilot-train.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Final Trainer max_steps for training modes. Formal --train also accepts this from config.",
    )
    parser.add_argument(
        "--save-steps",
        type=int,
        default=None,
        help="Checkpoint save interval for training modes. Formal --train also accepts this from config.",
    )
    parser.add_argument(
        "--eval-steps",
        type=int,
        default=None,
        help="Evaluation interval for formal --train; defaults to config or save_steps.",
    )
    parser.add_argument(
        "--save-total-limit",
        type=int,
        default=None,
        help="Maximum number of checkpoints to keep for --train.",
    )
    parser.add_argument(
        "--logging-steps",
        type=int,
        default=None,
        help="Trainer logging interval for --train.",
    )
    parser.add_argument(
        "--gradient-accumulation-steps",
        type=int,
        default=None,
        help="Gradient accumulation steps for formal --train.",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=None,
        help="Learning rate for formal --train.",
    )
    parser.add_argument(
        "--warmup-ratio",
        type=float,
        default=None,
        help="Warmup ratio for formal --train.",
    )
    parser.add_argument(
        "--weight-decay",
        type=float,
        default=None,
        help="Weight decay for formal --train.",
    )
    parser.add_argument(
        "--max-grad-norm",
        type=float,
        default=None,
        help="Max gradient norm for formal --train.",
    )
    parser.add_argument(
        "--limit-rows",
        type=int,
        default=None,
        help="Optional row limit for --train engineering validation; omit for full data.",
    )
    parser.add_argument(
        "--run-name",
        default=None,
        help="Optional run directory name under the configured runs directory for --train.",
    )
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Optional explicit run directory for --train or resume.",
    )
    parser.add_argument(
        "--resume-from-checkpoint",
        default=None,
        help="Checkpoint path or 'latest' for --train resume.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    if (
        not args.dry_run
        and not args.smoke_test
        and not args.nllb_smoke_test
        and not args.real_model_smoke_test
        and not args.pilot_train
        and not args.train
    ):
        print(
            "Full model training is deferred to a later RF-006 phase. "
            "Re-run with --dry-run, --smoke-test, --nllb-smoke-test, "
            "--real-model-smoke-test, --pilot-train, or --train."
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
    if args.real_model_smoke_test:
        result = run_real_nllb_model_smoke_test(
            config,
            output_dir=ROOT / "data" / "review" / "training_smoke" / "real_model",
            sample_rows=args.smoke_rows,
            device=args.device,
        )
        outputs.append(format_real_model_smoke_test(result))
    if args.pilot_train:
        result = run_real_nllb_pilot_training(
            config,
            pilot_rows=args.pilot_rows,
            max_steps=args.max_steps if args.max_steps is not None else 4,
            save_steps=args.save_steps if args.save_steps is not None else 2,
            device=args.device,
        )
        outputs.append(format_real_model_pilot_training(result))
    if args.train:
        try:
            result = run_real_nllb_formal_training(
                config,
                run_dir=args.run_dir,
                run_name=args.run_name,
                row_limit=args.limit_rows,
                max_steps=args.max_steps,
                save_steps=args.save_steps,
                eval_steps=args.eval_steps,
                save_total_limit=args.save_total_limit,
                logging_steps=args.logging_steps,
                gradient_accumulation_steps=args.gradient_accumulation_steps,
                learning_rate=args.learning_rate,
                warmup_ratio=args.warmup_ratio,
                weight_decay=args.weight_decay,
                max_grad_norm=args.max_grad_norm,
                device=args.device,
                resume_from_checkpoint=args.resume_from_checkpoint,
                command=sys.argv,
                repo_root=ROOT,
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        outputs.append(format_formal_training_run(result))

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
