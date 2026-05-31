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
import locale
import os
import re
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Any

from longtu_translation_pipeline.cleanup.common import (
    compile_regexes,
    ensure_csv_columns,
    read_json_config,
    read_term_file,
    sha256,
)

try:
    from wordfreq import zipf_frequency
except Exception:  # pragma: no cover - optional dependency guard
    zipf_frequency = None

ZIPF_CACHE: dict[tuple[str, str], float] = {}

LANGS = ["zh-CN", "zh-TW", "en", "th", "id", "ja", "ko", "pt", "ru", "vi"]
SCHEMA = ["term_id", "zh-CN", "ko"]
LEXICONS: dict[str, set[str] | list[str]] = {}
RULES: dict[str, Any] = {}
PATTERNS: dict[str, re.Pattern[str]] = {}

ZH_STANZA_PROCESSORS = "tokenize,pos,lemma,depparse"
KO_STANZA_PROCESSORS = "tokenize,pos,lemma,depparse"


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


def load_pipeline_config(config_dir: Path) -> None:
    global LEXICONS, RULES, PATTERNS

    list_files = {
        "acronyms": "acronym_whitelist.txt",
        "game_anchors": "game_anchors.txt",
        "general_zh": "general_words_zh.txt",
        "general_ko": "general_words_ko.txt",
        "common_zh": "common_nouns_zh.txt",
        "common_ko": "common_nouns_ko.txt",
        "ui_starts": "ui_starts.txt",
        "nonterm_exact": "nonterm_exact.txt",
        "phrase_markers": "phrase_markers.txt",
        "noun_suffixes": "noun_suffixes.txt",
        "compound_suffixes": "compound_suffixes.txt",
        "ko_game_tokens": "ko_game_tokens.txt",
    }
    loaded: dict[str, set[str] | list[str]] = {}
    for key, filename in list_files.items():
        values = read_term_file(config_dir / filename, key)
        if key in {"noun_suffixes", "compound_suffixes", "phrase_markers", "ui_starts"}:
            loaded[key] = values
        else:
            loaded[key] = set(values)

    loaded["compound_suffixes"] = sorted(
        loaded["compound_suffixes"], key=len, reverse=True
    )
    RULES = read_json_config(config_dir / "rules.json")
    PATTERNS = compile_regexes(RULES)
    LEXICONS = loaded


def score_setting(name: str) -> float:
    try:
        return float(RULES["scores"][name])
    except KeyError as exc:
        raise RuntimeError(f"Missing score setting in rules.json: {name}") from exc


def int_setting(name: str) -> int:
    return int(score_setting(name))


def pattern(name: str) -> re.Pattern[str]:
    try:
        return PATTERNS[name]
    except KeyError as exc:
        raise RuntimeError(f"Missing regex setting in rules.json: {name}") from exc


def lexicon(name: str) -> set[str]:
    value = LEXICONS.get(name)
    if not isinstance(value, set):
        raise RuntimeError(f"Missing set lexicon: {name}")
    return value


def lexicon_list(name: str) -> list[str]:
    value = LEXICONS.get(name)
    if not isinstance(value, list):
        raise RuntimeError(f"Missing list lexicon: {name}")
    return value


def read_glossary_baseline(glossary_path: Path) -> list[dict[str, str]]:
    with glossary_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        ensure_csv_columns(reader, SCHEMA, glossary_path)
        rows = list(reader)

    baseline: list[dict[str, str]] = []
    for idx, row in enumerate(rows, 1):
        item = {"original_term_id": row.get("term_id") or str(idx)}
        for lang in LANGS:
            item[lang] = (row.get(lang) or "").strip()
        baseline.append(item)
    return baseline


def read_segment_evidence(segments_path: Path) -> dict[str, str]:
    text = {"zh-CN": [], "ko": []}
    with segments_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            for lang in text:
                value = (row.get(lang) or "").strip()
                if value:
                    text[lang].append(value)
    joined = {lang: "\n".join(values) for lang, values in text.items()}
    joined["zh-CN_upper"] = joined["zh-CN"].upper()
    joined["ko_upper"] = joined["ko"].upper()
    return joined


def batched(values: list[str], size: int) -> list[list[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def load_stanza_pipelines(stanza_dir: Path) -> tuple[Any, Any]:
    import stanza

    common = {
        "model_dir": str(stanza_dir),
        "download_method": None,
        "verbose": False,
    }
    try:
        zh = stanza.Pipeline("zh", processors=ZH_STANZA_PROCESSORS, **common)
        ko = stanza.Pipeline("ko", processors=KO_STANZA_PROCESSORS, **common)
    except Exception as exc:  # pragma: no cover - user-facing setup guard
        command = (
            "$env:STANZA_RESOURCES_DIR="
            f"'{stanza_dir.resolve()}'; "
            "venv\\Scripts\\python.exe -c "
            f"\"import stanza; stanza.download('zh', model_dir=r'{stanza_dir.resolve()}'); "
            f"stanza.download('ko', model_dir=r'{stanza_dir.resolve()}')\""
        )
        raise RuntimeError(
            "Stanza zh/ko models are not available. Download them first:\n"
            f"{command}\nOriginal error: {type(exc).__name__}: {exc}"
        ) from exc
    return zh, ko


def summarize_stanza_doc(doc: Any) -> dict[str, Any]:
    words = [word for sent in doc.sentences for word in sent.words]
    upos = [word.upos for word in words]
    deprels = [word.deprel for word in words]
    root_upos = next((word.upos for word in words if word.deprel == "root"), "")
    summary = " ".join(
        f"{word.text}/{word.upos}/{word.deprel}" for word in words[:10]
    )
    return {
        "upos": upos,
        "deprels": deprels,
        "root_upos": root_upos,
        "summary": summary,
    }


def build_stanza_cache(
    pipeline: Any,
    values: list[str],
    *,
    batch_size: int,
    label: str,
) -> dict[str, dict[str, Any]]:
    unique = sorted({value for value in values if value})
    cache: dict[str, dict[str, Any]] = {}
    print(f"Stanza processing {label}: {len(unique)} unique texts")
    for batch in batched(unique, batch_size):
        docs = pipeline.bulk_process(batch)
        for text, doc in zip(batch, docs):
            cache[text] = summarize_stanza_doc(doc)
    return cache


def load_embedding_model(primary: str, fallback: str, hf_home: Path) -> tuple[Any, str, str]:
    os.environ.setdefault("HF_HOME", str(hf_home.resolve()))

    import torch
    from sentence_transformers import SentenceTransformer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    try:
        return SentenceTransformer(primary, device=device), primary, device
    except Exception as exc:
        print(f"Primary embedding model failed: {type(exc).__name__}: {exc}")
        return SentenceTransformer(fallback, device=device), fallback, device


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def has_hangul(text: str) -> bool:
    return any("\uac00" <= char <= "\ud7af" for char in text)


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
