"""Terminology marker protection for Chinese-Korean training text.

The current project direction intentionally uses one glossary marker shape on
both sides of a training pair: ``<start>visible term<end>``.  Historical
the old dual-term marker and code-id experiments remain documented as legacy
notebook work, but they are not part of this module's active behavior.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


GLOSSARY_SCHEMA = ["zh-CN", "ko"]
GLOSSARY_MARKER_RE = re.compile(r"<start>(.*?)<end>")


@dataclass(frozen=True)
class GlossaryTerm:
    zh_cn: str
    ko: str


@dataclass(frozen=True)
class ProtectionResult:
    source_text: str
    target_text: str
    metadata: dict[str, object]


def load_glossary_terms(path: str | Path) -> list[GlossaryTerm]:
    glossary_path = Path(path)
    with glossary_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [column for column in GLOSSARY_SCHEMA if column not in (reader.fieldnames or [])]
        if missing:
            raise RuntimeError(f"Glossary is missing required columns {missing}: {glossary_path}")

        terms = [
            GlossaryTerm(row["zh-CN"].strip(), row["ko"].strip())
            for row in reader
            if row.get("zh-CN", "").strip() and row.get("ko", "").strip()
        ]

    return sorted(terms, key=lambda term: len(term.zh_cn), reverse=True)


def protect_training_pair(
    source_text: str,
    target_text: str,
    terms: Sequence[GlossaryTerm],
) -> ProtectionResult:
    source_marked, target_marked, applied_terms = protect_glossary_terms(
        source_text,
        target_text,
        terms,
    )
    return ProtectionResult(
        source_text=source_marked,
        target_text=target_marked,
        metadata={"glossary_terms_applied": applied_terms},
    )


def protect_glossary_terms(
    source_text: str,
    target_text: str,
    terms: Sequence[GlossaryTerm],
) -> tuple[str, str, int]:
    source_occupied = occupied_ranges(source_text)
    target_occupied = occupied_ranges(target_text)
    source_replacements: list[tuple[int, int, str]] = []
    target_replacements: list[tuple[int, int, str]] = []
    applied_terms = 0

    for term in terms:
        source_hits = available_occurrences(source_text, term.zh_cn, source_occupied)
        target_hits = available_occurrences(target_text, term.ko, target_occupied)
        if not source_hits or not target_hits:
            continue

        applied_terms += 1
        for start, end in source_hits:
            source_occupied.append((start, end))
            source_replacements.append((start, end, f"<start>{term.zh_cn}<end>"))
        for start, end in target_hits:
            target_occupied.append((start, end))
            target_replacements.append((start, end, f"<start>{term.ko}<end>"))

    return (
        apply_replacements(source_text, source_replacements),
        apply_replacements(target_text, target_replacements),
        applied_terms,
    )


def strip_glossary_markers(text: str) -> str:
    return GLOSSARY_MARKER_RE.sub(r"\1", text)


def occupied_ranges(text: str) -> list[tuple[int, int]]:
    return [(match.start(), match.end()) for match in GLOSSARY_MARKER_RE.finditer(text)]


def available_occurrences(
    text: str,
    needle: str,
    occupied: Sequence[tuple[int, int]],
) -> list[tuple[int, int]]:
    if not needle:
        return []

    hits: list[tuple[int, int]] = []
    start_at = 0
    while True:
        start = text.find(needle, start_at)
        if start == -1:
            break
        end = start + len(needle)
        if not overlaps_any(start, end, [*occupied, *hits]):
            hits.append((start, end))
        start_at = end
    return hits


def overlaps_any(start: int, end: int, ranges: Sequence[tuple[int, int]]) -> bool:
    return any(start < range_end and end > range_start for range_start, range_end in ranges)


def apply_replacements(text: str, replacements: Sequence[tuple[int, int, str]]) -> str:
    if not replacements:
        return text

    result: list[str] = []
    cursor = 0
    for start, end, replacement in sorted(replacements, key=lambda item: item[0]):
        result.append(text[cursor:start])
        result.append(replacement)
        cursor = end
    result.append(text[cursor:])
    return "".join(result)
