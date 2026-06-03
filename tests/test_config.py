from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

from longtu_translation_pipeline.config import (
    load_inference_config,
    load_serving_config,
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

    def test_step10k_training_config_loads_profile_parameters(self) -> None:
        config = load_training_config(ROOT / "configs" / "training" / "step10k.json", base_dir=ROOT)

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

    def test_inference_config_default_from_hub_is_false(self) -> None:
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
                    "glossary": {"path": "data/glossary.csv", "source_terminology_markers": True},
                    "output": {"path": "out.csv", "strip_glossary_markers": True},
                    "generation": {"batch_size": 4, "max_length": 64},
                    "dry_run": {"preview_rows": 0},
                },
                f,
            )
            path = Path(f.name)

        try:
            config = load_inference_config(path, base_dir=ROOT)
        finally:
            path.unlink()

        self.assertFalse(config.model.from_hub)
        self.assertIsNone(config.model.revision)
        self.assertIsInstance(config.model.path, Path)

    def _write_serving_config(self, tmp_dir: str, *, model_extra: dict | None = None) -> Path:
        model_block: dict = {
            "path": "fine-tuned-models/test",
            "tokenizer_name": "facebook/nllb-200-distilled-600M",
        }
        if model_extra:
            model_block.update(model_extra)
        config = {
            "model": model_block,
            "language": {"source_code": "zho_Hans", "target_code": "kor_Hang"},
            "glossary": {"path": "data/glossary.csv", "source_terminology_markers": True},
            "output": {"strip_glossary_markers": True},
            "generation": {"batch_size": 8, "max_length": 400, "num_beams": 4,
                           "length_penalty": 1.0, "no_repeat_ngram_size": 0},
            "serving": {"host": "127.0.0.1", "port": 8000,
                        "max_items_per_request": 32, "max_concurrency": 1},
        }
        p = Path(tmp_dir) / "serving.json"
        p.write_text(json.dumps(config), encoding="utf-8")
        return p

    def test_serving_config_from_hub_without_revision_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self._write_serving_config(
                tmp, model_extra={"from_hub": True}
            )
            with self.assertRaises(ValueError):
                load_serving_config(config_path)

    def test_serving_config_from_hub_with_revision_keeps_repo_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self._write_serving_config(
                tmp,
                model_extra={
                    "path": "SimpleJerry/longtu-nllb-zh2ko",
                    "tokenizer_name": "SimpleJerry/longtu-nllb-zh2ko",
                    "from_hub": True,
                    "revision": "earlystop-v1-ckpt48000",
                },
            )
            config = load_serving_config(config_path)

        self.assertTrue(config.inference.model.from_hub)
        self.assertEqual(config.inference.model.revision, "earlystop-v1-ckpt48000")
        self.assertEqual(config.inference.model.path, "SimpleJerry/longtu-nllb-zh2ko")

    def test_serving_config_without_from_hub_resolves_local_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self._write_serving_config(tmp)
            config = load_serving_config(config_path, base_dir=ROOT)

        self.assertFalse(config.inference.model.from_hub)
        self.assertIsNone(config.inference.model.revision)
        self.assertIsInstance(config.inference.model.path, Path)
        self.assertEqual(config.inference.model.path, ROOT / "fine-tuned-models" / "test")

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
