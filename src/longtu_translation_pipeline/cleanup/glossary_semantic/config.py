"""Configuration loading and accessor functions for glossary_semantic (ADR-0033 step 9b)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from longtu_translation_pipeline.cleanup.common import (
    compile_regexes,
    read_json_config,
    read_term_file,
)

LEXICONS: dict[str, set[str] | list[str]] = {}
RULES: dict[str, Any] = {}
PATTERNS: dict[str, re.Pattern[str]] = {}


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
