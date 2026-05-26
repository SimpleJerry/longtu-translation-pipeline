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
import csv
import os
import re
from collections import OrderedDict
from io import StringIO
from pathlib import Path
from typing import Any

try:
    from cleanup_common import (
        compile_regexes,
        ensure_csv_columns,
        read_json_config,
        read_term_file,
        sha256,
    )
except ModuleNotFoundError:  # pragma: no cover - module import fallback
    from scripts.cleanup_common import (
        compile_regexes,
        ensure_csv_columns,
        read_json_config,
        read_term_file,
        sha256,
    )

SEGMENT_SCHEMA = ["segment_id", "zh-CN", "ko"]
GLOSSARY_SCHEMA = ["term_id", "zh-CN", "ko"]
ZH_STANZA_PROCESSORS = "tokenize,pos"
KO_STANZA_PROCESSORS = "tokenize,pos"

AUDIT_FIELDS = [
    "original_segment_id",
    "split_index",
    "action",
    "reason",
    "semantic_action",
    "semantic_term_score",
    "noun_score",
    "zh_noun_score",
    "ko_noun_score",
    "glossary_similarity",
    "term_seed_similarity",
    "sentence_like_score",
    "embedding_model",
    "embedding_device",
    "zh_pos",
    "ko_pos",
    "zh-CN",
    "ko",
]


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


