"""RF-028: Coarse-to-fine inference parameter sweep.

Usage:
  python scripts/sweep_inference_params.py \\
      --run-dir <run_dir> [--model-path <ckpt>] \\
      --split {validation,test} \\
      --grid configs/inference/sweep_v1.json \\
      --output-dir data/review/inference/sweeps/v1 \\
      [--rows <N>] [--config <inference_config.json>]
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import itertools
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.config import GenerationConfig, load_inference_config
from longtu_translation_pipeline.evaluation import (
    GlossaryTerm,
    TranslationRow,
    compute_chrf,
    compute_corpus_bleu,
    compute_glossary_preservation,
    read_glossary_terms,
)
from longtu_translation_pipeline.inference import (
    configure_tokenizer_language_codes,
    prepare_inference_records,
    read_run_manifest,
    read_split_records,
    require_manifest_string,
    resolve_latest_run_checkpoint,
    resolve_manifest_path,
    run_generation_batches,
)
from longtu_translation_pipeline.training import (
    add_marker_special_tokens,
    resolve_training_device,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep inference parameters (RF-028)")
    parser.add_argument("--run-dir", required=True, help="Training run directory")
    parser.add_argument("--model-path", help="Checkpoint path (overrides auto-latest)")
    parser.add_argument("--split", default="validation", choices=["validation", "test"])
    parser.add_argument("--grid", required=True, help="JSON grid file")
    parser.add_argument("--output-dir", required=True, help="Output directory for sweep_results.csv")
    parser.add_argument("--rows", type=int, default=None, help="Row limit (e.g. 1000 for val_mini)")
    parser.add_argument(
        "--config",
        default=str(ROOT / "configs" / "inference" / "default.json"),
        help="Inference config JSON (default: configs/inference/default.json)",
    )
    return parser.parse_args()


def expand_grid(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    if not grid:
        return [{}]
    keys = list(grid.keys())
    values = [grid[k] for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def make_generation_config(base: GenerationConfig, params: dict[str, Any]) -> GenerationConfig:
    updates: dict[str, Any] = {}
    if "num_beams" in params:
        updates["num_beams"] = int(params["num_beams"])
    if "length_penalty" in params:
        updates["length_penalty"] = float(params["length_penalty"])
    if "no_repeat_ngram_size" in params:
        updates["no_repeat_ngram_size"] = int(params["no_repeat_ngram_size"])
    return dataclasses.replace(base, **updates)


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = load_inference_config(args.config, base_dir=ROOT)
    grid_data: dict[str, list[Any]] = json.loads(Path(args.grid).read_text(encoding="utf-8"))
    combinations = expand_grid(grid_data)
    print(f"Grid: {len(combinations)} combinations from {args.grid}", flush=True)

    if args.model_path:
        model_path = Path(args.model_path)
    else:
        model_path = resolve_latest_run_checkpoint(run_dir)
    print(f"Model: {model_path}", flush=True)

    manifest_path = run_dir / "run_manifest.json"
    manifest = read_run_manifest(manifest_path)
    raw_split_path = require_manifest_string(
        manifest, ["data", f"{args.split}_split_path"], manifest_path
    )
    split_path = resolve_manifest_path(raw_split_path, run_dir=run_dir, repo_root=ROOT)
    records = read_split_records(split_path, args.split)
    if args.rows is not None:
        records = records[: args.rows]
    print(f"Split: {split_path} ({len(records)} rows)", flush=True)

    terms = read_glossary_terms(config.glossary.path, "zh-CN", "ko")
    print(f"Glossary: {len(terms)} terms", flush=True)

    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(config.model.tokenizer_name)
    configure_tokenizer_language_codes(tokenizer, config)
    add_marker_special_tokens(tokenizer)
    forced_bos_token_id = int(tokenizer.convert_tokens_to_ids(config.language.target_code))
    if forced_bos_token_id < 0:
        raise ValueError(f"Target language code not found in tokenizer: {config.language.target_code}")

    device = resolve_training_device("auto")
    model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
    if len(tokenizer) != model.get_input_embeddings().num_embeddings:
        model.resize_token_embeddings(len(tokenizer))
    if device == "cuda":
        model = model.to("cuda")
    model.eval()
    print(f"Model loaded on {device}", flush=True)

    prepared = prepare_inference_records(config, records)

    results_path = output_dir / "sweep_results.csv"
    fieldnames = [
        "num_beams", "length_penalty", "no_repeat_ngram_size",
        "bleu", "chrf", "preservation_nospace", "preservation_exact", "empty_candidate_rows",
    ]

    rows_written = 0
    with results_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i, params in enumerate(combinations, start=1):
            print(f"[{i}/{len(combinations)}] {params}", end=" ... ", flush=True)
            new_gen = make_generation_config(config.generation, params)
            sweep_config = dataclasses.replace(config, generation=new_gen)

            gen_rows = run_generation_batches(sweep_config, tokenizer, model, prepared, forced_bos_token_id)

            eval_rows = [
                TranslationRow(
                    row_number=j + 1,
                    segment_id=gr.record_id,
                    source=gr.source,
                    reference=gr.reference,
                    candidate=gr.candidate,
                )
                for j, gr in enumerate(gen_rows)
            ]

            references = [r.reference for r in eval_rows]
            candidates = [r.candidate for r in eval_rows]
            empty = sum(1 for c in candidates if not c.strip())

            bleu = compute_corpus_bleu(
                references, candidates,
                tokenization="whitespace", max_order=4, smooth_value=0.1,
            )
            chrf = compute_chrf(references, candidates, max_n=6, beta=2.0)
            pres = compute_glossary_preservation(eval_rows, terms)

            row = {
                "num_beams": new_gen.num_beams,
                "length_penalty": new_gen.length_penalty,
                "no_repeat_ngram_size": new_gen.no_repeat_ngram_size,
                "bleu": f"{bleu.score:.6f}",
                "chrf": f"{chrf.score:.6f}",
                "preservation_nospace": f"{pres.preservation_rate_nospace:.6f}",
                "preservation_exact": f"{pres.preservation_rate_exact:.6f}",
                "empty_candidate_rows": empty,
            }
            writer.writerow(row)
            f.flush()
            rows_written += 1
            print(
                f"BLEU={bleu.score:.4f}  chrF={chrf.score:.4f}"
                f"  pres_nospace={pres.preservation_rate_nospace:.4f}",
                flush=True,
            )

    print(f"\nSweep complete: {rows_written} combinations → {results_path}", flush=True)


if __name__ == "__main__":
    main()
