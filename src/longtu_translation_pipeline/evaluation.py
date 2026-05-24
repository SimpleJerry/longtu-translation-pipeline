"""Evaluation helpers for translation outputs.

RF-007 keeps evaluation lightweight and local: no model loading and no external
metric package dependency.  The default BLEU tokenizer is whitespace-based for
Korean text, with a character mode available through config.
"""

from __future__ import annotations

import csv
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .config import EvaluationConfig
from .text_protection import strip_glossary_markers


@dataclass(frozen=True)
class TranslationRow:
    source: str
    reference: str
    candidate: str


@dataclass(frozen=True)
class BleuResult:
    score: float
    tokenization: str
    max_order: int
    reference_length: int
    candidate_length: int
    precisions: list[float]
    brevity_penalty: float


@dataclass(frozen=True)
class GlossaryTerm:
    source: str
    target: str


@dataclass(frozen=True)
class GlossaryRowResult:
    row_number: int
    source: str
    candidate: str
    term_count: int
    matched_count: int
    missing_terms: list[str]
    status: str


@dataclass(frozen=True)
class GlossaryPreservationResult:
    total_terms: int
    matched_terms: int
    preservation_rate: float
    rows_with_terms: int
    rows_all_matched: int
    rows_partially_matched: int
    rows_not_matched: int
    rows_without_terms: int
    row_results: list[GlossaryRowResult]


@dataclass(frozen=True)
class EvaluationResult:
    input_path: Path
    row_count: int
    bleu: BleuResult
    glossary: GlossaryPreservationResult


def evaluate_translation(config: EvaluationConfig, input_override: str | Path | None = None) -> EvaluationResult:
    input_path = Path(input_override) if input_override is not None else config.input.path
    rows = read_translation_rows(
        input_path,
        config.input.source_column,
        config.input.reference_column,
        config.input.candidate_column,
    )
    terms = read_glossary_terms(
        config.glossary.path,
        config.glossary.source_column,
        config.glossary.target_column,
    )
    references = [row.reference for row in rows]
    candidates = [row.candidate for row in rows]
    bleu = compute_corpus_bleu(
        references,
        candidates,
        tokenization=config.bleu.tokenization,
        max_order=config.bleu.max_order,
        smooth_value=config.bleu.smooth_value,
    )
    glossary = compute_glossary_preservation(rows, terms)
    return EvaluationResult(input_path=input_path, row_count=len(rows), bleu=bleu, glossary=glossary)


def read_translation_rows(
    path: str | Path,
    source_column: str,
    reference_column: str,
    candidate_column: str,
) -> list[TranslationRow]:
    input_path = Path(path)
    rows: list[TranslationRow] = []
    with input_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        require_columns(input_path, reader.fieldnames, [source_column, reference_column, candidate_column])
        for row_number, row in enumerate(reader, start=2):
            source = row.get(source_column, "").strip()
            reference = row.get(reference_column, "").strip()
            candidate = row.get(candidate_column, "").strip()
            if not source:
                raise ValueError(f"Empty source at {input_path}:{row_number}")
            if not reference:
                raise ValueError(f"Empty reference at {input_path}:{row_number}")
            if not candidate:
                raise ValueError(f"Empty candidate at {input_path}:{row_number}")
            rows.append(TranslationRow(source=source, reference=reference, candidate=candidate))

    if not rows:
        raise ValueError(f"No translation rows found: {input_path}")
    return rows


def read_glossary_terms(path: str | Path, source_column: str, target_column: str) -> list[GlossaryTerm]:
    glossary_path = Path(path)
    terms: list[GlossaryTerm] = []
    with glossary_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        require_columns(glossary_path, reader.fieldnames, [source_column, target_column])
        for row in reader:
            source = row.get(source_column, "").strip()
            target = row.get(target_column, "").strip()
            if source and target:
                terms.append(GlossaryTerm(source=source, target=target))
    return sorted(terms, key=lambda term: len(term.source), reverse=True)


