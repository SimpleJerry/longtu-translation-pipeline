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
from longtu_translation_pipeline.inference import build_inference_dry_run  # noqa: E402


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
                            "id_column": "segment_id",
                        },
                        "language": {"source_code": "zho_Hans", "target_code": "kor_Hang"},
                        "model": {"path": "fine-tuned-models/test"},
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
                            "id_column": "segment_id",
                        },
                        "language": {"source_code": "zho_Hans", "target_code": "kor_Hang"},
                        "model": {"path": "fine-tuned-models/test"},
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


if __name__ == "__main__":
    unittest.main()
