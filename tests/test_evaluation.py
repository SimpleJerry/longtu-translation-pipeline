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
    compute_chrf,
    compute_corpus_bleu,
    compute_glossary_preservation,
    evaluate_translation,
    write_evaluation_reports,
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

    def test_bleu_allows_empty_candidates_as_zero_length_outputs(self) -> None:
        result = compute_corpus_bleu(["보스 도전"], [""], tokenization="whitespace")

        self.assertEqual(result.candidate_length, 0)
        self.assertEqual(result.score, 0.0)

    def test_glossary_preservation_counts_row_statuses(self) -> None:
        rows = [
            TranslationRow(1, "101", "挑战BOSS", "보스 도전", "보스 도전"),
            TranslationRow(2, "102", "领取VIP卡", "VIP 카드 수령", "<start>VIP 카드<end> 수령"),
            TranslationRow(3, "103", "挑战BOSS和VIP卡", "보스와 VIP 카드", "보스 등장"),
            TranslationRow(4, "104", "挑战BOSS", "보스 도전", "도전"),
            TranslationRow(5, "105", "普通句子", "일반 문장", "일반 문장"),
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
        self.assertAlmostEqual(result.preservation_rate_exact, 0.6)

    def test_glossary_preservation_reports_nospace_matches_separately(self) -> None:
        rows = [
            TranslationRow(
                1,
                "201",
                "追加伤害提升",
                "추가피해 증가",
                "추가 피해 증가",
            )
        ]
        terms = [GlossaryTerm("追加伤害", "추가피해")]

        result = compute_glossary_preservation(rows, terms)
        row = result.row_results[0]

        self.assertEqual(result.matched_terms_exact, 0)
        self.assertEqual(result.matched_terms_nospace, 1)
        self.assertAlmostEqual(result.preservation_rate_exact, 0.0)
        self.assertAlmostEqual(result.preservation_rate_nospace, 1.0)
        self.assertEqual(row.status_exact, "not_matched")
        self.assertEqual(row.status_nospace, "all_matched")
        self.assertEqual(row.missing_terms_exact, ["추가피해"])
        self.assertEqual(row.missing_terms_nospace, [])

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
        self.assertEqual(result.rows[0].segment_id, "")

    def test_evaluation_reports_write_sample_review_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "evaluation.json"
            input_path = tmp_path / "generated.csv"
            report_dir = tmp_path / "report"
            write_csv(
                input_path,
                ["segment_id", "source", "references", "candidates"],
                [
                    {
                        "segment_id": "10",
                        "source": "挑战BOSS",
                        "references": "보스 도전",
                        "candidates": "도전",
                    },
                    {
                        "segment_id": "11",
                        "source": "普通句子",
                        "references": "일반 문장",
                        "candidates": "일반 문장",
                    },
                ],
            )
            write_csv(
                glossary_path,
                ["term_id", "zh-CN", "ko"],
                [{"term_id": "1", "zh-CN": "BOSS", "ko": "보스"}],
            )
            write_config(config_path, input_path, glossary_path)

            result = evaluate_translation(load_evaluation_config(config_path))
            write_evaluation_reports(
                result,
                report_dir,
                checkpoint_path=Path("fine-tuned-models/checkpoint-4"),
                config_path=config_path,
                sample_review_rows=2,
            )

            summary_rows = read_csv(report_dir / "evaluation_summary.csv")
            review_rows = read_csv(report_dir / "sample_review.csv")
            manifest = json.loads((report_dir / "report_manifest.json").read_text(encoding="utf-8"))
            glossary_rows_exists = (report_dir / "glossary_preservation_rows.csv").exists()

        self.assertTrue(glossary_rows_exists)
        self.assertEqual(summary_rows[0]["metric"], "input")
        self.assertEqual(review_rows[0]["segment_id"], "10")
        self.assertEqual(review_rows[0]["glossary_status"], "not_matched")
        self.assertIn("glossary_status_nospace", review_rows[0])
        self.assertIn("glossary_preservation_rate_nospace", {row["metric"] for row in summary_rows})
        self.assertEqual(Path(manifest["checkpoint_path"]), Path("fine-tuned-models/checkpoint-4"))
        self.assertEqual(manifest["row_count"], 2)
        self.assertEqual(manifest["generation_csv"], str(input_path))
        self.assertIn("glossary_preservation_rate_nospace", manifest)

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

    def test_chrf_is_one_for_exact_match(self) -> None:
        result = compute_chrf(["abc def ghi"], ["abc def ghi"])

        self.assertAlmostEqual(result.score, 1.0)

    def test_chrf_is_zero_for_completely_different_strings(self) -> None:
        # "abc" has no character n-grams in common with "xyz"
        result = compute_chrf(["aaa"], ["zzz"])

        self.assertAlmostEqual(result.score, 0.0)

    def test_chrf_partial_match_matches_reference_value(self) -> None:
        # ref="abc def" (chars a,b,c,d,e,f), hyp="abc" (chars a,b,c)
        # n=1: P=1.0 R=0.5 | n=2: P=1.0 R=0.4 | n=3: P=1.0 R=0.25
        # n=4,5,6: hyp has no n-grams, P=0 R=0 (ref has n-grams so valid orders)
        # mean_P=0.5, mean_R=(0.5+0.4+0.25)/6≈0.1917, beta=2
        # verified against manual formula
        result = compute_chrf(["abc def"], ["abc"])

        self.assertGreater(result.score, 0.0)
        self.assertLess(result.score, 1.0)
        self.assertAlmostEqual(result.score, 0.21863, places=4)

    def test_chrf_partial_is_between_zero_and_exact(self) -> None:
        exact = compute_chrf(["abc def"], ["abc def"])
        partial = compute_chrf(["abc def"], ["abc"])
        empty = compute_chrf(["abc def"], [""])

        self.assertLess(empty.score, partial.score)
        self.assertLess(partial.score, exact.score)

    def test_chrf_result_carries_params(self) -> None:
        result = compute_chrf(["abc"], ["abc"], max_n=3, beta=1.0)

        self.assertEqual(result.max_n, 3)
        self.assertAlmostEqual(result.beta, 1.0)

    def test_chrf_appears_in_evaluation_summary_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "generated.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "evaluation.json"
            report_dir = tmp_path / "report"
            write_csv(
                input_path,
                ["segment_id", "source", "references", "candidates"],
                [{"segment_id": "1", "source": "abc", "references": "def ghi", "candidates": "def"}],
            )
            write_csv(glossary_path, ["term_id", "zh-CN", "ko"], [])
            write_config(config_path, input_path, glossary_path)

            result = evaluate_translation(load_evaluation_config(config_path))
            write_evaluation_reports(result, report_dir)

            summary = read_csv(report_dir / "evaluation_summary.csv")
            metrics = {row["metric"] for row in summary}

        self.assertIn("chrf", metrics)
        chrf_val = next(row["value"] for row in summary if row["metric"] == "chrf")
        self.assertGreater(float(chrf_val), 0.0)

    def test_empty_candidate_is_reported_not_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "generated.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "evaluation.json"
            report_dir = tmp_path / "report"

            write_csv(
                input_path,
                ["segment_id", "source", "references", "candidates"],
                [{"segment_id": "1", "source": "挑战BOSS", "references": "보스 도전", "candidates": ""}],
            )
            write_csv(
                glossary_path,
                ["term_id", "zh-CN", "ko"],
                [{"term_id": "1", "zh-CN": "BOSS", "ko": "보스"}],
            )
            write_config(config_path, input_path, glossary_path)

            result = evaluate_translation(load_evaluation_config(config_path))
            write_evaluation_reports(result, report_dir, sample_review_rows=1)
            summary_rows = read_csv(report_dir / "evaluation_summary.csv")
            review_rows = read_csv(report_dir / "sample_review.csv")

        self.assertEqual(result.empty_candidate_rows, 1)
        self.assertEqual(result.bleu.score, 0.0)
        self.assertEqual(result.glossary.rows_not_matched, 1)
        self.assertIn({"metric": "empty_candidate_rows", "value": "1"}, summary_rows)
        self.assertEqual(review_rows[0]["segment_id"], "1")
        self.assertEqual(review_rows[0]["candidates"], "")


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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    unittest.main()
