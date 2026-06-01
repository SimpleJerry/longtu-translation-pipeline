"""Clean the local Chinese-Korean game glossary in place.

The repository keeps only final training data, not raw customer/game source
files.  This pipeline uses the current data/glossary.csv as its authoritative
input, rewrites that glossary in place, and writes local audit CSVs for review.
Those audit files are reproducible run artifacts and are intentionally ignored
by Git.

Signals used by the cleaner:
- hard noise rules for placeholders, test-like rows, missing Korean, and UI
  fragments;
- a product-evidence relevance gate that removes terms unused by the current
  segment corpus;
- product-corpus evidence from data/segments.csv, which is read only and
  audited but is not a sufficient keep signal;
- jieba and Stanza for Chinese noun/phrase shape;
- kiwipiepy and Stanza for Korean noun/verb phrase shape;
- multilingual embeddings for Chinese/Korean semantic agreement;
- termhood signals that demote ordinary dictionary words unless they also
  carry game-domain evidence;
- compound-family suffix detection for residual item-name combinations.

Middle-confidence rows are kept in glossary.csv and recorded in the audit.
That bias is intentional: this is a game terminology table, and false
deletions are more costly than keeping a few uncertain terms for later review.
"""

from __future__ import annotations

import argparse
import csv
import os
from collections import OrderedDict
from pathlib import Path

from longtu_translation_pipeline.cleanup.common import (
    read_json_config,
    read_term_file,
    sha256,
)

