"""Glossary row classification for glossary_semantic (ADR-0033 step 9b)."""

from __future__ import annotations

from collections import OrderedDict, defaultdict
from typing import Any

from .config import int_setting, lexicon, lexicon_list, pattern, score_setting
from .io import LANGS
from .scoring import (
    acronym_component_product_score,
    common_noun_score,
    domain_specificity_score,
    game_term_score,
    general_word_score,
    has_cjk,
    has_game_anchor,
    has_hangul,
    ko_noun_score,
    safe_zipf_frequency,
    split_compound,
    zh_noun_score,
)


def classify_rows(
    rows: list[dict[str, str]],
    *,
    segment_text: dict[str, str],
    families: dict[str, set[str]],
    zh_stanza: dict[str, dict[str, Any]],
    ko_stanza: dict[str, dict[str, Any]],
    kiwi: Any,
    similarities: Any,
    game_embedding_scores: Any,
    generic_embedding_scores: Any,
    embedding_model: str,
    embedding_device: str,
) -> list[dict[str, Any]]:
    classified: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        zh = row["zh-CN"]
        ko = row["ko"]
        zh_count = segment_text["zh-CN"].count(zh) if zh and len(zh) >= 2 else 0
        ko_count = segment_text["ko"].count(ko) if ko and len(ko) >= 2 else 0
        product_score = (
            score_setting("product_both_score")
            if zh_count and ko_count
            else (score_setting("product_one_side_score") if zh_count or ko_count else 0.0)
        )
        product_score = max(
            product_score, acronym_component_product_score(zh, ko, segment_text)
        )
        no_product_evidence = product_score == 0.0

        zh_score, zh_pos = zh_noun_score(zh, zh_stanza.get(zh, {}))
        ko_score, ko_pos = ko_noun_score(ko, kiwi, ko_stanza.get(ko, {}))
        noun_score = (zh_score + ko_score) / 2
        bilingual_score = 0.0 if not ko else float(similarities[idx])
        game_embedding_score = float(game_embedding_scores[idx])
        generic_embedding_score = float(generic_embedding_scores[idx])
        zh_zipf = safe_zipf_frequency(zh, "zh")
        ko_zipf = safe_zipf_frequency(ko, "ko")
        general_score = general_word_score(zh, ko, zh_pos)
        game_score = game_term_score(zh, ko, game_embedding_score)
        common_noun = common_noun_score(
            zh,
            ko,
            zh_score,
            ko_score,
            zh_zipf,
            ko_zipf,
            generic_embedding_score,
        )
        domain_score = domain_specificity_score(
            zh,
            ko,
            zh_pos,
            zh_zipf,
            game_score,
        )
        common_without_game_signal = bool(
            general_score >= score_setting("general_non_noun_short_score")
            and game_score < score_setting("common_domain_min")
            and not pattern("ascii_or_digit_signal").search(zh)
        )
        common_noun_without_domain_signal = bool(
            common_noun >= score_setting("common_noun_full_threshold")
            and domain_score < score_setting("common_domain_min")
            and not has_game_anchor(zh)
            and zh.upper() not in lexicon("acronyms")
            and not pattern("ascii_or_digit_signal").search(zh)
        )

        stem, suffix = split_compound(zh)
        compound = bool(
            stem
            and suffix
            and len(families.get(stem, set())) >= int_setting("compound_family_min_suffixes")
            and len(stem) >= int_setting("compound_stem_min_length")
            and not pattern("compound_blockers").search(zh)
        )

        hard: list[str] = []
        if not ko:
            hard.append("missing_ko_for_zh_ko_glossary")
        if any(pattern("placeholder").search(row.get(lang, "") or "") for lang in LANGS):
            hard.append("placeholder_or_square_bracket_markup")
        if pattern("book_title").search(zh):
            hard.append("book_or_test_title_markup")
        if pattern("paren_prefix").search(zh):
            hard.append("parenthetical_modifier_fragment")
        if pattern("sentence_punct").search(zh):
            hard.append("sentence_punctuation")
        if zh in lexicon("nonterm_exact"):
            hard.append("standalone_ui_action_or_fragment")
        if pattern("standalone_numeric").fullmatch(zh):
            hard.append("standalone_numeric_or_signed_token")
        if has_hangul(zh):
            hard.append("zh_column_contains_hangul")
        if not has_cjk(zh) and zh.upper() not in lexicon("acronyms"):
            hard.append("zh_column_has_no_chinese_content")
        if pattern("ui_status_fragment").search(zh):
            hard.append("ui_or_status_sentence_fragment")
        if common_without_game_signal:
            hard.append("common_word_without_game_term_signal")
        if common_noun_without_domain_signal:
            hard.append("common_noun_without_domain_signal")
        if no_product_evidence:
            hard.append("not_in_segments_redundant_for_current_corpus")

        phrase: list[str] = []
        if any(zh.startswith(start) for start in lexicon_list("ui_starts")):
            phrase.append("ui_or_sentence_start")
        if pattern("zh_sentence_end").search(zh):
            phrase.append("zh_sentence_particle_end")
        if ko and pattern("ko_sentence_end").search(ko):
            phrase.append("ko_sentence_or_verb_end")
        if any(marker in zh for marker in lexicon_list("phrase_markers")) and not any(
            zh.endswith(suffix) for suffix in lexicon_list("noun_suffixes")
        ):
            phrase.append("phrase_marker_without_noun_suffix")
        if len(zh) >= 9 and (
            any(marker in zh for marker in lexicon_list("phrase_markers"))
            or (ko and pattern("ko_sentence_end").search(ko))
        ):
            phrase.append("long_sentence_like")

        proper_signal = bool(
            pattern("ascii_or_digit_signal").search(zh) or "【" in zh or "】" in zh
        )
        semantic_low = bool(
            ko
            and bilingual_score < score_setting("semantic_low_bilingual")
            and product_score == 0.0
            and noun_score < score_setting("semantic_low_noun")
            and not proper_signal
        )
        if semantic_low:
            phrase.append("low_embedding_similarity_without_product_or_noun_signal")

        if hard:
            action = "AUTO_REMOVE"
            reasons = hard + phrase
        elif compound:
            action = "AUTO_SPLIT_COMPOUND"
            reasons = ["compound_family_suffix", *phrase]
        elif semantic_low:
            action = "AUTO_REMOVE"
            reasons = phrase
        elif (len(phrase) >= 2) or (
            phrase and noun_score < score_setting("term_score_noun_min")
        ):
            action = "AUTO_REMOVE"
            reasons = phrase
        else:
            term_score = (
                score_setting("term_score_noun_weight") * noun_score
                + score_setting("term_score_bilingual_weight") * max(0.0, bilingual_score)
                + score_setting("term_score_game_weight") * game_score
            )
            if (
                term_score >= score_setting("term_score_keep_threshold")
                and noun_score >= score_setting("term_score_noun_min")
            ):
                action = "AUTO_KEEP"
                reasons = phrase or ["termhood_semantic_supported"]
            else:
                action = "KEEP_UNCERTAIN"
                reasons = phrase or ["weak_termhood_or_mid_semantic_confidence"]

        term_score = (
            score_setting("term_score_noun_weight") * noun_score
            + score_setting("term_score_bilingual_weight") * max(0.0, bilingual_score)
            + score_setting("term_score_game_weight") * game_score
        )
        classified.append(
            {
                "row": row,
                "action": action,
                "reasons": reasons,
                "term_score": max(0.0, min(1.0, term_score)),
                "noun_score": noun_score,
                "zh_noun_score": zh_score,
                "ko_noun_score": ko_score,
                "product_evidence_score": product_score,
                "compound_score": 1.0 if compound else 0.0,
                "bilingual_score": bilingual_score,
                "general_word_score": general_score,
                "game_term_score": game_score,
                "common_noun_score": common_noun,
                "domain_specificity_score": domain_score,
                "game_embedding_score": game_embedding_score,
                "generic_embedding_score": generic_embedding_score,
                "zh_zipf_frequency": zh_zipf,
                "ko_zipf_frequency": ko_zipf,
                "embedding_model": embedding_model,
                "embedding_device": embedding_device,
                "zh_segment_count": zh_count,
                "ko_segment_count": ko_count,
                "stem": stem,
                "suffix": suffix,
                "family_size": len(families.get(stem, set())) if stem else 0,
                "zh_pos": zh_pos,
                "ko_pos": ko_pos,
            }
        )

    return classified


