from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.config import (  # noqa: E402
    load_inference_config,
    load_training_config,
)


class ConfigTest(unittest.TestCase):
    def test_default_training_config_loads(self) -> None:
        config = load_training_config(ROOT / "configs" / "training" / "default.json")

        self.assertEqual(config.data.source_column, "zh-CN")
        self.assertEqual(config.data.target_column, "ko")
        self.assertEqual(config.language.source_code, "zho_Hans")
        self.assertEqual(config.language.target_code, "kor_Hang")
        self.assertTrue(config.tokenization.terminology_markers)

    def test_default_inference_config_loads(self) -> None:
        config = load_inference_config(ROOT / "configs" / "inference" / "default.json")

        self.assertEqual(config.input.text_column, "zh-CN")
        self.assertEqual(config.language.target_code, "kor_Hang")
        self.assertTrue(config.output.strip_glossary_markers)

    def test_training_paths_can_resolve_against_base_dir(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "data": {
                        "segments_path": "data/segments.csv",
                        "glossary_path": "data/glossary.csv",
                        "source_column": "zh-CN",
                        "target_column": "ko",
                        "id_column": "segment_id",
                    },
                    "language": {"source_code": "zho_Hans", "target_code": "kor_Hang"},
                    "model": {
                        "base_model": "test-model",
                        "output_dir": "fine-tuned-models/test",
                    },
                    "split": {"validation_ratio": 0.2, "seed": 42},
                    "tokenization": {
                        "max_length": 32,
                        "padding": "max_length",
                        "truncation": True,
                        "terminology_markers": True,
                    },
                    "training": {
                        "num_train_epochs": 1,
                        "per_device_train_batch_size": 1,
                        "per_device_eval_batch_size": 1,
                    },
                    "dry_run": {"preview_rows": 1},
                },
                f,
            )
            path = Path(f.name)

        try:
            config = load_training_config(path, base_dir=ROOT)
        finally:
            path.unlink()

        self.assertEqual(config.data.segments_path, ROOT / "data" / "segments.csv")
        self.assertEqual(config.data.glossary_path, ROOT / "data" / "glossary.csv")
        self.assertEqual(config.model.output_dir, ROOT / "fine-tuned-models" / "test")

    def test_inference_paths_can_resolve_against_base_dir(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "input": {
                        "path": "data/segments.csv",
                        "text_column": "zh-CN",
                        "id_column": "segment_id",
                    },
                    "language": {"source_code": "zho_Hans", "target_code": "kor_Hang"},
                    "model": {"path": "fine-tuned-models/test"},
                    "output": {"path": "translation_result.csv", "strip_glossary_markers": True},
                    "generation": {"batch_size": 4, "max_length": 64},
                    "dry_run": {"preview_rows": 1},
                },
                f,
            )
            path = Path(f.name)

        try:
            config = load_inference_config(path, base_dir=ROOT)
        finally:
            path.unlink()

        self.assertEqual(config.input.path, ROOT / "data" / "segments.csv")
        self.assertEqual(config.model.path, ROOT / "fine-tuned-models" / "test")
        self.assertEqual(config.output.path, ROOT / "translation_result.csv")

    def test_missing_required_training_section_is_reported(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
            json.dump({"data": {}}, f)
            path = Path(f.name)

        try:
            with self.assertRaisesRegex(ValueError, "language"):
                load_training_config(path)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
