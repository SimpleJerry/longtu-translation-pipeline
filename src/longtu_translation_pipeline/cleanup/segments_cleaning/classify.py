"""Classification and semantic scoring orchestration for segments_cleaning (ADR-0033 step 8b)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .io import require_setting
from .nlp import build_stanza_cache, load_embedding_model, load_stanza_pipelines
from .normalize import (
    has_meaningful_text,
    is_non_segment_single_cjk_fragment,
    normalize_row,
    parse_tuple_like,
    placeholder_set,
    target_language_contamination_reason,
)
from .scoring import encode_semantic_scores, ko_noun_score, sentence_like_score, zh_noun_score


def base_audit_item(
    *,
    row: dict[str, str],
    split_index: int,
    zh: str,
    ko: str,
) -> dict[str, str]:
    return {
        "original_segment_id": row["segment_id"],
        "split_index": str(split_index),
        "action": "KEEP",
        "reason": "kept",
        "semantic_action": "NOT_EVALUATED",
        "semantic_term_score": "",
        "noun_score": "",
        "zh_noun_score": "",
        "ko_noun_score": "",
        "glossary_similarity": "",
        "term_seed_similarity": "",
        "sentence_like_score": "",
        "embedding_model": "",
        "embedding_device": "",
        "zh_pos": "",
        "ko_pos": "",
        "zh-CN": zh.strip(),
        "ko": ko.strip(),
    }


def initial_classify(
    item: dict[str, str],
    *,
    glossary_pairs: set[tuple[str, str]],
    patterns: dict[str, re.Pattern[str]],
    thresholds: dict[str, float],
    sentence_markers: list[str],
) -> None:
    zh = item["zh-CN"]
    ko = item["ko"]
    if not zh or not ko:
        item["action"] = "REMOVE_EMPTY"
        item["reason"] = "empty_after_split"
        item["semantic_action"] = "SKIP_EMPTY"
        return

    contamination_reason = target_language_contamination_reason(ko)
    if contamination_reason:
        item["action"] = "REMOVE_TARGET_LANGUAGE_CONTAMINATION"
        item["reason"] = contamination_reason
        item["semantic_action"] = "AUTO_REMOVE_TARGET_LANGUAGE_CONTAMINATION"
        return

    if is_non_segment_single_cjk_fragment(zh, ko, patterns=patterns):
        item["action"] = "REMOVE_NON_SEGMENT_FRAGMENT"
        item["reason"] = "pure_cjk_single_char_fragment"
        item["semantic_action"] = "AUTO_REMOVE_NON_SEGMENT_FRAGMENT"
        return

    if patterns["machine_placeholder"].search(zh + ko):
        item["reason"] = "placeholder_kept"
        item["semantic_action"] = "SKIP_PLACEHOLDER"
        item["sentence_like_score"] = "1.0000"
        return

    if (zh, ko) in glossary_pairs:
        item["action"] = "REMOVE_TERM_LIKE"
        item["reason"] = "exact_glossary_pair"
        item["semantic_action"] = "AUTO_REMOVE_EXACT_GLOSSARY"
        item["semantic_term_score"] = "1.0000"
        item["glossary_similarity"] = "1.0000"
        return

    score = sentence_like_score(
        zh,
        ko,
        patterns=patterns,
        sentence_markers=sentence_markers,
    )
    item["sentence_like_score"] = f"{score:.4f}"
    if score >= require_setting(thresholds, "sentence_like_keep_threshold"):
        item["reason"] = "sentence_like_kept"
        item["semantic_action"] = "SKIP_SENTENCE_LIKE"
        return

    if patterns["tuple_wrapper"].match(zh) or patterns["tuple_wrapper"].match(ko):
        item["reason"] = "structured_wrapper_kept_for_review"
        item["semantic_action"] = "SKIP_STRUCTURE_WRAPPER"
        return

    item["semantic_action"] = "PENDING_SEMANTIC"


def collect_initial_items(
    rows: list[dict[str, str]],
    *,
    glossary_pairs: set[tuple[str, str]],
    patterns: dict[str, re.Pattern[str]],
    thresholds: dict[str, float],
    sentence_markers: list[str],
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    audit: list[dict[str, str]] = []
    split_review_sources: list[dict[str, str]] = []
    placeholder_review: list[dict[str, str]] = []
    normalized_markup: list[dict[str, str]] = []
    normalized_wrappers: list[dict[str, str]] = []
    markup_mismatch_review: list[dict[str, str]] = []
    removed_markup_only: list[dict[str, str]] = []

    for row in rows:
        original_row = row
        row = normalize_row(
            row,
            patterns=patterns,
            normalized_markup=normalized_markup,
            normalized_wrappers=normalized_wrappers,
            markup_mismatch_review=markup_mismatch_review,
        )
        zh = row["zh-CN"]
        ko = row["ko"]
        if not has_meaningful_text(zh + ko):
            item = base_audit_item(row=row, split_index=0, zh=zh, ko=ko)
            item["action"] = "REMOVE_MARKUP_ONLY"
            item["reason"] = "markup_only_after_normalization"
            item["semantic_action"] = "SKIP_MARKUP_ONLY"
            audit.append(item)
            removed_markup_only.append(
                {
                    "original_segment_id": original_row["segment_id"],
                    "original_zh-CN": original_row["zh-CN"],
                    "original_ko": original_row["ko"],
                    "normalized_zh-CN": zh,
                    "normalized_ko": ko,
                }
            )
            continue
        zh_placeholders = placeholder_set(zh, patterns)
        ko_placeholders = placeholder_set(ko, patterns)
        if zh_placeholders != ko_placeholders:
            placeholder_review.append(
                {
                    "original_segment_id": row["segment_id"],
                    "zh_placeholders": zh_placeholders,
                    "ko_placeholders": ko_placeholders,
                    "zh-CN": zh,
                    "ko": ko,
                }
            )

        zh_items = parse_tuple_like(zh, patterns)
        ko_items = parse_tuple_like(ko, patterns)
        if zh_items is not None or ko_items is not None:
            if zh_items is None or ko_items is None or len(zh_items) != len(ko_items):
                item = base_audit_item(row=row, split_index=0, zh=zh, ko=ko)
                item["action"] = "REMOVE_STRUCTURED_UNPARSED"
                item["reason"] = "tuple_parse_or_alignment_failed"
                item["semantic_action"] = "SKIP_STRUCTURED_UNPARSED"
                audit.append(item)
                continue

            for split_index, (child_zh, child_ko) in enumerate(zip(zh_items, ko_items), 1):
                item = base_audit_item(
                    row=row,
                    split_index=split_index,
                    zh=child_zh,
                    ko=child_ko,
                )
                initial_classify(
                    item,
                    glossary_pairs=glossary_pairs,
                    patterns=patterns,
                    thresholds=thresholds,
                    sentence_markers=sentence_markers,
                )
                item["source_zh-CN"] = zh
                item["source_ko"] = ko
                split_review_sources.append(item)
                audit.append(item)
            continue

        item = base_audit_item(row=row, split_index=0, zh=zh, ko=ko)
        initial_classify(
            item,
            glossary_pairs=glossary_pairs,
            patterns=patterns,
            thresholds=thresholds,
            sentence_markers=sentence_markers,
        )
        audit.append(item)

    return (
        audit,
        split_review_sources,
        placeholder_review,
        normalized_markup,
        normalized_wrappers,
        markup_mismatch_review,
        removed_markup_only,
    )


def score_semantic_candidates(
    semantic_items: list[dict[str, str]],
    *,
    glossary_terms: list[str],
    seed_terms: list[str],
    patterns: dict[str, re.Pattern[str]],
    thresholds: dict[str, float],
    weights: dict[str, float],
    hf_home: Path,
    stanza_dir: Path,
    embedding_model: str,
    embedding_fallback: str,
) -> tuple[str, str, str]:
    if not semantic_items:
        return "", "", ""

    os.environ.setdefault("HF_HOME", str(hf_home.resolve()))
    os.environ.setdefault("STANZA_RESOURCES_DIR", str(stanza_dir.resolve()))

    zh_pipeline, ko_pipeline = load_stanza_pipelines(stanza_dir)
    zh_stanza = build_stanza_cache(
        zh_pipeline,
        [item["zh-CN"] for item in semantic_items],
        batch_size=512,
        label="segment zh-CN",
    )
    ko_stanza = build_stanza_cache(
        ko_pipeline,
        [item["ko"] for item in semantic_items],
        batch_size=512,
        label="segment ko",
    )
    del zh_pipeline, ko_pipeline

    try:
        import torch

        torch.cuda.empty_cache()
    except Exception:
        pass

    from kiwipiepy import Kiwi

    model, actual_model, device = load_embedding_model(
        embedding_model, embedding_fallback, hf_home
    )
    glossary_scores, seed_scores, similarity_method = encode_semantic_scores(
        model=model,
        items=semantic_items,
        glossary_terms=glossary_terms,
        seed_terms=seed_terms,
    )

    kiwi = Kiwi()
    remove_threshold = require_setting(thresholds, "semantic_term_remove_threshold")
    review_threshold = require_setting(thresholds, "semantic_term_review_threshold")
    noun_min = require_setting(thresholds, "noun_score_min")
    glossary_threshold = require_setting(thresholds, "glossary_similarity_threshold")
    seed_threshold = require_setting(thresholds, "term_seed_similarity_threshold")

    for idx, item in enumerate(semantic_items):
        zh_info = zh_stanza.get(item["zh-CN"], {})
        ko_info = ko_stanza.get(item["ko"], {})
        zh_score, zh_pos = zh_noun_score(item["zh-CN"], zh_info)
        ko_score, ko_pos = ko_noun_score(item["ko"], kiwi, ko_info)
        noun_score = min(zh_score, ko_score)
        glossary_score = float(glossary_scores[idx])
        seed_score = float(seed_scores[idx])
        sentence_score = float(item["sentence_like_score"] or "0")
        semantic_score = (
            require_setting(weights, "noun_score") * noun_score
            + require_setting(weights, "glossary_similarity") * glossary_score
            + require_setting(weights, "term_seed_similarity") * seed_score
            - require_setting(weights, "sentence_like_penalty") * sentence_score
        )
        semantic_score = max(0.0, min(1.0, semantic_score))

        item["zh_noun_score"] = f"{zh_score:.4f}"
        item["ko_noun_score"] = f"{ko_score:.4f}"
        item["noun_score"] = f"{noun_score:.4f}"
        item["zh_pos"] = zh_pos
        item["ko_pos"] = ko_pos
        item["glossary_similarity"] = f"{glossary_score:.4f}"
        item["term_seed_similarity"] = f"{seed_score:.4f}"
        item["semantic_term_score"] = f"{semantic_score:.4f}"
        item["embedding_model"] = actual_model
        item["embedding_device"] = device

        has_term_neighborhood = (
            glossary_score >= glossary_threshold or seed_score >= seed_threshold
        )
        if (
            semantic_score >= remove_threshold
            and noun_score >= noun_min
            and has_term_neighborhood
        ):
            item["action"] = "REMOVE_TERM_LIKE"
            item["reason"] = "semantic_term_entity_like"
            item["semantic_action"] = "AUTO_REMOVE_SEMANTIC_TERM_ENTITY"
        elif semantic_score >= review_threshold and noun_score >= noun_min:
            item["reason"] = "semantic_term_entity_review"
            item["semantic_action"] = "REVIEW_SEMANTIC_TERM_ENTITY"
        else:
            item["semantic_action"] = "KEEP_SEMANTIC_SEGMENT"

    return actual_model, device, similarity_method
