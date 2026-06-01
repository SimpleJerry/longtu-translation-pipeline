"""Domain and weak-word scoring for glossary terms (ADR-0007).

Extracted verbatim from the former ``scripts/segments_glossary_cross_cleaning_pipeline.py``
under ADR-0033. Scores are config-driven (configs/cross_cleaning/rules.json +
configs/glossary lexicons) and clamped to [0, 1].
"""

from __future__ import annotations

from typing import Any

from .models import CrossLexicons


def score_domain(
    zh: str,
    lexicons: CrossLexicons,
    rules: dict[str, Any],
) -> float:
    scores = rules["scores"]
    upper = zh.upper()
    candidates = [0.0]
    if zh in lexicons.game_term_seeds:
        candidates.append(scores["game_seed"])
    if any(anchor and anchor in zh for anchor in lexicons.game_anchors):
        candidates.append(scores["domain_anchor"])
    if any(acronym and acronym.upper() in upper for acronym in lexicons.acronym_whitelist):
        candidates.append(scores["acronym"])
    if any(suffix and zh.endswith(suffix) for suffix in lexicons.compound_suffixes):
        candidates.append(scores["compound_suffix"])
    if any(suffix and zh.endswith(suffix) for suffix in lexicons.noun_suffixes):
        candidates.append(scores["noun_suffix"])
    length = cjk_len(zh)
    if length >= 6:
        candidates.append(scores["length_six_plus"])
    elif length >= 4:
        candidates.append(scores["length_four_plus"])
    return min(max(candidates), 1.0)


def score_weak(
    zh: str,
    domain_score: float,
    lexicons: CrossLexicons,
    rules: dict[str, Any],
) -> float:
    scores = rules["scores"]
    candidates = [0.0]
    if zh in lexicons.nonterm_exact:
        candidates.append(scores["weak_exact"])
    if zh in lexicons.general_words_zh or zh in lexicons.common_nouns_zh:
        candidates.append(scores["common_word"])
    if cjk_len(zh) <= 2 and domain_score < rules["thresholds"]["strong_domain_score_min"]:
        candidates.append(scores["short_weak"])
    return min(max(candidates), 1.0)


def cjk_len(text: str) -> int:
    return sum(1 for char in text if "一" <= char <= "鿿")
