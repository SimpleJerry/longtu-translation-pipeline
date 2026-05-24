from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.config import load_evaluation_config  # noqa: E402
from longtu_translation_pipeline.evaluation import (  # noqa: E402
    GlossaryTerm,
    TranslationRow,
    compute_corpus_bleu,
    compute_glossary_preservation,
    evaluate_translation,
)


class EvaluationTest(unittest.TestCase):
    def test_bleu_is_one_for_exact_match(self) -> None:
        result = compute_corpus_bleu(["보스 도전"], ["보스 도전"], tokenization="whitespace")

        self.assertAlmostEqual(result.score, 1.0)

    def test_bleu_drops_for_partial_mismatch(self) -> None:
        exact = compute_corpus_bleu(["보스 도전"], ["보스 도전"], tokenization="whitespace")
        partial = compute_corpus_bleu(["보스 도전"], ["도전"], tokenization="whitespace")

        self.assertLess(partial.score, exact.score)

    def test_char_tokenization_runs(self) -> None:
        result = compute_corpus_bleu(["보스도전"], ["보스도전"], tokenization="char")

        self.assertAlmostEqual(result.score, 1.0)

    def test_glossary_preservation_counts_row_statuses(self) -> None:
        rows = [
            TranslationRow("挑战BOSS", "보스 도전", "보스 도전"),
            TranslationRow("领取VIP卡", "VIP 카드 수령", "<start>VIP 카드<end> 수령"),
            TranslationRow("挑战BOSS和VIP卡", "보스와 VIP 카드", "보스 등장"),
            TranslationRow("挑战BOSS", "보스 도전", "도전"),
            TranslationRow("普通句子", "일반 문장", "일반 문장"),
        ]
        terms = [GlossaryTerm("BOSS", "보스"), GlossaryTerm("VIP卡", "VIP 카드")]

        result = compute_glossary_preservation(rows, terms)

        self.assertEqual(result.total_terms, 5)
        self.assertEqual(result.matched_terms, 3)
        self.assertEqual(result.rows_all_matched, 2)
        self.assertEqual(result.rows_partially_matched, 1)
        self.assertEqual(result.rows_not_matched, 1)
        self.assertEqual(result.rows_without_terms, 1)
        self.assertAlmostEqual(result.preservation_rate, 0.6)

    def test_evaluate_translation_reads_config_and_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "evaluation.json"
            write_csv(
                glossary_path,
                ["term_id", "zh-CN", "ko"],
                [
                    {"term_id": "1", "zh-CN": "BOSS", "ko": "보스"},
                    {"term_id": "2", "zh-CN": "VIP卡", "ko": "VIP 카드"},
                    {"term_id": "3", "zh-CN": "副本", "ko": "던전"},
                ],
            )
            config_path.write_text(
                json.dumps(
                    {
                        "input": {
                            "path": str(ROOT / "tests" / "fixtures" / "evaluation_translation_result.csv"),
                            "source_column": "source",
                            "reference_column": "references",
                            "candidate_column": "candidates",
                        },
                        "glossary": {
                            "path": str(glossary_path),
                            "source_column": "zh-CN",
                            "target_column": "ko",
                        },
                        "bleu": {"tokenization": "whitespace", "max_order": 4, "smooth_value": 0.1},
                        "output": {"report_dir": str(tmp_path / "review"), "write_reports": False},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = evaluate_translation(load_evaluation_config(config_path))

        self.assertEqual(result.row_count, 4)
        self.assertEqual(result.glossary.total_terms, 3)
        self.assertEqual(result.glossary.matched_terms, 2)

    def test_missing_translation_column_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "bad.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "evaluation.json"

            write_csv(input_path, ["source", "references"], [{"source": "挑战BOSS", "references": "보스 도전"}])
            write_csv(glossary_path, ["term_id", "zh-CN", "ko"], [])
            write_config(config_path, input_path, glossary_path)

            with self.assertRaisesRegex(ValueError, "missing required columns"):
                evaluate_translation(load_evaluation_config(config_path))

    def test_empty_translation_csv_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "empty.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "evaluation.json"

            write_csv(input_path, ["source", "references", "candidates"], [])
            write_csv(glossary_path, ["term_id", "zh-CN", "ko"], [])
            write_config(config_path, input_path, glossary_path)

            with self.assertRaisesRegex(ValueError, "No translation rows found"):
                evaluate_translation(load_evaluation_config(config_path))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_config(config_path: Path, input_path: Path, glossary_path: Path) -> None:
    config_path.write_text(
        json.dumps(
            {
                "input": {
                    "path": str(input_path),
                    "source_column": "source",
                    "reference_column": "references",
                    "candidate_column": "candidates",
                },
                "glossary": {
                    "path": str(glossary_path),
                    "source_column": "zh-CN",
                    "target_column": "ko",
                },
                "bleu": {"tokenization": "whitespace", "max_order": 4, "smooth_value": 0.1},
                "output": {"report_dir": str(config_path.parent / "review"), "write_reports": False},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
