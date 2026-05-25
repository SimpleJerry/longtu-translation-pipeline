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
        self.assertEqual(config.split.train_ratio, 0.8)
        self.assertEqual(config.split.validation_ratio, 0.1)
        self.assertEqual(config.split.test_ratio, 0.1)
        self.assertTrue(config.tokenization.terminology_markers)
        self.assertIsNone(config.training.max_steps)

    def test_full_10k_training_config_loads_profile_parameters(self) -> None:
        config = load_training_config(ROOT / "configs" / "training" / "full_10k.json", base_dir=ROOT)

        self.assertEqual(config.training.max_steps, 10000)
        self.assertEqual(config.training.save_steps, 1000)
        self.assertEqual(config.training.eval_steps, 5000)
        self.assertEqual(config.training.save_total_limit, 6)
        self.assertEqual(config.training.logging_steps, 100)
        self.assertEqual(config.training.gradient_accumulation_steps, 1)
        self.assertEqual(config.training.learning_rate, 0.00002)
        self.assertEqual(config.training.warmup_ratio, 0.03)
        self.assertEqual(config.training.weight_decay, 0.01)
        self.assertEqual(config.training.max_grad_norm, 1.0)
        self.assertEqual(config.split.train_ratio, 0.8)
        self.assertEqual(config.split.validation_ratio, 0.1)
        self.assertEqual(config.split.test_ratio, 0.1)
        self.assertEqual(config.data.segments_path, ROOT / "data" / "segments.csv")

    def test_default_inference_config_loads(self) -> None:
        config = load_inference_config(ROOT / "configs" / "inference" / "default.json")

        self.assertEqual(config.input.text_column, "zh-CN")
        self.assertEqual(config.input.reference_column, "ko")
        self.assertEqual(config.language.target_code, "kor_Hang")
        self.assertEqual(config.model.tokenizer_name, "facebook/nllb-200-distilled-600M")
        self.assertTrue(config.glossary.source_terminology_markers)
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
                    "split": {
                        "train_ratio": 0.8,
                        "validation_ratio": 0.1,
                        "test_ratio": 0.1,
                        "seed": 42,
                    },
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
                        "reference_column": "ko",
                        "id_column": "segment_id",
                    },
                    "language": {"source_code": "zho_Hans", "target_code": "kor_Hang"},
                    "model": {
                        "path": "fine-tuned-models/test",
                        "tokenizer_name": "facebook/nllb-200-distilled-600M",
                    },
                    "glossary": {
                        "path": "data/glossary.csv",
                        "source_terminology_markers": True,
                    },
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
        self.assertEqual(config.glossary.path, ROOT / "data" / "glossary.csv")
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
