"""Regression tests for publish_model.py (ADR-0037 contract)."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location(
    "publish_model", _SCRIPTS_DIR / "publish_model.py"
)
assert _spec is not None and _spec.loader is not None
_publish_model = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_publish_model)  # type: ignore[arg-type]

INFERENCE_PATTERNS = _publish_model.INFERENCE_PATTERNS
_build_model_card = _publish_model._build_model_card

_REQUIRED_FILES = {
    "config.json",
    "generation_config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
}

_MINIMAL_MANIFEST = {
    "data": {"segments_sha256": "abc123", "split_seed": 42},
    "model": {"name": "facebook/nllb-200-distilled-600M"},
    "training": {"best_metric_value": 0.6375},
}


class InferencePatternsContractTest(unittest.TestCase):
    """INFERENCE_PATTERNS must contain exactly the ADR-0037 required files."""

    def test_contains_all_required_files(self) -> None:
        missing = _REQUIRED_FILES - set(INFERENCE_PATTERNS)
        self.assertFalse(
            missing,
            f"INFERENCE_PATTERNS is missing ADR-0037 required files: {missing}",
        )

    def test_no_training_state_files(self) -> None:
        forbidden = {"optimizer.pt", "scheduler.pt", "trainer_state.json", "training_args.bin"}
        present = forbidden & set(INFERENCE_PATTERNS)
        self.assertFalse(
            present,
            f"INFERENCE_PATTERNS must not publish training-state files (ADR-0037): {present}",
        )


class BuildModelCardTest(unittest.TestCase):
    """_build_model_card must embed required provenance fields."""

    def setUp(self) -> None:
        self.card = _build_model_card(_MINIMAL_MANIFEST, "SimpleJerry/longtu-nllb-zh2ko", "earlystop-v1-ckpt48000")

    def test_contains_repo_id(self) -> None:
        self.assertIn("SimpleJerry/longtu-nllb-zh2ko", self.card)

    def test_contains_tag(self) -> None:
        self.assertIn("earlystop-v1-ckpt48000", self.card)

    def test_contains_corpus_sha(self) -> None:
        self.assertIn("abc123", self.card)

    def test_contains_license_header(self) -> None:
        self.assertIn("cc-by-nc-4.0", self.card)

    def test_contains_best_metric(self) -> None:
        self.assertIn("0.6375", self.card)


if __name__ == "__main__":
    unittest.main()