def read_rows(path: Path, schema: list[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        ensure_csv_columns(reader, schema, path)
        return [{key: (row.get(key) or "").strip() for key in schema} for row in reader]


def read_glossary(path: Path) -> tuple[set[tuple[str, str]], list[str]]:
    rows = read_rows(path, GLOSSARY_SCHEMA)
    pairs = {(row["zh-CN"], row["ko"]) for row in rows if row["zh-CN"] and row["ko"]}
    terms = sorted({row["zh-CN"] for row in rows if row["zh-CN"]})
    return pairs, terms


def read_thresholds(rules: dict[str, Any]) -> dict[str, float]:
    thresholds = rules.get("thresholds")
    if not isinstance(thresholds, dict):
        raise RuntimeError("segments rules.json must contain a 'thresholds' object.")
    return {key: float(value) for key, value in thresholds.items()}


def read_weights(rules: dict[str, Any]) -> dict[str, float]:
    weights = rules.get("weights")
    if not isinstance(weights, dict):
        raise RuntimeError("segments rules.json must contain a 'weights' object.")
    return {key: float(value) for key, value in weights.items()}


def require_setting(values: dict[str, float], name: str) -> float:
    try:
        return values[name]
    except KeyError as exc:
        raise RuntimeError(f"Missing segments rule setting: {name}") from exc


def placeholder_set(text: str, patterns: dict[str, re.Pattern[str]]) -> str:
    return ";".join(sorted(set(patterns["machine_placeholder"].findall(text or ""))))


def parse_tuple_like(text: str, patterns: dict[str, re.Pattern[str]]) -> list[str] | None:
    stripped = text.strip()
    if not patterns["tuple_like"].match(stripped):
        return None

    body = stripped[1:-1] if stripped[0] in "{[" and stripped[-1] in "}]" else stripped
    try:
        values = next(csv.reader(StringIO(body)))
    except csv.Error:
        return None

    values = [value.strip() for value in values]
    return values if len(values) > 1 else None


def has_meaningful_text(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff\uac00-\ud7afA-Za-z0-9]", text))


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def has_hangul(text: str) -> bool:
    return any("\uac00" <= char <= "\ud7af" for char in text)


def pure_cjk_len(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    if not all("\u4e00" <= char <= "\u9fff" for char in stripped):
        return 0
    return len(stripped)


def target_language_contamination_reason(ko: str) -> str:
    if has_cjk(ko):
        return "ko_contains_cjk"
    if ko and not has_hangul(ko):
        return "ko_without_hangul"
    return ""


def is_non_segment_single_cjk_fragment(
    zh: str,
    ko: str,
    *,
    patterns: dict[str, re.Pattern[str]],
) -> bool:
    return (
        pure_cjk_len(zh) == 1
        and not patterns["machine_placeholder"].search(zh + ko)
        and not patterns["sentence_punctuation"].search(zh + ko)
        and not patterns["tuple_wrapper"].match(zh)
        and not patterns["tuple_wrapper"].match(ko)
    )


def strip_presentation_tags(text: str, patterns: dict[str, re.Pattern[str]]) -> str:
    # Use spaces as a buffer so tag removal does not glue adjacent Latin/Korean text.
    value = patterns["presentation_tag"].sub(" ", text)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" ?\\n ?", r"\\n", value)
    value = re.sub(r" (?=[,，.。!?！？;；:：）)\]}])", "", value)
    value = re.sub(r"(?<=[（(\[{]) ", "", value)
    value = re.sub(r"(?<=[\u4e00-\u9fff]) (?=[\u4e00-\u9fff])", "", value)
    return value.strip()


def wrapper_match(text: str, patterns: dict[str, re.Pattern[str]]) -> tuple[str, str] | None:
    for name in ["brace_quote_wrapper", "quote_wrapper", "paren_wrapper"]:
        match = patterns[name].match(text)
        if match:
            return name, match.group(1).strip()
    return None


def unknown_angle_tags(text: str, patterns: dict[str, re.Pattern[str]]) -> list[str]:
    unknown: list[str] = []
    for token in patterns["angle_tag"].findall(text):
        if patterns["presentation_tag"].fullmatch(token):
            continue
        if patterns["machine_angle_placeholder"].fullmatch(token):
            continue
        unknown.append(token)
    return unknown


def normalize_row(
    row: dict[str, str],
    *,
    patterns: dict[str, re.Pattern[str]],
    normalized_markup: list[dict[str, str]],
    normalized_wrappers: list[dict[str, str]],
    markup_mismatch_review: list[dict[str, str]],
) -> dict[str, str]:
    original_zh = row["zh-CN"]
    original_ko = row["ko"]
    normalized = dict(row)

    zh_has_tag = bool(patterns["presentation_tag"].search(original_zh))
    ko_has_tag = bool(patterns["presentation_tag"].search(original_ko))
    zh_unknown = unknown_angle_tags(original_zh, patterns)
    ko_unknown = unknown_angle_tags(original_ko, patterns)
    if zh_has_tag or ko_has_tag:
        normalized["zh-CN"] = strip_presentation_tags(original_zh, patterns)
        normalized["ko"] = strip_presentation_tags(original_ko, patterns)
        normalized_markup.append(
            {
                "original_segment_id": row["segment_id"],
                "zh_tag_count": str(len(patterns["presentation_tag"].findall(original_zh))),
                "ko_tag_count": str(len(patterns["presentation_tag"].findall(original_ko))),
                "original_zh-CN": original_zh,
                "original_ko": original_ko,
                "normalized_zh-CN": normalized["zh-CN"],
                "normalized_ko": normalized["ko"],
            }
        )
    if zh_has_tag != ko_has_tag or zh_unknown or ko_unknown:
        markup_mismatch_review.append(
            {
                "original_segment_id": row["segment_id"],
                "mismatch_type": "presentation_tag_one_side_or_unknown_angle",
                "zh_unknown_angle_tags": ";".join(zh_unknown),
                "ko_unknown_angle_tags": ";".join(ko_unknown),
                "original_zh-CN": original_zh,
                "original_ko": original_ko,
                "normalized_zh-CN": normalized["zh-CN"],
                "normalized_ko": normalized["ko"],
            }
        )

    zh_wrapper = wrapper_match(normalized["zh-CN"], patterns)
    ko_wrapper = wrapper_match(normalized["ko"], patterns)
    if zh_wrapper and ko_wrapper and zh_wrapper[0] == ko_wrapper[0]:
        before_zh = normalized["zh-CN"]
        before_ko = normalized["ko"]
        normalized["zh-CN"] = zh_wrapper[1]
        normalized["ko"] = ko_wrapper[1]
        normalized_wrappers.append(
            {
                "original_segment_id": row["segment_id"],
                "wrapper_type": zh_wrapper[0],
                "original_zh-CN": before_zh,
                "original_ko": before_ko,
                "normalized_zh-CN": normalized["zh-CN"],
                "normalized_ko": normalized["ko"],
            }
        )
    elif bool(zh_wrapper) != bool(ko_wrapper):
        markup_mismatch_review.append(
            {
                "original_segment_id": row["segment_id"],
                "mismatch_type": "wrapper_one_side",
                "zh_unknown_angle_tags": "",
                "ko_unknown_angle_tags": "",
                "original_zh-CN": normalized["zh-CN"],
                "original_ko": normalized["ko"],
                "normalized_zh-CN": normalized["zh-CN"],
                "normalized_ko": normalized["ko"],
            }
        )
    return normalized


def batched(values: list[Any], size: int) -> list[list[Any]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def summarize_stanza_doc(doc: Any) -> dict[str, Any]:
    words = [word for sent in doc.sentences for word in sent.words]
    upos = [word.upos for word in words]
    summary = " ".join(f"{word.text}/{word.upos}" for word in words[:10])
    return {"upos": upos, "summary": summary}


def load_stanza_pipelines(stanza_dir: Path) -> tuple[Any, Any]:
    import stanza

    common = {"model_dir": str(stanza_dir), "download_method": None, "verbose": False}
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


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_review_outputs(
    review_dir: Path,
    *,
    audit: list[dict[str, str]],
    split_review: list[dict[str, str]],
    placeholder_review: list[dict[str, str]],
    normalized_markup: list[dict[str, str]],
    normalized_wrappers: list[dict[str, str]],
    markup_mismatch_review: list[dict[str, str]],
    removed_markup_only: list[dict[str, str]],
    summary: OrderedDict[str, str],
) -> None:
    write_csv(review_dir / "segments_cleaning_audit.csv", AUDIT_FIELDS, audit)

    removed_non_segment = [
        row for row in audit if row["action"] == "REMOVE_NON_SEGMENT_FRAGMENT"
    ]
    write_csv(
        review_dir / "removed_segment_non_segment_fragment.csv",
        AUDIT_FIELDS,
        removed_non_segment,
    )

    removed_target_contamination = [
        row for row in audit if row["action"] == "REMOVE_TARGET_LANGUAGE_CONTAMINATION"
    ]
    write_csv(
        review_dir / "removed_segment_target_language_contamination.csv",
        AUDIT_FIELDS,
        removed_target_contamination,
    )

    removed_term_like = [row for row in audit if row["action"] == "REMOVE_TERM_LIKE"]
    write_csv(review_dir / "removed_segment_term_like.csv", AUDIT_FIELDS, removed_term_like)

    semantic_review = [
        row for row in audit if row["semantic_action"] == "REVIEW_SEMANTIC_TERM_ENTITY"
    ]
    write_csv(
        review_dir / "segments_semantic_term_review.csv",
        AUDIT_FIELDS,
        semantic_review,
    )

    removed_structured = [
        row for row in audit if row["action"] == "REMOVE_STRUCTURED_UNPARSED"
    ]
    write_csv(
        review_dir / "removed_segment_structured_unparsed.csv",
        AUDIT_FIELDS,
        removed_structured,
    )

    markup_only_fields = [
        "original_segment_id",
        "original_zh-CN",
        "original_ko",
        "normalized_zh-CN",
        "normalized_ko",
    ]
    write_csv(
        review_dir / "removed_segment_markup_only.csv",
        markup_only_fields,
        removed_markup_only,
    )

    split_fields = [
        "original_segment_id",
        "split_index",
        "action",
        "reason",
        "semantic_action",
        "semantic_term_score",
        "noun_score",
        "glossary_similarity",
        "term_seed_similarity",
        "sentence_like_score",
        "zh-CN",
        "ko",
        "source_zh-CN",
        "source_ko",
    ]
    write_csv(review_dir / "split_segment_structured.csv", split_fields, split_review)

    placeholder_fields = [
        "original_segment_id",
        "zh_placeholders",
        "ko_placeholders",
        "zh-CN",
        "ko",
    ]
    write_csv(
        review_dir / "segments_placeholder_review.csv",
        placeholder_fields,
        placeholder_review,
    )

    markup_fields = [
        "original_segment_id",
        "zh_tag_count",
        "ko_tag_count",
        "original_zh-CN",
        "original_ko",
        "normalized_zh-CN",
        "normalized_ko",
    ]
    write_csv(
        review_dir / "normalized_segment_markup.csv",
        markup_fields,
        normalized_markup,
    )

    wrapper_fields = [
        "original_segment_id",
        "wrapper_type",
        "original_zh-CN",
        "original_ko",
        "normalized_zh-CN",
        "normalized_ko",
    ]
    write_csv(
        review_dir / "normalized_segment_wrappers.csv",
        wrapper_fields,
        normalized_wrappers,
    )

    mismatch_fields = [
        "original_segment_id",
        "mismatch_type",
        "zh_unknown_angle_tags",
        "ko_unknown_angle_tags",
        "original_zh-CN",
        "original_ko",
        "normalized_zh-CN",
        "normalized_ko",
    ]
    write_csv(
        review_dir / "segments_markup_mismatch_review.csv",
        mismatch_fields,
        markup_mismatch_review,
    )

    write_csv(
        review_dir / "segments_cleaning_summary.csv",
        ["metric", "value"],
        [{"metric": key, "value": value} for key, value in summary.items()],
    )


def write_segments(path: Path, kept_rows: list[dict[str, str]]) -> None:
    output = [
        {"segment_id": str(index), "zh-CN": row["zh-CN"], "ko": row["ko"]}
        for index, row in enumerate(kept_rows, 1)
    ]
    write_csv(path, SEGMENT_SCHEMA, output)


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
