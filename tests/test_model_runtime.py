"""Tests for model_runtime — lazy-import guard + pure-function unit tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


class LazyImportGuardTest(unittest.TestCase):
    def test_import_model_runtime_does_not_load_torch(self) -> None:
        """Importing model_runtime must not pull torch into sys.modules (ADR-0042 §2).

        Run in a subprocess so the check is isolated from whatever else pytest
        workers have already imported in the shared process.
        """
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import longtu_translation_pipeline.model_runtime; "
                    "import sys; "
                    "assert 'torch' not in sys.modules, "
                    "'model_runtime top-level import must not trigger torch loading'"
                ),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"subprocess check failed:\n{result.stderr}",
        )


class ListCheckpointPathsTest(unittest.TestCase):
    def test_empty_dir_returns_empty_list(self) -> None:
        from longtu_translation_pipeline.model_runtime import list_checkpoint_paths

        with tempfile.TemporaryDirectory() as tmp:
            result = list_checkpoint_paths(tmp)
            self.assertEqual(result, [])

    def test_nonexistent_dir_returns_empty_list(self) -> None:
        from longtu_translation_pipeline.model_runtime import list_checkpoint_paths

        result = list_checkpoint_paths("/nonexistent/path/that/does/not/exist")
        self.assertEqual(result, [])

    def test_returns_sorted_by_step(self) -> None:
        from longtu_translation_pipeline.model_runtime import list_checkpoint_paths

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for step in (10, 5, 20):
                (tmp_path / f"checkpoint-{step}").mkdir()
            result = list_checkpoint_paths(tmp_path)
            self.assertEqual([p.name for p in result], ["checkpoint-5", "checkpoint-10", "checkpoint-20"])

    def test_ignores_non_checkpoint_dirs(self) -> None:
        from longtu_translation_pipeline.model_runtime import list_checkpoint_paths

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "checkpoint-10").mkdir()
            (tmp_path / "logs").mkdir()
            (tmp_path / "checkpoint-bad").mkdir()
            result = list_checkpoint_paths(tmp_path)
            self.assertEqual([p.name for p in result], ["checkpoint-10"])


class FindLatestCheckpointTest(unittest.TestCase):
    def test_returns_none_when_no_checkpoints(self) -> None:
        from longtu_translation_pipeline.model_runtime import find_latest_checkpoint

        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(find_latest_checkpoint(tmp))

    def test_returns_highest_step(self) -> None:
        from longtu_translation_pipeline.model_runtime import find_latest_checkpoint

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for step in (5, 10, 3):
                (tmp_path / f"checkpoint-{step}").mkdir()
            result = find_latest_checkpoint(tmp_path)
            self.assertIsNotNone(result)
            self.assertEqual(result.name, "checkpoint-10")  # type: ignore[union-attr]


class ConfigureTokenizerLanguageCodesTest(unittest.TestCase):
    def _make_tokenizer(self) -> SimpleNamespace:
        tok = SimpleNamespace()
        tok.src_lang = None
        tok.tgt_lang = None
        return tok

    def test_sets_attributes_and_returns_assignments(self) -> None:
        from longtu_translation_pipeline.model_runtime import configure_tokenizer_language_codes

        tok = self._make_tokenizer()
        result = configure_tokenizer_language_codes(tok, "zh_CN", "ko_KR")
        self.assertEqual(tok.src_lang, "zh_CN")
        self.assertEqual(tok.tgt_lang, "ko_KR")
        self.assertIn("src_lang=zh_CN", result)
        self.assertIn("tgt_lang=ko_KR", result)

    def test_skips_missing_attributes_gracefully(self) -> None:
        from longtu_translation_pipeline.model_runtime import configure_tokenizer_language_codes

        class _FrozenTok:
            __slots__ = ()

        result = configure_tokenizer_language_codes(_FrozenTok(), "zh_CN", "ko_KR")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