def enforce_strict_pairs(classified: list[dict[str, Any]]) -> OrderedDict[tuple[str, str], dict[str, Any]]:
    keep_items = [
        item
        for item in classified
        if item["action"] not in {"AUTO_REMOVE", "AUTO_SPLIT_COMPOUND"}
    ]
    by_pair: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()

    for item in keep_items:
        row = item["row"]
        key = (row["zh-CN"], row["ko"])
        if key not in by_pair:
            by_pair[key] = item
            continue

        base = by_pair[key]
        conflict = False
        for lang in LANGS:
            if lang in {"zh-CN", "ko"}:
                continue
            left = base["row"].get(lang) or ""
            right = row.get(lang) or ""
            if left and right and left != right:
                conflict = True
                break

        if conflict:
            item["action"] = "AUTO_REMOVE"
            item["reasons"] = [
                *item["reasons"],
                "duplicate_zh_ko_with_target_language_conflict",
            ]
        else:
            for lang in LANGS:
                if not base["row"].get(lang) and row.get(lang):
                    base["row"][lang] = row[lang]
            item["action"] = "MERGED_DUPLICATE"
            item["reasons"] = [*item["reasons"], "merged_into_existing_zh_ko_pair"]

    post_keep = [
        item
        for item in by_pair.values()
        if item["action"] not in {"AUTO_REMOVE", "AUTO_SPLIT_COMPOUND", "MERGED_DUPLICATE"}
    ]
    zh_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ko_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in post_keep:
        row = item["row"]
        if row["zh-CN"] and row["ko"]:
            zh_groups[row["zh-CN"]].append(item)
            ko_groups[row["ko"]].append(item)

    conflict_ids: set[int] = set()
    for group in zh_groups.values():
        if len({item["row"]["ko"] for item in group}) > 1:
            conflict_ids.update(id(item) for item in group)
    for group in ko_groups.values():
        if len({item["row"]["zh-CN"] for item in group}) > 1:
            conflict_ids.update(id(item) for item in group)

    for item in post_keep:
        if id(item) in conflict_ids:
            item["action"] = "AUTO_REMOVE"
            item["reasons"] = [*item["reasons"], "strict_zh_ko_bidirectional_conflict"]

    return by_pair
