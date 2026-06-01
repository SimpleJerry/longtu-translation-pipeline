"""Semantic scoring functions for the segments_cleaning pipeline (ADR-0033 step 8b)."""

from __future__ import annotations

import re
from typing import Any

from .normalize import has_cjk


def zh_noun_score(text: str, stanza_info: dict[str, Any]) -> tuple[float, str]:
    import jieba.posseg as pseg

    if not text:
        return 0.0, ""

    try:
        jieba_tokens = [(word, flag) for word, flag in pseg.cut(text)]
    except Exception:
        jieba_tokens = []
    noun_flags = {"n", "nr", "nrfg", "nrt", "ns", "nt", "nz", "ng", "eng", "x"}
    jieba_hits = sum(
        1 for _, flag in jieba_tokens if flag in noun_flags or flag.startswith("n")
    )
    jieba_score = jieba_hits / max(1, len(jieba_tokens)) if jieba_tokens else 0.0

    upos = stanza_info.get("upos", [])
    stanza_hits = sum(1 for item in upos if item in {"NOUN", "PROPN", "NUM", "X"})
    stanza_score = stanza_hits / max(1, len(upos)) if upos else 0.0

    score = 0.15 + 0.45 * jieba_score + 0.40 * stanza_score
    if not has_cjk(text) and not re.search(r"[A-Za-z]", text):
        score -= 0.35
    if re.search(r"[A-Za-z0-9]", text):
        score += 0.08
    return max(0.0, min(1.0, score)), "jieba=" + " ".join(
        f"{word}/{flag}" for word, flag in jieba_tokens[:8]
    ) + " | stanza=" + stanza_info.get("summary", "")


def ko_noun_score(text: str, kiwi: Any, stanza_info: dict[str, Any]) -> tuple[float, str]:
    if not text:
        return 0.0, ""

    try:
        kiwi_tokens = kiwi.tokenize(text)
    except Exception:
        kiwi_tokens = []

    noun_tags = {"NNG", "NNP", "NNB", "NR", "NP", "SL", "SH", "SN", "XR"}
    verb_final_tags = {"VV", "VA", "VX", "VCP", "VCN", "EF", "EC", "ETM", "ETN", "EP"}
    meaningful = [
        token
        for token in kiwi_tokens
        if not token.tag.startswith("J") and token.tag not in {"SF", "SP", "SS", "SE", "SO", "SW"}
    ]
    kiwi_hits = sum(
        1 for token in meaningful if token.tag in noun_tags or token.tag.startswith("NN")
    )
    kiwi_score = kiwi_hits / max(1, len(meaningful)) if meaningful else 0.0

    upos = stanza_info.get("upos", [])
    stanza_hits = sum(1 for item in upos if item in {"NOUN", "PROPN", "NUM", "X"})
    stanza_score = stanza_hits / max(1, len(upos)) if upos else 0.0

    score = 0.15 + 0.45 * kiwi_score + 0.35 * stanza_score
    if meaningful and (
        meaningful[-1].tag in noun_tags or meaningful[-1].tag.startswith("NN")
    ):
        score += 0.10
    if meaningful and meaningful[-1].tag in verb_final_tags:
        score -= 0.25
    return max(0.0, min(1.0, score)), "kiwi=" + " ".join(
        f"{token.form}/{token.tag}" for token in kiwi_tokens[:10]
    ) + " | stanza=" + stanza_info.get("summary", "")


def sentence_like_score(
    zh: str,
    ko: str,
    *,
    patterns: dict[str, re.Pattern[str]],
    sentence_markers: list[str],
) -> float:
    text = f"{zh}\n{ko}"
    score = 0.0
    if patterns["machine_placeholder"].search(text):
        score += 1.0
    if patterns["sentence_punctuation"].search(text):
        score += 0.45
    if patterns["zh_sentence_end"].search(zh):
        score += 0.35
    if patterns["ko_sentence_end"].search(ko):
        score += 0.35
    if any(marker in zh for marker in sentence_markers):
        score += 0.45
    return max(0.0, min(1.0, score))


def encode_semantic_scores(
    *,
    model: Any,
    items: list[dict[str, str]],
    glossary_terms: list[str],
    seed_terms: list[str],
) -> tuple[list[float], list[float], str]:
    import numpy as np

    if not items:
        return [], [], ""

    zh_texts = [item["zh-CN"] or "[EMPTY]" for item in items]
    print(f"Encoding segment candidate embeddings: {len(zh_texts)}")
    zh_emb = model.encode(
        zh_texts,
        batch_size=96,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    )

    glossary_similarity = np.zeros(len(items), dtype="float32")
    if glossary_terms:
        print(f"Encoding glossary term embeddings: {len(glossary_terms)}")
        glossary_emb = model.encode(
            glossary_terms,
            batch_size=96,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=True,
        )
        for start in range(0, len(items), 512):
            sims = np.dot(zh_emb[start : start + 512], glossary_emb.T)
            glossary_similarity[start : start + 512] = sims.max(axis=1)

    print(f"Encoding segment term/entity seeds: {len(seed_terms)}")
    seed_emb = model.encode(
        seed_terms,
        batch_size=32,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    seed_similarity = np.zeros(len(items), dtype="float32")
    for start in range(0, len(items), 512):
        sims = np.dot(zh_emb[start : start + 512], seed_emb.T)
        seed_similarity[start : start + 512] = sims.max(axis=1)

    seed_set = set(seed_terms)
    for idx, item in enumerate(items):
        if item["zh-CN"] in seed_set:
            seed_similarity[idx] = 1.0
    return glossary_similarity.tolist(), seed_similarity.tolist(), "max_zh_embedding"
