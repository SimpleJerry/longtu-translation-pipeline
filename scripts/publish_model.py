"""Publish a fine-tuned checkpoint to a public Hugging Face Hub repository.

Contract: ADR-0037 — only inference-required files + run_manifest.json + a model
card are uploaded; optimizer / training-state files are never published.
HF_TOKEN (write scope) is required only for publishing; pulling the public repo
requires no token.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INFERENCE_PATTERNS = [
    "config.json",
    "generation_config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
]

DEFAULT_CHECKPOINT = str(
    ROOT
    / "fine-tuned-models"
    / "nllb-200-distilled-600M"
    / "zh2ko"
    / "runs"
    / "earlystop-v1"
    / "checkpoint-48000"
)
DEFAULT_REPO = "SimpleJerry/longtu-nllb-zh2ko"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Publish a fine-tuned NLLB checkpoint to a public HF Hub repo (ADR-0037). "
            "HF_TOKEN (write scope) must be set in the environment for publishing. "
            "The published repo is public; pulling requires no token."
        )
    )
    parser.add_argument(
        "--checkpoint",
        default=DEFAULT_CHECKPOINT,
        help="Path to the local checkpoint directory to publish.",
    )
    parser.add_argument(
        "--run-manifest",
        default=None,
        help=(
            "Path to run_manifest.json. "
            "Defaults to run_manifest.json in the parent of --checkpoint."
        ),
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help="HF Hub repo ID (e.g. 'SimpleJerry/longtu-nllb-zh2ko').",
    )
    parser.add_argument(
        "--tag",
        required=True,
        help="Git-style tag to create on the repo after uploading (e.g. 'earlystop-v1-ckpt48000').",
    )
    parser.add_argument(
        "--private",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Create the repo as private (default: False — public).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned operations without actually uploading anything.",
    )
    return parser.parse_args()


def _load_manifest(manifest_path: Path) -> dict:
    if not manifest_path.exists():
        print(f"[ERROR] run_manifest.json not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)
    with manifest_path.open(encoding="utf-8") as f:
        return json.load(f)


def _build_model_card(manifest: dict, repo: str, tag: str) -> str:
    data = manifest.get("data", {})
    corpus_sha256 = data.get("segments_sha256", "unknown")
    split_seed = data.get("split_seed", "unknown")
    model_name = manifest.get("model", {}).get("name", "facebook/nllb-200-distilled-600M")
    gen = manifest.get("training", {})
    best_metric = gen.get("best_metric_value")
    best_metric_str = f"{best_metric:.4f}" if best_metric is not None else "unknown"

    return f"""---
language:
- zh
- ko
license: cc-by-nc-4.0
tags:
- translation
- nllb
- fine-tuned
- game-localization
---

# longtu-nllb-zh2ko

Fine-tuned `{model_name}` for zh-CN → ko game localization translation.

**Public model. License: cc-by-nc-4.0 (inherited from NLLB-200; non-commercial use only).**
Trained on a proprietary game localization corpus; game-domain terminology is encoded in the
weights. The original corpus text is not distributed with this model.

## Task

Sequence-to-sequence translation: Simplified Chinese (`zho_Hans`) → Korean (`kor_Hang`)

## Base model

`{model_name}`

## Language pair

- Source: `zh-CN` (NLLB code: `zho_Hans`)
- Target: `ko` (NLLB code: `kor_Hang`)
- Direction: zh-CN → ko (unidirectional fine-tune)

## Usage

```python
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

repo = "{repo}"
tag  = "{tag}"   # pin to a specific published checkpoint

tokenizer = AutoTokenizer.from_pretrained(repo, revision=tag)
model     = AutoModelForSeq2SeqLM.from_pretrained(repo, revision=tag)

inputs = tokenizer("攻击力提升50%", return_tensors="pt",
                   src_lang="zho_Hans")
output_ids = model.generate(**inputs, forced_bos_token_id=tokenizer.lang_code_to_id["kor_Hang"],
                             num_beams=4, max_length=400)
print(tokenizer.decode(output_ids[0], skip_special_tokens=True))
```

Always pass `revision=<tag>` to pin to a specific published checkpoint (see §Published tag below).
No token is required to pull this public repository.

## Decoding defaults

See `generation_config.json`. Key parameters: `num_beams=4`, `max_length=400`.

## Provenance

- `corpus_sha256`: `{corpus_sha256}`
- `split_seed`: `{split_seed}`
- `best_composite_metric` (0.5·BLEU + 0.5·preservation_nospace): `{best_metric_str}`
- Full training metadata: `run_manifest.json` (included in this repo)

