"""Shared helpers for local CSV cleanup pipelines."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def read_term_file(path: Path, label: str) -> list[str]:
    if not path.exists():
        raise RuntimeError(f"{label} file does not exist: {path}")

    terms: list[str] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            term = line.strip()
            if not term or term.startswith("#"):
                continue
            if term in seen:
                raise RuntimeError(
                    f"Duplicate {label} term at {path}:{line_no}: {term}"
                )
            terms.append(term)
            seen.add(term)

    if not terms:
        raise RuntimeError(f"{label} file is empty after comments: {path}")
    return terms


def read_json_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Rules config does not exist: {path}")
    with path.open(encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise RuntimeError(f"Rules config must be a JSON object: {path}")
    return data


def compile_regexes(rules: dict[str, Any]) -> dict[str, re.Pattern[str]]:
    regexes = rules.get("regex")
    if not isinstance(regexes, dict) or not regexes:
        raise RuntimeError("rules.json must contain a non-empty 'regex' object.")
    return {name: re.compile(pattern) for name, pattern in regexes.items()}


def ensure_csv_columns(reader: csv.DictReader, required: list[str], path: Path) -> None:
    missing = [column for column in required if column not in (reader.fieldnames or [])]
    if missing:
        raise RuntimeError(f"CSV is missing required columns {missing}: {path}")
