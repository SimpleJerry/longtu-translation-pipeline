"""Text normalization helpers for the segments_cleaning pipeline (ADR-0033 step 8b)."""

from __future__ import annotations

import csv
import re
from io import StringIO
from typing import Any


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
    return any("一" <= char <= "鿿" for char in text)


def has_hangul(text: str) -> bool:
    return any("가" <= char <= "힯" for char in text)


def pure_cjk_len(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    if not all("一" <= char <= "鿿" for char in stripped):
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