Training governed by ADR-0020, ADR-0031. Distribution governed by ADR-0037.

## Published tag

`{tag}`

---

*Non-commercial use only (CC-BY-NC-4.0). Attribution required.*
"""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        print(
            "[ERROR] HF_TOKEN environment variable is not set. "
            "Inject it from .env before running this script.",
            file=sys.stderr,
        )
        return 1

    checkpoint_dir = Path(args.checkpoint).resolve()
    if not checkpoint_dir.is_dir():
        print(f"[ERROR] Checkpoint directory not found: {checkpoint_dir}", file=sys.stderr)
        return 1

    manifest_path = (
        Path(args.run_manifest).resolve()
        if args.run_manifest
        else checkpoint_dir.parent / "run_manifest.json"
    )
    manifest = _load_manifest(manifest_path)

    missing = [p for p in INFERENCE_PATTERNS if not (checkpoint_dir / p).exists()]
    if missing:
        print(f"[ERROR] Missing required inference files in checkpoint: {missing}", file=sys.stderr)
        return 1

    model_card_content = _build_model_card(manifest, args.repo, args.tag)

    print("=" * 60)
    print("publish_model.py — ADR-0037")
    print("=" * 60)
    print(f"  checkpoint  : {checkpoint_dir}")
    print(f"  manifest    : {manifest_path}")
    print(f"  repo        : {args.repo}")
    print(f"  tag         : {args.tag}")
    print(f"  private     : {args.private}")
    print(f"  dry-run     : {args.dry_run}")
    print()
    print("Files to upload:")
    for p in INFERENCE_PATTERNS:
        size_mb = (checkpoint_dir / p).stat().st_size / (1024 ** 2)
        print(f"  {p:40s}  {size_mb:8.2f} MB  (from checkpoint)")
    print(f"  {'run_manifest.json':40s}  {'':>8}     (from manifest path)")
    print(f"  {'README.md':40s}  {'':>8}     (generated model card)")
    print()
    print(f"Tag to create: {args.tag}")
    print("=" * 60)

    if args.dry_run:
        print("[DRY-RUN] No files uploaded. Remove --dry-run to publish.")
        return 0

    from huggingface_hub import HfApi

    api = HfApi(token=token)

    print(f"\n[1/4] Ensuring repo '{args.repo}' exists (private={args.private}) …")
    api.create_repo(
        repo_id=args.repo,
        repo_type="model",
        private=args.private,
        exist_ok=True,
    )
    print("      OK")

    print(f"\n[2/4] Uploading inference files from {checkpoint_dir} …")
    commit_info = api.upload_folder(
        folder_path=str(checkpoint_dir),
        repo_id=args.repo,
        repo_type="model",
        allow_patterns=INFERENCE_PATTERNS,
        commit_message=f"publish checkpoint {args.tag} — inference files (ADR-0037)",
    )
    print(f"      commit sha: {commit_info.oid}")

    print(f"\n[3/4] Uploading run_manifest.json (provenance, ADR-0020) …")
    api.upload_file(
        path_or_fileobj=str(manifest_path),
        path_in_repo="run_manifest.json",
        repo_id=args.repo,
        repo_type="model",
        commit_message=f"publish run_manifest.json for {args.tag} (ADR-0037 provenance)",
    )
    print("      OK")

    print(f"\n[3b] Uploading README.md (model card) …")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(model_card_content)
        tmp_path = tmp.name
    try:
        api.upload_file(
            path_or_fileobj=tmp_path,
            path_in_repo="README.md",
            repo_id=args.repo,
            repo_type="model",
            commit_message=f"publish model card for {args.tag} (ADR-0037)",
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    print("      OK")

    print(f"\n[4/4] Creating tag '{args.tag}' …")
    try:
        api.create_tag(
            repo_id=args.repo,
            repo_type="model",
            tag=args.tag,
            tag_message=f"Release {args.tag} (ADR-0037)",
            exist_ok=True,
        )
        print("      OK")
    except Exception as exc:
        print(f"      [WARN] Tag creation failed (may already exist): {exc}")

    repo_url = f"https://huggingface.co/{args.repo}"
    print()
    print("=" * 60)
    print("Upload complete.")
    print(f"  repo URL    : {repo_url}")
    print(f"  commit sha  : {commit_info.oid}")
    print(f"  tag         : {args.tag}")
    print()
    print("Uploaded files:")
    for p in INFERENCE_PATTERNS:
        print(f"  {p}")
    print("  run_manifest.json")
    print("  README.md")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
