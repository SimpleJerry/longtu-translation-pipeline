"""Output writing for the glossary_semantic pipeline (ADR-0033 step 9b)."""

from __future__ import annotations

import csv
import locale
from collections import OrderedDict
from pathlib import Path
from typing import Any

from .config import score_setting
from .io import LANGS, SCHEMA


def write_outputs(
    *,
    classified: list[dict[str, Any]],
    by_pair: OrderedDict[tuple[str, str], dict[str, Any]],
    glossary_path: Path,
    review_dir: Path,
    summary: OrderedDict[str, Any],
) -> None:
    audit_fields = [
        "original_term_id",
        "action",
        "reasons",
        "term_score",
        "noun_score",
        "zh_noun_score",
        "ko_noun_score",
        "product_evidence_score",
        "compound_score",
        "bilingual_score",
        "general_word_score",
        "game_term_score",
        "common_noun_score",
        "domain_specificity_score",
        "game_embedding_score",
        "generic_embedding_score",
        "zh_zipf_frequency",
        "ko_zipf_frequency",
        "embedding_model",
        "embedding_device",
        "external_signal",
        "zh_segment_count",
        "ko_segment_count",
        "stem_zh-CN",
        "suffix_zh-CN",
        "family_size",
        "zh_pos",
        "ko_pos",
        *LANGS,
    ]
    with (review_dir / "glossary_semantic_audit.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(f, fieldnames=audit_fields)
        writer.writeheader()
        for item in classified:
            row = item["row"]
            out = {
                "original_term_id": row["original_term_id"],
                "action": item["action"],
                "reasons": ";".join(item["reasons"]),
                "term_score": f"{item['term_score']:.4f}",
                "noun_score": f"{item['noun_score']:.4f}",
                "zh_noun_score": f"{item['zh_noun_score']:.4f}",
                "ko_noun_score": f"{item['ko_noun_score']:.4f}",
                "product_evidence_score": f"{item['product_evidence_score']:.4f}",
                "compound_score": f"{item['compound_score']:.4f}",
                "bilingual_score": f"{item['bilingual_score']:.4f}",
                "general_word_score": f"{item['general_word_score']:.4f}",
                "game_term_score": f"{item['game_term_score']:.4f}",
                "common_noun_score": f"{item['common_noun_score']:.4f}",
                "domain_specificity_score": f"{item['domain_specificity_score']:.4f}",
                "game_embedding_score": f"{item['game_embedding_score']:.4f}",
                "generic_embedding_score": f"{item['generic_embedding_score']:.4f}",
                "zh_zipf_frequency": f"{item['zh_zipf_frequency']:.4f}",
                "ko_zipf_frequency": f"{item['ko_zipf_frequency']:.4f}",
                "embedding_model": item["embedding_model"],
                "embedding_device": item["embedding_device"],
                "external_signal": "not_configured",
                "zh_segment_count": item["zh_segment_count"],
                "ko_segment_count": item["ko_segment_count"],
                "stem_zh-CN": item["stem"],
                "suffix_zh-CN": item["suffix"],
                "family_size": item["family_size"],
                "zh_pos": item["zh_pos"],
                "ko_pos": item["ko_pos"],
            }
            for lang in LANGS:
                out[lang] = row.get(lang, "")
            writer.writerow(out)

    removed_items = [item for item in classified if item["action"] == "AUTO_REMOVE"]
    split_items = [
        item for item in classified if item["action"] == "AUTO_SPLIT_COMPOUND"
    ]
    uncertain_items = [
        item for item in classified if item["action"] == "KEEP_UNCERTAIN"
    ]
    common_review_items = [
        item
        for item in classified
        if item["action"] != "AUTO_REMOVE"
        and item["general_word_score"] >= score_setting("general_non_noun_short_score")
        and item["game_term_score"] < score_setting("common_review_game_max")
    ]
    common_noun_review_items = [
        item
        for item in classified
        if item["action"] != "AUTO_REMOVE"
        and item["common_noun_score"] >= score_setting("common_noun_review_min")
        and item["domain_specificity_score"] < score_setting("common_noun_review_domain_max")
    ]

    removed_fields = [
        "removed_id",
        "original_term_id",
        "action",
        "reasons",
        "term_score",
        "noun_score",
        "product_evidence_score",
        "bilingual_score",
        "general_word_score",
        "game_term_score",
        "common_noun_score",
        "domain_specificity_score",
        "game_embedding_score",
        "generic_embedding_score",
        "zh_zipf_frequency",
        "ko_zipf_frequency",
        "embedding_model",
        "zh_segment_count",
        "ko_segment_count",
        *LANGS,
    ]
    with (review_dir / "removed_glossary_semantic_cleanup.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(f, fieldnames=removed_fields)
        writer.writeheader()
        for idx, item in enumerate(removed_items, 1):
            row = item["row"]
            out = {
                "removed_id": idx,
                "original_term_id": row["original_term_id"],
                "action": item["action"],
                "reasons": ";".join(item["reasons"]),
                "term_score": f"{item['term_score']:.4f}",
                "noun_score": f"{item['noun_score']:.4f}",
                "product_evidence_score": f"{item['product_evidence_score']:.4f}",
                "bilingual_score": f"{item['bilingual_score']:.4f}",
                "general_word_score": f"{item['general_word_score']:.4f}",
                "game_term_score": f"{item['game_term_score']:.4f}",
                "common_noun_score": f"{item['common_noun_score']:.4f}",
                "domain_specificity_score": f"{item['domain_specificity_score']:.4f}",
                "game_embedding_score": f"{item['game_embedding_score']:.4f}",
                "generic_embedding_score": f"{item['generic_embedding_score']:.4f}",
                "zh_zipf_frequency": f"{item['zh_zipf_frequency']:.4f}",
                "ko_zipf_frequency": f"{item['ko_zipf_frequency']:.4f}",
                "embedding_model": item["embedding_model"],
                "zh_segment_count": item["zh_segment_count"],
                "ko_segment_count": item["ko_segment_count"],
            }
            for lang in LANGS:
                out[lang] = row.get(lang, "")
            writer.writerow(out)

    split_fields = [
        "split_id",
        "original_term_id",
        "action",
        "reasons",
        "stem_zh-CN",
        "suffix_zh-CN",
        "family_size",
        "suggested_components",
        "component_status",
        "bilingual_score",
        "embedding_model",
        *LANGS,
    ]
    with (review_dir / "split_glossary_compounds_semantic.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(f, fieldnames=split_fields)
        writer.writeheader()
        for idx, item in enumerate(split_items, 1):
            row = item["row"]
            components = ";".join(x for x in [item["stem"], item["suffix"]] if x)
            out = {
                "split_id": idx,
                "original_term_id": row["original_term_id"],
                "action": item["action"],
                "reasons": ";".join(item["reasons"]),
                "stem_zh-CN": item["stem"],
                "suffix_zh-CN": item["suffix"],
                "family_size": item["family_size"],
                "suggested_components": components,
                "component_status": "not_auto_added_without_stable_bilingual_component",
                "bilingual_score": f"{item['bilingual_score']:.4f}",
                "embedding_model": item["embedding_model"],
            }
            for lang in LANGS:
                out[lang] = row.get(lang, "")
            writer.writerow(out)

    uncertain_fields = [
        "review_id",
        "original_term_id",
        "action",
        "reasons",
        "term_score",
        "noun_score",
        "zh_noun_score",
        "ko_noun_score",
        "product_evidence_score",
        "bilingual_score",
        "general_word_score",
        "game_term_score",
        "common_noun_score",
        "domain_specificity_score",
        "game_embedding_score",
        "generic_embedding_score",
        "zh_zipf_frequency",
        "ko_zipf_frequency",
        "zh_segment_count",
        "ko_segment_count",
        "zh_pos",
        "ko_pos",
        *LANGS,
    ]
    with (review_dir / "glossary_keep_uncertain_review.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(f, fieldnames=uncertain_fields)
        writer.writeheader()
        for idx, item in enumerate(uncertain_items, 1):
            row = item["row"]
            out = {
                "review_id": idx,
                "original_term_id": row["original_term_id"],
                "action": item["action"],
                "reasons": ";".join(item["reasons"]),
                "term_score": f"{item['term_score']:.4f}",
                "noun_score": f"{item['noun_score']:.4f}",
                "zh_noun_score": f"{item['zh_noun_score']:.4f}",
                "ko_noun_score": f"{item['ko_noun_score']:.4f}",
                "product_evidence_score": f"{item['product_evidence_score']:.4f}",
                "bilingual_score": f"{item['bilingual_score']:.4f}",
                "general_word_score": f"{item['general_word_score']:.4f}",
                "game_term_score": f"{item['game_term_score']:.4f}",
                "common_noun_score": f"{item['common_noun_score']:.4f}",
                "domain_specificity_score": f"{item['domain_specificity_score']:.4f}",
                "game_embedding_score": f"{item['game_embedding_score']:.4f}",
                "generic_embedding_score": f"{item['generic_embedding_score']:.4f}",
                "zh_zipf_frequency": f"{item['zh_zipf_frequency']:.4f}",
                "ko_zipf_frequency": f"{item['ko_zipf_frequency']:.4f}",
                "zh_segment_count": item["zh_segment_count"],
                "ko_segment_count": item["ko_segment_count"],
                "zh_pos": item["zh_pos"],
                "ko_pos": item["ko_pos"],
            }
            for lang in LANGS:
                out[lang] = row.get(lang, "")
            writer.writerow(out)

    common_review_fields = [
        "review_id",
        "original_term_id",
        "action",
        "reasons",
        "term_score",
        "general_word_score",
        "game_term_score",
        "common_noun_score",
        "domain_specificity_score",
        "game_embedding_score",
        "generic_embedding_score",
        "zh_zipf_frequency",
        "ko_zipf_frequency",
        "noun_score",
        "product_evidence_score",
        "bilingual_score",
        "zh_segment_count",
        "ko_segment_count",
        "zh_pos",
        "ko_pos",
        *LANGS,
    ]
    with (review_dir / "glossary_common_word_review.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(f, fieldnames=common_review_fields)
        writer.writeheader()
        for idx, item in enumerate(common_review_items, 1):
            row = item["row"]
            out = {
                "review_id": idx,
                "original_term_id": row["original_term_id"],
                "action": item["action"],
                "reasons": ";".join(item["reasons"]),
                "term_score": f"{item['term_score']:.4f}",
                "general_word_score": f"{item['general_word_score']:.4f}",
                "game_term_score": f"{item['game_term_score']:.4f}",
                "common_noun_score": f"{item['common_noun_score']:.4f}",
                "domain_specificity_score": f"{item['domain_specificity_score']:.4f}",
                "game_embedding_score": f"{item['game_embedding_score']:.4f}",
                "generic_embedding_score": f"{item['generic_embedding_score']:.4f}",
                "zh_zipf_frequency": f"{item['zh_zipf_frequency']:.4f}",
                "ko_zipf_frequency": f"{item['ko_zipf_frequency']:.4f}",
                "noun_score": f"{item['noun_score']:.4f}",
                "product_evidence_score": f"{item['product_evidence_score']:.4f}",
                "bilingual_score": f"{item['bilingual_score']:.4f}",
                "zh_segment_count": item["zh_segment_count"],
                "ko_segment_count": item["ko_segment_count"],
                "zh_pos": item["zh_pos"],
                "ko_pos": item["ko_pos"],
            }
            for lang in LANGS:
                out[lang] = row.get(lang, "")
            writer.writerow(out)

    common_noun_review_fields = [
        "review_id",
        "original_term_id",
        "action",
        "reasons",
        "term_score",
        "common_noun_score",
        "domain_specificity_score",
        "general_word_score",
        "game_term_score",
        "generic_embedding_score",
        "game_embedding_score",
        "zh_zipf_frequency",
        "ko_zipf_frequency",
        "noun_score",
        "product_evidence_score",
        "bilingual_score",
        "zh_segment_count",
        "ko_segment_count",
        "zh_pos",
        "ko_pos",
        *LANGS,
    ]
    with (review_dir / "glossary_common_noun_review.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(f, fieldnames=common_noun_review_fields)
        writer.writeheader()
        for idx, item in enumerate(common_noun_review_items, 1):
            row = item["row"]
            out = {
                "review_id": idx,
                "original_term_id": row["original_term_id"],
                "action": item["action"],
                "reasons": ";".join(item["reasons"]),
                "term_score": f"{item['term_score']:.4f}",
                "common_noun_score": f"{item['common_noun_score']:.4f}",
                "domain_specificity_score": f"{item['domain_specificity_score']:.4f}",
                "general_word_score": f"{item['general_word_score']:.4f}",
                "game_term_score": f"{item['game_term_score']:.4f}",
                "generic_embedding_score": f"{item['generic_embedding_score']:.4f}",
                "game_embedding_score": f"{item['game_embedding_score']:.4f}",
                "zh_zipf_frequency": f"{item['zh_zipf_frequency']:.4f}",
                "ko_zipf_frequency": f"{item['ko_zipf_frequency']:.4f}",
                "noun_score": f"{item['noun_score']:.4f}",
                "product_evidence_score": f"{item['product_evidence_score']:.4f}",
                "bilingual_score": f"{item['bilingual_score']:.4f}",
                "zh_segment_count": item["zh_segment_count"],
                "ko_segment_count": item["ko_segment_count"],
                "zh_pos": item["zh_pos"],
                "ko_pos": item["ko_pos"],
            }
            for lang in LANGS:
                out[lang] = row.get(lang, "")
            writer.writerow(out)

    final_rows = []
    for item in by_pair.values():
        if item["action"] in {"AUTO_REMOVE", "AUTO_SPLIT_COMPOUND", "MERGED_DUPLICATE"}:
            continue
        final_rows.append(
            {
                "zh-CN": item["row"].get("zh-CN", ""),
                "ko": item["row"].get("ko", ""),
            }
        )

    try:
        locale.setlocale(locale.LC_COLLATE, "Chinese_China.936")
    except locale.Error:
        try:
            locale.setlocale(locale.LC_COLLATE, "zh_CN.UTF-8")
        except locale.Error:
            locale.setlocale(locale.LC_COLLATE, "")

    final_rows.sort(key=lambda row: locale.strxfrm(row["zh-CN"]))
    for idx, row in enumerate(final_rows, 1):
        row["term_id"] = str(idx)

    with glossary_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SCHEMA)
        writer.writeheader()
        writer.writerows(final_rows)

    summary["final_glossary_rows"] = len(final_rows)
    summary["auto_remove_rows"] = len(removed_items)
    summary["auto_split_compound_rows"] = len(split_items)
    summary["auto_keep_rows"] = sum(
        1 for item in classified if item["action"] == "AUTO_KEEP"
    )
    summary["keep_uncertain_rows"] = sum(
        1 for item in classified if item["action"] == "KEEP_UNCERTAIN"
    )
    summary["product_redundant_removed_rows"] = sum(
        1
        for item in removed_items
        if "not_in_segments_redundant_for_current_corpus" in item["reasons"]
    )
    summary["structural_noise_removed_rows"] = sum(
        1
        for item in removed_items
        if any(
            reason in item["reasons"]
            for reason in {
                "standalone_numeric_or_signed_token",
                "zh_column_has_no_chinese_content",
                "zh_column_contains_hangul",
                "ui_or_status_sentence_fragment",
            }
        )
    )
    summary["common_word_removed_rows"] = sum(
        1
        for item in removed_items
        if "common_word_without_game_term_signal" in item["reasons"]
    )
    summary["common_word_review_rows"] = len(common_review_items)
    summary["common_noun_removed_rows"] = sum(
        1
        for item in removed_items
        if "common_noun_without_domain_signal" in item["reasons"]
    )
    summary["common_noun_review_rows"] = len(common_noun_review_items)
    summary["merged_duplicate_rows"] = sum(
        1 for item in classified if item["action"] == "MERGED_DUPLICATE"
    )
    summary["strict_conflict_removed_rows"] = sum(
        1
        for item in removed_items
        if "strict_zh_ko_bidirectional_conflict" in item["reasons"]
    )

    with (review_dir / "glossary_semantic_cleanup_summary.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(f, fieldnames=["metric", "value"])
        writer.writeheader()
        for key, value in summary.items():
            writer.writerow({"metric": key, "value": value})