def compute_corpus_bleu(
    references: Sequence[str],
    candidates: Sequence[str],
    tokenization: str = "whitespace",
    max_order: int = 4,
    smooth_value: float = 0.1,
) -> BleuResult:
    if len(references) != len(candidates):
        raise ValueError("references and candidates must have the same length")
    if not references:
        raise ValueError("At least one reference/candidate pair is required")
    if max_order <= 0:
        raise ValueError("max_order must be positive")

    clipped_counts = [0] * max_order
    possible_counts = [0] * max_order
    reference_length = 0
    candidate_length = 0

    for reference, candidate in zip(references, candidates):
        reference_tokens = tokenize(reference, tokenization)
        candidate_tokens = tokenize(candidate, tokenization)
        if not reference_tokens or not candidate_tokens:
            raise ValueError("BLEU inputs must not tokenize to empty sequences")

        reference_length += len(reference_tokens)
        candidate_length += len(candidate_tokens)
        for order in range(1, max_order + 1):
            ref_counts = ngram_counts(reference_tokens, order)
            cand_counts = ngram_counts(candidate_tokens, order)
            clipped_counts[order - 1] += sum(
                min(count, ref_counts.get(ngram, 0)) for ngram, count in cand_counts.items()
            )
            possible_counts[order - 1] += max(len(candidate_tokens) - order + 1, 0)

    precisions: list[float] = []
    for clipped, possible in zip(clipped_counts, possible_counts):
        if possible == 0:
            continue
        if clipped == 0:
            precisions.append(smooth_value / (possible + smooth_value))
        else:
            precisions.append(clipped / possible)

    if not precisions:
        score = 0.0
    else:
        brevity_penalty = compute_brevity_penalty(candidate_length, reference_length)
        score = brevity_penalty * math.exp(sum(math.log(precision) for precision in precisions) / len(precisions))

    return BleuResult(
        score=score,
        tokenization=tokenization,
        max_order=max_order,
        reference_length=reference_length,
        candidate_length=candidate_length,
        precisions=precisions,
        brevity_penalty=compute_brevity_penalty(candidate_length, reference_length),
    )


def tokenize(text: str, tokenization: str) -> list[str]:
    if tokenization == "whitespace":
        return text.strip().split()
    if tokenization == "char":
        return [char for char in text.strip() if not char.isspace()]
    raise ValueError(f"Unsupported BLEU tokenization: {tokenization}")


def ngram_counts(tokens: Sequence[str], order: int) -> Counter[tuple[str, ...]]:
    return Counter(tuple(tokens[index : index + order]) for index in range(len(tokens) - order + 1))


def compute_brevity_penalty(candidate_length: int, reference_length: int) -> float:
    if candidate_length == 0:
        return 0.0
    if candidate_length > reference_length:
        return 1.0
    return math.exp(1 - reference_length / candidate_length)


def compute_glossary_preservation(
    rows: Sequence[TranslationRow],
    terms: Sequence[GlossaryTerm],
) -> GlossaryPreservationResult:
    total_terms = 0
    matched_terms = 0
    row_results: list[GlossaryRowResult] = []

    for index, row in enumerate(rows, start=1):
        row_terms = terms_in_source(row.source, terms)
        candidate = strip_glossary_markers(row.candidate)
        missing_terms = [term.target for term in row_terms if term.target not in candidate]
        row_matched = len(row_terms) - len(missing_terms)

        total_terms += len(row_terms)
        matched_terms += row_matched
        row_results.append(
            GlossaryRowResult(
                row_number=index,
                source=row.source,
                candidate=row.candidate,
                term_count=len(row_terms),
                matched_count=row_matched,
                missing_terms=missing_terms,
                status=glossary_status(len(row_terms), row_matched),
            )
        )

    rows_with_terms = sum(1 for row in row_results if row.term_count > 0)
    rows_all_matched = sum(1 for row in row_results if row.status == "all_matched")
    rows_partially_matched = sum(1 for row in row_results if row.status == "partially_matched")
    rows_not_matched = sum(1 for row in row_results if row.status == "not_matched")
    rows_without_terms = sum(1 for row in row_results if row.status == "no_terms")
    preservation_rate = matched_terms / total_terms if total_terms else 1.0

    return GlossaryPreservationResult(
        total_terms=total_terms,
        matched_terms=matched_terms,
        preservation_rate=preservation_rate,
        rows_with_terms=rows_with_terms,
        rows_all_matched=rows_all_matched,
        rows_partially_matched=rows_partially_matched,
        rows_not_matched=rows_not_matched,
        rows_without_terms=rows_without_terms,
        row_results=row_results,
    )


