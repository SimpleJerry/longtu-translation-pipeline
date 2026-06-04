"""Select the best fine-tuned checkpoint via full-validation-set reranking.

Contract: ADR-0041 — scripted checkpoint selection is required for all formal
runs; selection uses the composite metric (0.5·BLEU + 0.5·preservation_nospace)
evaluated on the FULL validation split (not the 1k in-loop subset).

Usage (dry-run, no GPU needed):
    python scripts/select_checkpoint.py --run-dir <run-dir> --dry-run

Usage (real selection, requires GPU + checkpoints locally):
    python scripts/select_checkpoint.py --run-dir <run-dir>
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Select the best checkpoint by full-validation-set reranking (ADR-0041). "
            "Writes checkpoint_selection_manifest.json to --run-dir."
        )
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        help="Training run directory containing run_manifest.json and checkpoint-N/ subdirs.",
    )
    parser.add_argument(
        "--inference-config",
        default=str(ROOT / "configs" / "inference" / "default.json"),
        help="Inference config JSON. Default: configs/inference/default.json.",
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="Device for model inference (auto/cpu/cuda). Default: auto.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List discovered checkpoints and exit without running inference.",
    )
    return parser.parse_args()


def _composite_metric(bleu: float, preservation_nospace: float) -> float:
    """Composite metric = 0.5·BLEU + 0.5·preservation_nospace (ADR-0031/ADR-0041)."""
    return 0.5 * bleu + 0.5 * preservation_nospace


def _find_checkpoints(run_dir: Path) -> list[Path]:
    from longtu_translation_pipeline.model_runtime import list_checkpoint_paths
    return list_checkpoint_paths(run_dir)


def _score_checkpoint(
    checkpoint: Path,
    run_dir: Path,
    inference_config_path: Path,
    output_dir: Path,
    device: str,
) -> dict:
    """Run inference on the full validation split and return metric scores."""
    from longtu_translation_pipeline.config import load_inference_config
    from longtu_translation_pipeline.inference import (
        generate_run_split_translations,
        read_run_manifest,
    )
    from longtu_translation_pipeline.evaluation import (
        compute_corpus_bleu,
        compute_glossary_preservation,
        read_glossary_terms,
        read_translation_rows,
    )

    config = load_inference_config(inference_config_path, base_dir=ROOT)
    manifest = read_run_manifest(run_dir / "run_manifest.json")
    glossary_path = ROOT / "data" / "glossary.csv"
    generation_out = output_dir / f"validation_{checkpoint.name}.csv"

    generation, *_ = generate_run_split_translations(
        config,
        run_dir=run_dir,
        split_name="validation",
        model_path=checkpoint,
        output_path=generation_out,
        device=device,
        repo_root=ROOT,
    )

    rows = read_translation_rows(generation_out, "source", "references", "candidates")
    terms = read_glossary_terms(glossary_path, "zh-CN", "ko")
    references = [r.reference for r in rows]
    candidates = [r.candidate for r in rows]

    bleu_result = compute_corpus_bleu(references, candidates)
    glossary_result = compute_glossary_preservation(rows, terms)
    bleu = bleu_result.score
    preservation_nospace = glossary_result.preservation_rate_nospace
    composite = _composite_metric(bleu, preservation_nospace)

    return {
        "checkpoint": str(checkpoint),
        "validation_rows": len(rows),
        "bleu": round(bleu, 6),
        "preservation_nospace": round(preservation_nospace, 6),
        "composite": round(composite, 6),
    }


def _write_manifest(
    run_dir: Path,
    scores: list[dict],
    winner: dict,
) -> Path:
    manifest = {
        "selected_checkpoint": winner["checkpoint"],
        "composite_metric_formula": "0.5 * bleu + 0.5 * preservation_nospace",
        "selected_scores": {
            "bleu": winner["bleu"],
            "preservation_nospace": winner["preservation_nospace"],
            "composite": winner["composite"],
        },
        "all_checkpoints": scores,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "adr": "ADR-0041",
    }
    path = run_dir / "checkpoint_selection_manifest.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    run_dir = Path(args.run_dir).resolve()
    inference_config_path = Path(args.inference_config).resolve()

    if not run_dir.is_dir():
        print(f"[ERROR] run-dir does not exist: {run_dir}", file=sys.stderr)
        return 1
    if not (run_dir / "run_manifest.json").exists():
        print(f"[ERROR] run_manifest.json not found in: {run_dir}", file=sys.stderr)
        return 1
    if not inference_config_path.exists():
        print(f"[ERROR] inference config not found: {inference_config_path}", file=sys.stderr)
        return 1

    checkpoints = _find_checkpoints(run_dir)

    print("=" * 60)
    print("select_checkpoint.py — ADR-0041")
    print("=" * 60)
    print(f"  run-dir          : {run_dir}")
    print(f"  inference-config : {inference_config_path}")
    print(f"  device           : {args.device}")
    print(f"  checkpoints found: {len(checkpoints)}")
    for ckpt in checkpoints:
        print(f"    {ckpt.name}")
    print()

    if not checkpoints:
        print("[ERROR] No checkpoint-N directories found in run-dir.", file=sys.stderr)
        return 1

    if args.dry_run:
        print("[DRY-RUN] Checkpoint discovery complete. Remove --dry-run to run selection.")
        return 0

    scores: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for i, ckpt in enumerate(checkpoints, 1):
            print(f"[{i}/{len(checkpoints)}] Scoring {ckpt.name} …")
            score = _score_checkpoint(ckpt, run_dir, inference_config_path, tmp_path, args.device)
            scores.append(score)
            print(
                f"      BLEU={score['bleu']:.4f}  "
                f"preservation_nospace={score['preservation_nospace']:.4f}  "
                f"composite={score['composite']:.4f}"
            )

    scores.sort(key=lambda s: s["composite"], reverse=True)
    winner = scores[0]

    print()
    print("=" * 60)
    print(f"Winner: {winner['checkpoint']}")
    print(f"  composite = {winner['composite']:.4f}  "
          f"(BLEU={winner['bleu']:.4f}, preservation_nospace={winner['preservation_nospace']:.4f})")
    print("=" * 60)

    manifest_path = _write_manifest(run_dir, scores, winner)
    print(f"\n[OK] Manifest written: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
