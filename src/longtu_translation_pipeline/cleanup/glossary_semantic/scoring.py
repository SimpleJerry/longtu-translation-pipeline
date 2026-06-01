"""Semantic scoring functions for glossary_semantic (ADR-0033 step 9b)."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .config import (
    int_setting,
    lexicon,
    lexicon_list,
    pattern,
    score_setting,
)

try:
    from wordfreq import zipf_frequency
except Exception:  # pragma: no cover - optional dependency guard
    zipf_frequency = None

ZIPF_CACHE: dict[tuple[str, str], float] = {}


def has_cjk(text: str) -> bool:
    return any("一" <= char <= "鿿" for char in text)


def has_hangul(text: str) -> bool:
    return any("가" <= char <= "힯" for char in text)


def split_compound(zh: str) -> tuple[str, str]:
    for suffix in lexicon_list("compound_suffixes"):
        if zh.endswith(suffix) and len(zh) > len(suffix) + 1:
            return zh[: -len(suffix)], suffix
    return "", ""


def build_compound_families(rows: list[dict[str, str]]) -> dict[str, set[str]]:
    families: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        stem, suffix = split_compound(row["zh-CN"])
        if stem and suffix and not pattern("compound_blockers").search(row["zh-CN"]):
            families[stem].add(suffix)
    return families


def zh_noun_score(text: str, stanza_info: dict[str, Any]) -> tuple[float, str]:
    import jieba.posseg as pseg

    if not text:
        return 0.0, ""

    try:
        jieba_tokens = [(word, flag) for word, flag in pseg.cut(text)]
    except Exception:
        jieba_tokens = []

    jieba_flags = [flag for _, flag in jieba_tokens]
    jieba_noun_flags = {"n", "nr", "nrfg", "nrt", "ns", "nt", "nz", "ng", "eng", "x", "m"}
    jieba_hits = sum(
        1 for flag in jieba_flags if flag in jieba_noun_flags or flag.startswith("n")
    )
    jieba_score = jieba_hits / max(1, len(jieba_flags)) if jieba_flags else 0.0

    stanza_upos = stanza_info.get("upos", [])
    stanza_root = stanza_info.get("root_upos", "")
    stanza_nouns = {"NOUN", "PROPN", "NUM", "X"}
    stanza_hits = sum(1 for upos in stanza_upos if upos in stanza_nouns)
    stanza_score = stanza_hits / max(1, len(stanza_upos)) if stanza_upos else 0.0

    score = (
        score_setting("zh_base")
        + score_setting("zh_jieba_weight") * jieba_score
        + score_setting("zh_stanza_weight") * stanza_score
    )
    if stanza_root in {"NOUN", "PROPN"}:
        score += score_setting("zh_root_noun_bonus")
    if stanza_root in {"VERB", "AUX", "ADJ"}:
        score -= score_setting("zh_root_non_noun_penalty")
    if int_setting("zh_short_min") <= len(text) <= int_setting("zh_short_max"):
        score += score_setting("zh_short_bonus")
    if any(text.endswith(suffix) for suffix in lexicon_list("noun_suffixes")):
        score += score_setting("zh_noun_suffix_bonus")
    if re.search(r"[A-Za-z0-9·+.-]", text):
        score += score_setting("zh_ascii_bonus")
    if pattern("sentence_punct").search(text) or pattern("zh_sentence_end").search(text):
        score -= score_setting("zh_sentence_penalty")
    if any(marker in text for marker in lexicon_list("phrase_markers")) and not any(
        text.endswith(suffix) for suffix in lexicon_list("noun_suffixes")
    ):
        score -= score_setting("zh_phrase_marker_penalty")
    if (
        pattern("book_title").search(text)
        or pattern("paren_prefix").search(text)
        or pattern("placeholder").search(text)
    ):
        score -= score_setting("zh_markup_penalty")

    evidence = " | ".join(
        [
            "jieba=" + " ".join(f"{w}/{flag}" for w, flag in jieba_tokens[:8]),
            "stanza=" + stanza_info.get("summary", ""),
        ]
    )
    return max(0.0, min(1.0, score)), evidence


def ko_noun_score(text: str, kiwi: Any, stanza_info: dict[str, Any]) -> tuple[float, str]:
    if not text:
        return 0.0, ""

    try:
        kiwi_tokens = kiwi.tokenize(text)
    except Exception:
        kiwi_tokens = []

    ko_noun_tags = {"NNG", "NNP", "NNB", "NR", "NP", "SL", "SH", "SN", "XR"}
    ko_bad_final = {"VV", "VA", "VX", "VCP", "VCN", "EF", "EC", "ETM", "ETN", "EP"}
    meaningful = [
        token
        for token in kiwi_tokens
        if not token.tag.startswith("J") and token.tag not in {"SF", "SP", "SS", "SE", "SO", "SW"}
    ]
    kiwi_hits = sum(
        1 for token in meaningful if token.tag in ko_noun_tags or token.tag.startswith("NN")
    )
    kiwi_score = kiwi_hits / max(1, len(meaningful)) if meaningful else 0.0

    stanza_upos = stanza_info.get("upos", [])
    stanza_root = stanza_info.get("root_upos", "")
    stanza_nouns = {"NOUN", "PROPN", "NUM", "X"}
    stanza_hits = sum(1 for upos in stanza_upos if upos in stanza_nouns)
    stanza_score = stanza_hits / max(1, len(stanza_upos)) if stanza_upos else 0.0

    score = (
        score_setting("ko_base")
        + score_setting("ko_kiwi_weight") * kiwi_score
        + score_setting("ko_stanza_weight") * stanza_score
    )
    if meaningful and (meaningful[-1].tag in ko_noun_tags or meaningful[-1].tag.startswith("NN")):
        score += score_setting("ko_noun_final_bonus")
    if meaningful and meaningful[-1].tag in ko_bad_final:
        score -= score_setting("ko_bad_final_penalty")
    if stanza_root in {"NOUN", "PROPN"}:
        score += score_setting("ko_root_noun_bonus")
    if stanza_root in {"VERB", "AUX", "ADJ"}:
        score -= score_setting("ko_root_non_noun_penalty")
    if pattern("ko_sentence_end").search(text):
        score -= score_setting("ko_sentence_penalty")
    if pattern("ko_punctuation").search(text):
        score -= score_setting("ko_punctuation_penalty")

    evidence = " | ".join(
        [
            "kiwi=" + " ".join(f"{token.form}/{token.tag}" for token in kiwi_tokens[:10]),
            "stanza=" + stanza_info.get("summary", ""),
        ]
    )
    return max(0.0, min(1.0, score)), evidence


def encode_similarities_and_game_scores(
    model: Any,
    rows: list[dict[str, str]],
    game_seed_terms: list[str],
    common_noun_seed_terms: list[str],
) -> tuple[Any, Any, Any]:
    import numpy as np

    zh_texts = [row["zh-CN"] or "[EMPTY]" for row in rows]
    ko_texts = [row["ko"] or "[EMPTY]" for row in rows]
    print(f"Encoding zh-CN embeddings: {len(zh_texts)}")
    zh_emb = model.encode(
        zh_texts,
        batch_size=96,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    )
    print(f"Encoding ko embeddings: {len(ko_texts)}")
    ko_emb = model.encode(
        ko_texts,
        batch_size=96,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    )
    print(f"Encoding game seed embeddings: {len(game_seed_terms)}")
    seed_emb = model.encode(
        game_seed_terms,
        batch_size=32,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    centroid = seed_emb.mean(axis=0)
    centroid = centroid / max(float(np.linalg.norm(centroid)), 1e-9)
    print(f"Encoding common noun seed embeddings: {len(common_noun_seed_terms)}")
    generic_seed_emb = model.encode(
        common_noun_seed_terms,
        batch_size=32,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    generic_centroid = generic_seed_emb.mean(axis=0)
    generic_centroid = generic_centroid / max(float(np.linalg.norm(generic_centroid)), 1e-9)
    return (
        np.sum(zh_emb * ko_emb, axis=1),
        np.dot(zh_emb, centroid),
        np.dot(zh_emb, generic_centroid),
    )


def root_is_non_noun(pos_summary: str) -> bool:
    return "/VERB/root" in pos_summary or "/ADJ/root" in pos_summary


def has_game_anchor(text: str) -> bool:
    upper = text.upper()
    return any(anchor in text or anchor in upper for anchor in lexicon("game_anchors"))


def general_word_score(zh: str, ko: str, zh_pos: str) -> float:
    score = 0.0
    if zh in lexicon("general_zh") or ko in lexicon("general_ko"):
        score = max(score, score_setting("general_word_score"))
    if root_is_non_noun(zh_pos) and len(zh) <= 4:
        score = max(score, score_setting("general_non_noun_short_score"))
    if root_is_non_noun(zh_pos) and zh in lexicon("general_zh"):
        score = max(score, score_setting("general_word_score"))
    return score


def game_term_score(zh: str, ko: str, game_embedding_score: float) -> float:
    score = 0.0
    if zh.upper() in lexicon("acronyms"):
        score = max(score, score_setting("game_acronym_score"))
    if has_game_anchor(zh):
        score = max(score, score_setting("game_anchor_score"))
    if any(zh.endswith(suffix) for suffix in lexicon_list("noun_suffixes")):
        score = max(score, score_setting("game_suffix_score"))
    if game_embedding_score >= score_setting("game_embedding_threshold"):
        score = max(score, score_setting("game_embedding_score"))
    if pattern("ascii_or_digit_signal").search(zh):
        score = max(score, score_setting("game_ascii_score"))
    if any(token in ko for token in lexicon("ko_game_tokens")):
        score = max(score, score_setting("game_ko_token_score"))
    return score


def safe_zipf_frequency(text: str, lang: str) -> float:
    if not text or zipf_frequency is None:
        return -1.0
    key = (text, lang)
    if key in ZIPF_CACHE:
        return ZIPF_CACHE[key]
    try:
        value = float(zipf_frequency(text, lang))
    except Exception:
        value = -1.0
    ZIPF_CACHE[key] = value
    return value


def is_proper_like(zh_pos: str) -> bool:
    return bool(
        "/PROPN/root" in zh_pos
        or pattern("jieba_proper_flags").search(zh_pos)
    )


def common_noun_score(
    zh: str,
    ko: str,
    zh_score: float,
    ko_score: float,
    zh_zipf: float,
    ko_zipf: float,
    generic_embedding_score: float,
) -> float:
    score = 0.0
    noun_like = (
        zh_score >= score_setting("common_noun_noun_like_threshold")
        and ko_score >= score_setting("common_noun_noun_like_threshold")
    )
    if zh in lexicon("common_zh") or ko in lexicon("common_ko"):
        score = max(score, score_setting("common_noun_exact_score"))
    if noun_like and len(zh) <= 4 and zh_zipf >= score_setting("common_noun_zh_zipf_high"):
        score = max(score, score_setting("common_noun_high_score"))
    elif noun_like and len(zh) <= 4 and zh_zipf >= score_setting("common_noun_zh_zipf_mid"):
        score = max(score, score_setting("common_noun_mid_score"))
    if noun_like and generic_embedding_score >= score_setting("common_noun_generic_high"):
        score = max(score, score_setting("common_noun_high_score"))
    elif (
        noun_like
        and generic_embedding_score >= score_setting("common_noun_generic_mid")
        and zh_zipf >= score_setting("common_noun_zh_zipf_low")
    ):
        score = max(score, score_setting("common_noun_generic_mid_score"))
    if ko_zipf >= score_setting("common_noun_ko_zipf") and noun_like:
        score = max(score, score_setting("common_noun_mid_score"))
    return max(0.0, min(1.0, score))


def domain_specificity_score(
    zh: str,
    ko: str,
    zh_pos: str,
    zh_zipf: float,
    game_score: float,
) -> float:
    score = game_score
    if zh.upper() in lexicon("acronyms") or has_game_anchor(zh):
        score = max(score, score_setting("domain_acronym_anchor_score"))
    if is_proper_like(zh_pos) and (
        zh_zipf < score_setting("domain_proper_zipf_max") or len(zh) >= 3
    ):
        score = max(score, score_setting("domain_proper_score"))
    if pattern("ascii_or_digit_signal").search(zh):
        score = max(score, score_setting("domain_ascii_score"))
    return max(0.0, min(1.0, score))


def acronym_component_product_score(
    zh: str, ko: str, segment_text: dict[str, str]
) -> float:
    """Allow strong game acronym compounds through the product-evidence gate.

    Exact product evidence remains the normal relevance check.  However, terms
    such as "BOSS层" may not appear as one literal string in segments even
    though the acronym itself is clearly present on both Chinese and Korean
    sides.  This narrow fallback only prevents false "not in corpus" deletion;
    it does not bypass hard noise, common-word, placeholder, or phrase filters.
    """

    zh_upper = zh.upper()
    ko_upper = ko.upper()
    for acronym in lexicon("acronyms"):
        if acronym in zh_upper and acronym in ko_upper:
            if (
                acronym in segment_text["zh-CN_upper"]
                and acronym in segment_text["ko_upper"]
            ):
                return score_setting("acronym_component_score")
    return 0.0
