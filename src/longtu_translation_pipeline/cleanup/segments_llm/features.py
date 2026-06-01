"""Local feature detection for segment rows.

Extracted verbatim from the former ``scripts/segments_llm_cleanup_pipeline.py``
under ADR-0033. These are the local pre-judgment signals (placeholders, matched
glossary terms, target contamination, structured-string hint). Per ADR-0026
they are computed for auditing and post-response validation only; they are never
sent to the model in the prompt.
"""

from __future__ import annotations

from .models import (
    CJK_RE,
    GlossaryTerm,
    HANGUL_RE,
    PLACEHOLDER_RE,
    STRUCTURED_RE,
    SegmentFeatures,
    SegmentRow,
)


def build_features(row: SegmentRow, glossary_sorted: list[GlossaryTerm]) -> SegmentFeatures:
    placeholders = sorted(set(PLACEHOLDER_RE.findall(f"{row.zh} {row.ko}")))
    glossary_terms = find_glossary_terms(row.zh, glossary_sorted)
    return SegmentFeatures(
        placeholders=placeholders,
        glossary_terms=glossary_terms,
        target_contamination=target_is_contaminated(row.ko),
        structured_hint=bool(STRUCTURED_RE.search(row.zh) or STRUCTURED_RE.search(row.ko)),
    )


def find_glossary_terms(text: str, glossary_sorted: list[GlossaryTerm]) -> list[GlossaryTerm]:
    matches: list[tuple[int, int, GlossaryTerm]] = []
    occupied: list[tuple[int, int]] = []
    for term in glossary_sorted:
        start = text.find(term.zh)
        while start != -1:
            end = start + len(term.zh)
            if not any(start < used_end and end > used_start for used_start, used_end in occupied):
                matches.append((start, end, term))
                occupied.append((start, end))
                break
            start = text.find(term.zh, start + 1)
    return [term for _, _, term in sorted(matches, key=lambda item: item[0])]


def target_is_contaminated(text: str) -> bool:
    return bool(CJK_RE.search(text) or (text.strip() and not HANGUL_RE.search(text)))