from .classify import classify_rows, enforce_strict_pairs
from .config import (
    LEXICONS,
    PATTERNS,
    RULES,
    int_setting,
    lexicon,
    lexicon_list,
    load_pipeline_config,
    pattern,
    score_setting,
)
from .io import (
    LANGS,
    SCHEMA,
    batched,
    read_glossary_baseline,
    read_segment_evidence,
)
from .nlp import (
    KO_STANZA_PROCESSORS,
    ZH_STANZA_PROCESSORS,
    build_stanza_cache,
    load_embedding_model,
    load_stanza_pipelines,
    summarize_stanza_doc,
)
from .review import write_outputs
from .scoring import (
    ZIPF_CACHE,
    acronym_component_product_score,
    build_compound_families,
    common_noun_score,
    domain_specificity_score,
    encode_similarities_and_game_scores,
    game_term_score,
    general_word_score,
    has_cjk,
    has_game_anchor,
    has_hangul,
    is_proper_like,
    ko_noun_score,
    root_is_non_noun,
    safe_zipf_frequency,
    split_compound,
    zh_noun_score,
    zipf_frequency,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the local semantic glossary cleanup pipeline."
    )
    parser.add_argument(
        "--segments",
        default="data/segments.csv",
        help="Final segment corpus used only for read-only product evidence.",
    )
    parser.add_argument(
        "--glossary",
        default="data/glossary.csv",
        help="Final glossary CSV to rewrite.",
    )
    parser.add_argument(
        "--review-dir",
        default="data/review",
        help="Directory for semantic audit and review CSV outputs.",
    )
    parser.add_argument(
        "--config-dir",
        default="configs/glossary",
        help="Directory containing glossary cleanup rules and lexicons.",
    )
    parser.add_argument(
        "--hf-home",
        default="venv/hf_cache",
        help="Local Hugging Face cache directory. venv/ is gitignored.",
    )
    parser.add_argument(
        "--stanza-dir",
        default="venv/stanza_resources",
        help="Local Stanza model directory. venv/ is gitignored.",
    )
    parser.add_argument(
        "--embedding-model",
        default="BAAI/bge-m3",
        help="Primary multilingual embedding model.",
    )
    parser.add_argument(
        "--embedding-fallback",
        default="intfloat/multilingual-e5-base",
        help="Fallback embedding model if the primary model fails.",
    )
    parser.add_argument(
        "--game-seeds",
        default="configs/glossary/game_term_seeds.txt",
        help="Game-domain seed terms used to build the game embedding centroid.",
    )
    parser.add_argument(
        "--common-noun-seeds",
        default="configs/glossary/common_noun_seeds.txt",
        help="Ordinary-noun seed terms used to build the generic embedding centroid.",
    )
    parser.add_argument(
        "--expected-segments-sha256",
        default="",
        help="Optional safety hash for data/segments.csv. Empty disables the gate.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    segments_path = Path(args.segments)
    glossary_path = Path(args.glossary)
    review_dir = Path(args.review_dir)
    config_dir = Path(args.config_dir)
    hf_home = Path(args.hf_home)
    stanza_dir = Path(args.stanza_dir)
    game_seed_path = Path(args.game_seeds)
    common_noun_seed_path = Path(args.common_noun_seeds)
    review_dir.mkdir(parents=True, exist_ok=True)
    load_pipeline_config(config_dir)

    os.environ.setdefault("HF_HOME", str(hf_home.resolve()))
    os.environ.setdefault("STANZA_RESOURCES_DIR", str(stanza_dir.resolve()))

    segments_sha_before = sha256(segments_path)
    if args.expected_segments_sha256 and segments_sha_before != args.expected_segments_sha256.upper():
        raise RuntimeError(
            "Unexpected data/segments.csv hash before run: "
            f"{segments_sha_before}. Refusing to continue."
        )

    rows = read_glossary_baseline(glossary_path)
    segment_text = read_segment_evidence(segments_path)
    families = build_compound_families(rows)
    game_seed_terms = read_term_file(game_seed_path, "game seed")
    common_noun_seed_terms = read_term_file(
        common_noun_seed_path, "common noun"
    )

    zh_pipeline, ko_pipeline = load_stanza_pipelines(stanza_dir)
    zh_stanza = build_stanza_cache(
        zh_pipeline,
        [row["zh-CN"] for row in rows],
        batch_size=512,
        label="zh-CN",
    )
    ko_stanza = build_stanza_cache(
        ko_pipeline,
        [row["ko"] for row in rows],
        batch_size=512,
        label="ko",
    )

    # Free Stanza pipelines before loading BGE to reduce peak GPU memory.
    del zh_pipeline, ko_pipeline
    try:
        import torch

        torch.cuda.empty_cache()
    except Exception:
        pass

    from kiwipiepy import Kiwi

    embedding, embedding_model, embedding_device = load_embedding_model(
        args.embedding_model, args.embedding_fallback, hf_home
    )
    similarities, game_embedding_scores, generic_embedding_scores = (
        encode_similarities_and_game_scores(
            embedding,
            rows,
            game_seed_terms,
            common_noun_seed_terms,
        )
    )

    kiwi = Kiwi()
    classified = classify_rows(
        rows,
        segment_text=segment_text,
        families=families,
        zh_stanza=zh_stanza,
        ko_stanza=ko_stanza,
        kiwi=kiwi,
        similarities=similarities,
        game_embedding_scores=game_embedding_scores,
        generic_embedding_scores=generic_embedding_scores,
        embedding_model=embedding_model,
        embedding_device=embedding_device,
    )
    by_pair = enforce_strict_pairs(classified)

    import torch

    summary = OrderedDict(
        [
            ("input_glossary_rows", len(rows)),
            ("final_glossary_rows", 0),
            ("auto_remove_rows", 0),
            ("auto_split_compound_rows", 0),
            ("auto_keep_rows", 0),
            ("keep_uncertain_rows", 0),
            ("merged_duplicate_rows", 0),
            ("strict_conflict_removed_rows", 0),
            ("embedding_model", embedding_model),
            ("embedding_device", embedding_device),
            ("torch_cuda_available", torch.cuda.is_available()),
            ("torch_cuda_version", torch.version.cuda),
            ("stanza_status", "zh_ko_models_loaded"),
            ("stanza_processors", f"zh={ZH_STANZA_PROCESSORS};ko={KO_STANZA_PROCESSORS}"),
            ("wordfreq_status", "available" if zipf_frequency is not None else "unavailable"),
            ("config_dir", str(config_dir)),
            ("game_seed_file", str(game_seed_path)),
            ("game_seed_count", len(game_seed_terms)),
            ("common_noun_seed_file", str(common_noun_seed_path)),
            ("common_noun_seed_count", len(common_noun_seed_terms)),
            ("external_signal", "not_configured"),
            ("segments_sha256_before", segments_sha_before),
            ("segments_sha256_after", ""),
        ]
    )

    write_outputs(
        classified=classified,
        by_pair=by_pair,
        glossary_path=glossary_path,
        review_dir=review_dir,
        summary=summary,
    )

    segments_sha_after = sha256(segments_path)
    if segments_sha_after != segments_sha_before:
        raise RuntimeError(
            f"data/segments.csv changed unexpectedly: {segments_sha_before} -> {segments_sha_after}"
        )

    # Patch the after hash after write_outputs computed row counts.
    summary_path = review_dir / "glossary_semantic_cleanup_summary.csv"
    summary["segments_sha256_after"] = segments_sha_after
    with summary_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["metric", "value"])
        writer.writeheader()
        for key, value in summary.items():
            writer.writerow({"metric": key, "value": value})

    print("Glossary semantic pipeline completed.")
    for key, value in summary.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
