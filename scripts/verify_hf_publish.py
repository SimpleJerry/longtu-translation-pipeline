"""Post-publish self-check: verify that all required files are reachable on HF Hub.

Usage:
    python scripts/verify_hf_publish.py --repo SimpleJerry/longtu-nllb-zh2ko \\
        --tag earlystop-v1-ckpt48000 [--skip-model-load]

HF_TOKEN must be set in the environment.
"""
from __future__ import annotations

import argparse
import os
import sys

REQUIRED_FILES = [
    "config.json",
    "generation_config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "run_manifest.json",
    "README.md",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify HF Hub publish (ADR-0036).")
    parser.add_argument("--repo", default="SimpleJerry/longtu-nllb-zh2ko")
    parser.add_argument("--tag", default="earlystop-v1-ckpt48000")
    parser.add_argument(
        "--skip-model-load",
        action="store_true",
        help="Skip AutoModelForSeq2SeqLM.from_pretrained (saves ~2.3 GB download).",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("[ERROR] HF_TOKEN not set.", file=sys.stderr)
        return 1

    from huggingface_hub import HfApi

    api = HfApi(token=token)

    print(f"[1/3] Listing files in {args.repo} @ {args.tag} …")
    repo_files = list(api.list_repo_files(args.repo, repo_type="model", revision=args.tag))
    print(f"      Found {len(repo_files)} file(s):")
    for f in sorted(repo_files):
        print(f"        {f}")

    missing = [f for f in REQUIRED_FILES if f not in repo_files]
    if missing:
        print(f"\n[FAIL] Missing required files: {missing}", file=sys.stderr)
        return 1
    print("      All required files present. OK")

    print(f"\n[2/3] Loading tokenizer from {args.repo}@{args.tag} …")
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        args.repo,
        revision=args.tag,
        token=token,
    )
    print(f"      Tokenizer loaded. Vocab size: {tokenizer.vocab_size}")

    if not args.skip_model_load:
        print(f"\n[3/3] Loading model from {args.repo}@{args.tag} (~2.3 GB) …")
        from transformers import AutoModelForSeq2SeqLM

        model = AutoModelForSeq2SeqLM.from_pretrained(
            args.repo,
            revision=args.tag,
            token=token,
        )
        num_params = sum(p.numel() for p in model.parameters())
        print(f"      Model loaded. Parameters: {num_params:,}")
    else:
        print("\n[3/3] Model load skipped (--skip-model-load).")

    print("\n[PASS] All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
