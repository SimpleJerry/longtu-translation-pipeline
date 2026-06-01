"""Review-first semantic cleanup for Chinese-Korean segment training data.

Segments are seq2seq training examples, not glossary terms.  This pipeline
therefore removes high-confidence non-segment fragments, target-language
contamination, term/entity-like rows, and exact glossary pairs, while keeping
sentence-like UI text and placeholder-bearing strings for training unless the
target side is clearly contaminated.  It defaults to dry-run and writes local
review CSVs under data/review/segments/, which is ignored by Git.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
from pathlib import Path

from longtu_translation_pipeline.cleanup.common import (
    compile_regexes,
    read_json_config,
    read_term_file,
    sha256,
)

from .classify import (
    base_audit_item,
    collect_initial_items,
    initial_classify,
    score_semantic_candidates,
)
from .io import (
    AUDIT_FIELDS,
    GLOSSARY_SCHEMA,
    SEGMENT_SCHEMA,
    read_glossary,
    read_rows,
    read_thresholds,
    read_weights,
    require_setting,
    write_csv,
    write_review_outputs,
    write_segments,
)
from .nlp import (
    KO_STANZA_PROCESSORS,
    ZH_STANZA_PROCESSORS,
    batched,
    build_stanza_cache,
    load_embedding_model,
    load_stanza_pipelines,
    summarize_stanza_doc,
)
from .normalize import (
    has_cjk,
    has_hangul,
    has_meaningful_text,
    is_non_segment_single_cjk_fragment,
    normalize_row,
    parse_tuple_like,
    placeholder_set,
    pure_cjk_len,
    strip_presentation_tags,
    target_language_contamination_reason,
    unknown_angle_tags,
    wrapper_match,
)
from .scoring import (
    encode_semantic_scores,
    ko_noun_score,
    sentence_like_score,
    zh_noun_score,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean segment data with local semantic review-first outputs."
    )
    parser.add_argument("--segments", default="data/segments.csv")
    parser.add_argument("--glossary", default="data/glossary.csv")
    parser.add_argument("--config", default="configs/segments/rules.json")
    parser.add_argument("--term-seeds", default="configs/segments/term_entity_seeds.txt")
    parser.add_argument(
        "--sentence-keep-markers",
        default="configs/segments/sentence_keep_markers.txt",
    )
    parser.add_argument("--review-dir", default="data/review/segments")
    parser.add_argument("--hf-home", default="venv/hf_cache")
    parser.add_argument("--stanza-dir", default="venv/stanza_resources")
    parser.add_argument("--embedding-model", default="BAAI/bge-m3")
    parser.add_argument("--embedding-fallback", default="intfloat/multilingual-e5-base")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Generate review only.")
    mode.add_argument("--apply", action="store_true", help="Rewrite segments.csv.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    segments_path = Path(args.segments)
    glossary_path = Path(args.glossary)
    review_dir = Path(args.review_dir)
    rules = read_json_config(Path(args.config))
    patterns = compile_regexes(rules)
    thresholds = read_thresholds(rules)
    weights = read_weights(rules)
    term_seed_terms = read_term_file(Path(args.term_seeds), "segment term/entity seed")
    sentence_markers = read_term_file(
        Path(args.sentence_keep_markers), "segment sentence keep marker"
    )

    segments_sha_before = sha256(segments_path)
    rows = read_rows(segments_path, SEGMENT_SCHEMA)
    glossary_pairs, glossary_terms = read_glossary(glossary_path)
    (
        audit,
        split_review,
        placeholder_review,
        normalized_markup,
        normalized_wrappers,
        markup_mismatch_review,
        removed_markup_only,
    ) = collect_initial_items(
        rows,
        glossary_pairs=glossary_pairs,
        patterns=patterns,
        thresholds=thresholds,
        sentence_markers=sentence_markers,
    )

    semantic_items = [
        row for row in audit if row["semantic_action"] == "PENDING_SEMANTIC"
    ]
    embedding_model, embedding_device, similarity_method = score_semantic_candidates(
        semantic_items,
        glossary_terms=glossary_terms,
        seed_terms=term_seed_terms,
        patterns=patterns,
        thresholds=thresholds,
        weights=weights,
        hf_home=Path(args.hf_home),
        stanza_dir=Path(args.stanza_dir),
        embedding_model=args.embedding_model,
        embedding_fallback=args.embedding_fallback,
    )

    kept_rows = [row for row in audit if row["action"] == "KEEP"]
    summary: OrderedDict[str, str] = OrderedDict(
        [
            ("mode", "apply" if args.apply else "dry-run"),
            ("input_rows", str(len(rows))),
            ("audit_rows_after_split", str(len(audit))),
            ("kept_rows", str(len(kept_rows))),
            (
                "removed_term_like_rows",
                str(sum(1 for row in audit if row["action"] == "REMOVE_TERM_LIKE")),
            ),
            (
                "removed_exact_glossary_rows",
                str(sum(1 for row in audit if row["reason"] == "exact_glossary_pair")),
            ),
            (
                "removed_semantic_term_entity_rows",
                str(
                    sum(
                        1
                        for row in audit
                        if row["reason"] == "semantic_term_entity_like"
                    )
                ),
            ),
            (
                "semantic_term_review_rows",
                str(
                    sum(
                        1
                        for row in audit
                        if row["semantic_action"] == "REVIEW_SEMANTIC_TERM_ENTITY"
                    )
                ),
            ),
            (
                "removed_structured_unparsed_rows",
                str(
                    sum(
                        1
                        for row in audit
                        if row["action"] == "REMOVE_STRUCTURED_UNPARSED"
                    )
                ),
            ),
            (
                "removed_empty_rows",
                str(sum(1 for row in audit if row["action"] == "REMOVE_EMPTY")),
            ),
            (
                "removed_non_segment_fragment_rows",
                str(
                    sum(
                        1
                        for row in audit
                        if row["action"] == "REMOVE_NON_SEGMENT_FRAGMENT"
                    )
                ),
            ),
            (
                "removed_target_language_contamination_rows",
                str(
                    sum(
                        1
                        for row in audit
                        if row["action"] == "REMOVE_TARGET_LANGUAGE_CONTAMINATION"
                    )
                ),
            ),
            (
                "removed_markup_only_rows",
                str(sum(1 for row in audit if row["action"] == "REMOVE_MARKUP_ONLY")),
            ),
            ("normalized_markup_rows", str(len(normalized_markup))),
            ("normalized_wrapper_rows", str(len(normalized_wrappers))),
            ("markup_mismatch_review_rows", str(len(markup_mismatch_review))),
            ("structured_split_child_rows", str(len(split_review))),
            ("placeholder_review_rows", str(len(placeholder_review))),
            ("semantic_candidate_rows", str(len(semantic_items))),
            ("embedding_model", embedding_model),
            ("embedding_device", embedding_device),
            ("similarity_method", similarity_method),
            ("stanza_status", "zh_ko_models_loaded" if semantic_items else "not_needed"),
            ("stanza_processors", f"zh={ZH_STANZA_PROCESSORS};ko={KO_STANZA_PROCESSORS}"),
            ("term_seed_count", str(len(term_seed_terms))),
            ("sentence_keep_marker_count", str(len(sentence_markers))),
            ("segments_sha256_before", segments_sha_before),
            ("segments_sha256_after", ""),
        ]
    )

    if args.apply:
        write_segments(segments_path, kept_rows)

    segments_sha_after = sha256(segments_path)
    summary["segments_sha256_after"] = segments_sha_after
    write_review_outputs(
        review_dir,
        audit=audit,
        split_review=split_review,
        placeholder_review=placeholder_review,
        normalized_markup=normalized_markup,
        normalized_wrappers=normalized_wrappers,
        markup_mismatch_review=markup_mismatch_review,
        removed_markup_only=removed_markup_only,
        summary=summary,
    )

    if not args.apply and segments_sha_after != segments_sha_before:
        raise RuntimeError("Dry run unexpectedly modified data/segments.csv.")

    print("Segments semantic cleaning pipeline completed.")
    for key, value in summary.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
