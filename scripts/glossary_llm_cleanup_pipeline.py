"""Aggressively prune glossary rows with an OpenAI-compatible LLM.

This pipeline is intentionally delete-only.  It sends the current
``data/glossary.csv`` term pairs to a cloud LLM and asks whether each pair
should remain in the company game glossary.  The model may keep or remove rows,
but it must not rewrite Korean, add terms, or merge entries.  Review artifacts
are written under ignored ``data/review/`` paths.

Thin entry point under ADR-0033: argparse + main wiring only. All domain logic
lives in ``longtu_translation_pipeline.cleanup.glossary_llm``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.cleanup.glossary_llm.models import (  # noqa: E402
    CleanupResult,
)
from longtu_translation_pipeline.cleanup.glossary_llm.pipeline import (  # noqa: E402
    run_cleanup,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete-only cloud LLM cleanup for data/glossary.csv."
    )
    parser.add_argument("--glossary", default="data/glossary.csv")
    parser.add_argument(
        "--review-dir", default="data/review/llm_glossary_cleanup"
    )
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override OPENAI_BASE_URL. Defaults to https://api.openai.com/v1.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override LLM_MODEL. The repository intentionally has no default.",
    )
    parser.add_argument(
        "--batch-mode",
        choices=["sync", "batch"],
        default="batch",
        help="sync: legacy synchronous /v1/chat/completions per micro-batch. "
        "batch: submit one /v1/batches job for the whole glossary (50%% discount). "
        "Default: batch.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=None,
        help="Cap on completion tokens per micro-batch. Defaults to batch_size*30.",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=60,
        help="Seconds between batch status polls (batch mode only).",
    )
    parser.add_argument(
        "--max-wait-sec",
        type=int,
        default=24 * 3600,
        help="Maximum seconds to wait for a batch job to complete.",
    )
    parser.add_argument(
        "--completion-window",
        default="24h",
        help="Completion window passed to /v1/batches (batch mode only).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Write review only.")
    mode.add_argument("--apply", action="store_true", help="Rewrite glossary.csv.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mode = "apply" if args.apply else "dry-run"
    try:
        result = run_cleanup(
            glossary_path=Path(args.glossary),
            review_dir=Path(args.review_dir),
            apply_changes=args.apply,
            batch_size=args.batch_size,
            max_retries=args.max_retries,
            temperature=args.temperature,
            timeout=args.timeout,
            base_url=args.base_url,
            model=args.model,
            batch_mode=args.batch_mode,
            max_output_tokens=args.max_output_tokens,
            poll_interval_sec=args.poll_interval,
            max_wait_sec=args.max_wait_sec,
            completion_window=args.completion_window,
        )
    except RuntimeError as exc:
        print(f"Glossary LLM cleanup failed in {mode} mode: {exc}")
        return 1
    print_result(result)
    return 0


def print_result(result: CleanupResult) -> None:
    print("LLM glossary cleanup completed.")
    print(f"mode={result.mode}")
    print(f"model={result.model}")
    print(f"input_rows={result.input_rows}")
    print(f"kept_rows={result.kept_rows}")
    print(f"removed_rows={result.removed_rows}")
    print(f"review_dir={result.review_dir}")
    print(f"prompt_tokens={result.total_prompt_tokens}")
    print(f"completion_tokens={result.total_completion_tokens}")
    print(f"total_tokens={result.total_tokens}")
    for action, count in sorted(result.action_counts.items()):
        print(f"action.{action}={count}")


if __name__ == "__main__":
    raise SystemExit(main())