def terms_in_source(source: str, terms: Sequence[GlossaryTerm]) -> list[GlossaryTerm]:
    matched_terms: list[GlossaryTerm] = []
    occupied: list[tuple[int, int]] = []
    for term in terms:
        start = source.find(term.source)
        if start == -1:
            continue
        end = start + len(term.source)
        if any(start < occupied_end and end > occupied_start for occupied_start, occupied_end in occupied):
            continue
        matched_terms.append(term)
        occupied.append((start, end))
    return matched_terms


def glossary_status(term_count: int, matched_count: int) -> str:
    if term_count == 0:
        return "no_terms"
    if matched_count == term_count:
        return "all_matched"
    if matched_count == 0:
        return "not_matched"
    return "partially_matched"


def require_columns(path: Path, fieldnames: Sequence[str] | None, columns: Iterable[str]) -> None:
    missing = [column for column in columns if column not in (fieldnames or [])]
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")


def format_evaluation_summary(result: EvaluationResult) -> str:
    glossary = result.glossary
    bleu = result.bleu
    return "\n".join(
        [
            "Evaluation summary",
            f"input={result.input_path}",
            f"rows={result.row_count}",
            f"bleu={bleu.score:.6f}",
            f"bleu_tokenization={bleu.tokenization}",
            f"bleu_brevity_penalty={bleu.brevity_penalty:.6f}",
            f"glossary_preservation_rate={glossary.preservation_rate:.6f}",
            f"glossary_terms={glossary.total_terms}",
            f"glossary_terms_matched={glossary.matched_terms}",
            f"rows_with_glossary_terms={glossary.rows_with_terms}",
            f"rows_all_terms_matched={glossary.rows_all_matched}",
            f"rows_partially_matched={glossary.rows_partially_matched}",
            f"rows_not_matched={glossary.rows_not_matched}",
            f"rows_without_glossary_terms={glossary.rows_without_terms}",
        ]
    )


def write_evaluation_reports(result: EvaluationResult, report_dir: str | Path) -> None:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with (output_dir / "evaluation_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["metric", "value"])
        writer.writeheader()
        for metric, value in summary_rows(result):
            writer.writerow({"metric": metric, "value": value})

    with (output_dir / "glossary_preservation_rows.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "row_number",
                "status",
                "term_count",
                "matched_count",
                "missing_terms",
                "source",
                "candidate",
            ],
        )
        writer.writeheader()
        for row in result.glossary.row_results:
            writer.writerow(
                {
                    "row_number": row.row_number,
                    "status": row.status,
                    "term_count": row.term_count,
                    "matched_count": row.matched_count,
                    "missing_terms": ";".join(row.missing_terms),
                    "source": row.source,
                    "candidate": row.candidate,
                }
            )


def summary_rows(result: EvaluationResult) -> list[tuple[str, str]]:
    glossary = result.glossary
    bleu = result.bleu
    return [
        ("input", str(result.input_path)),
        ("rows", str(result.row_count)),
        ("bleu", f"{bleu.score:.6f}"),
        ("bleu_tokenization", bleu.tokenization),
        ("bleu_reference_length", str(bleu.reference_length)),
        ("bleu_candidate_length", str(bleu.candidate_length)),
        ("bleu_brevity_penalty", f"{bleu.brevity_penalty:.6f}"),
        ("glossary_preservation_rate", f"{glossary.preservation_rate:.6f}"),
        ("glossary_terms", str(glossary.total_terms)),
        ("glossary_terms_matched", str(glossary.matched_terms)),
        ("rows_with_glossary_terms", str(glossary.rows_with_terms)),
        ("rows_all_terms_matched", str(glossary.rows_all_matched)),
        ("rows_partially_matched", str(glossary.rows_partially_matched)),
        ("rows_not_matched", str(glossary.rows_not_matched)),
        ("rows_without_glossary_terms", str(glossary.rows_without_terms)),
    ]
