"""Glossary-term matching and Korean-preservation checks for cross-cleaning.

Extracted verbatim from the former ``scripts/segments_glossary_cross_cleaning_pipeline.py``
under ADR-0033. Longest-first, non-overlapping Chinese matches; preservation is
exact or no-space exact on the Korean side (ADR-0029 spirit). Never rewrites
Korean (ADR-0018).
"""

from __future__ import annotations

import re

from .models import GlossaryTerm, TermMatch


def find_term_matches(
    source: str, target: str, terms: list[GlossaryTerm]
) -> list[TermMatch]:
    matches: list[TermMatch] = []
    occupied: list[tuple[int, int]] = []
    for term in terms:
        start = source.find(term.zh)
        while start >= 0:
            end = start + len(term.zh)
            if not overlaps_any(start, end, occupied):
                occupied.append((start, end))
                matches.append(
                    TermMatch(
                        term=term,
                        start=start,
                        end=end,
                        preserved=contains_exact_or_no_space(target, term.ko),
                    )
                )
            start = source.find(term.zh, start + 1)
    return sorted(matches, key=lambda match: (match.start, match.end))


def contains_exact_or_no_space(text: str, expected: str) -> bool:
    if expected in text:
        return True
    normalized_text = normalize_no_space(text)
    normalized_expected = normalize_no_space(expected)
    return bool(normalized_expected and normalized_expected in normalized_text)


def normalize_no_space(text: str) -> str:
    return re.sub(r"\s+", "", text)


def overlaps_any(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(not (end <= span_start or start >= span_end) for span_start, span_end in spans)
