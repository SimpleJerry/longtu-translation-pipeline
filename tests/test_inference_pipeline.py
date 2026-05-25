from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.config import load_inference_config  # noqa: E402
from longtu_translation_pipeline.inference import (  # noqa: E402
    GeneratedTranslationRow,
    InferenceGenerationResult,
    build_inference_dry_run,
    format_inference_generation,
    write_generation_csv,
)


class InferencePipelineTest(unittest.TestCase):
    def test_dry_run_reads_inputs_and_plans_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "segments.csv"
            output_path = tmp_path / "translation_result.csv"
            config_path = tmp_path / "inference.json"

            with input_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["segment_id", "zh-CN", "ko"])
                writer.writeheader()
                writer.writerow({"segment_id": "1", "zh-CN": "勇士竞技", "ko": "용맹의 결투장"})
                writer.writerow({"segment_id": "2", "zh-CN": "挑战次数:{0}", "ko": "도전 횟수: {0}"})

            config_path.write_text(
                json.dumps(
                    {
                        "input": {
                        "path": str(input_path),
                        "text_column": "zh-CN",
                        "reference_column": "ko",
                        "id_column": "segment_id",
                    },
                    "language": {"source_code": "zho_Hans", "target_code": "kor_Hang"},
                    "model": {
                        "path": "fine-tuned-models/test",
                        "tokenizer_name": "facebook/nllb-200-distilled-600M",
                    },
                        "output": {"path": str(output_path), "strip_glossary_markers": True},
                        "generation": {"batch_size": 4, "max_length": 64},
                        "dry_run": {"preview_rows": 1},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            plan = build_inference_dry_run(load_inference_config(config_path))

        self.assertEqual(plan.total_rows, 2)
        self.assertEqual(plan.output_path, output_path)
        self.assertEqual(plan.batch_size, 4)
        self.assertEqual(plan.preview_records[0].record_id, "1")
        self.assertEqual(plan.preview_records[0].text, "勇士竞技")
        self.assertEqual(plan.preview_records[0].reference, "용맹의 결투장")

    def test_empty_inference_csv_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "segments.csv"
            config_path = tmp_path / "inference.json"

            with input_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["segment_id", "zh-CN", "ko"])
                writer.writeheader()

            config_path.write_text(
                json.dumps(
                    {
                        "input": {
                        "path": str(input_path),
                        "text_column": "zh-CN",
                        "reference_column": "ko",
                        "id_column": "segment_id",
                    },
                    "language": {"source_code": "zho_Hans", "target_code": "kor_Hang"},
                    "model": {
                        "path": "fine-tuned-models/test",
                        "tokenizer_name": "facebook/nllb-200-distilled-600M",
                    },
                        "output": {"path": "translation_result.csv", "strip_glossary_markers": True},
                        "generation": {"batch_size": 4, "max_length": 64},
                        "dry_run": {"preview_rows": 1},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "No inference records found"):
                build_inference_dry_run(load_inference_config(config_path))

    def test_generation_csv_schema_matches_evaluation_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "generated.csv"
            write_generation_csv(
                output_path,
                [
                    GeneratedTranslationRow(
                        record_id="1",
                        source="挑战BOSS",
                        reference="보스 도전",
                        candidate="보스 도전",
                    )
                ],
            )

            with output_path.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

        self.assertEqual(reader.fieldnames, ["segment_id", "source", "references", "candidates"])
        self.assertEqual(rows[0]["segment_id"], "1")
        self.assertEqual(rows[0]["source"], "挑战BOSS")
        self.assertEqual(rows[0]["references"], "보스 도전")
        self.assertEqual(rows[0]["candidates"], "보스 도전")

    def test_generation_result_format_reports_model_and_schema(self) -> None:
        result = InferenceGenerationResult(
            config_path=Path("inference.json"),
            input_path=Path("segments.csv"),
            output_path=Path("data/review/inference/generated_samples.csv"),
            model_path=Path("fine-tuned-models/checkpoint-4"),
            tokenizer_name="facebook/nllb-200-distilled-600M",
            source_code="zho_Hans",
            target_code="kor_Hang",
            forced_bos_token_id=256098,
            special_tokens_added=2,
            tokenizer_vocab_size=256206,
            embedding_size_before=256204,
            embedding_size_after=256206,
            device="cuda",
            cuda_device_name="NVIDIA Test GPU",
            cuda_memory_summary="allocated_gb=1.00;reserved_gb=2.00",
            batch_size=8,
            max_length=400,
            strip_glossary_markers=True,
            input_rows=1,
            generated_rows=1,
            output_columns=["segment_id", "source", "references", "candidates"],
            preview_rows=[
                GeneratedTranslationRow(
                    record_id="1",
                    source="挑战BOSS",
                    reference="보스 도전",
                    candidate="보스 도전",
                )
            ],
        )

        formatted = format_inference_generation(result)

        self.assertIn("Inference generation result", formatted)
        self.assertIn("model_path=fine-tuned-models", formatted)
        self.assertIn("tokenizer_name=facebook/nllb-200-distilled-600M", formatted)
        self.assertIn("language_pair=zho_Hans->kor_Hang", formatted)
        self.assertIn("forced_bos_token_id=256098", formatted)
        self.assertIn("output_columns=segment_id,source,references,candidates", formatted)


if __name__ == "__main__":
    unittest.main()
