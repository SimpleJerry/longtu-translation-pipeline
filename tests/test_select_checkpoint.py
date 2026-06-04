"""Tests for scripts/select_checkpoint.py (ADR-0041, ADR-0014).

All tests use dry-run mode or fixture data — no GPU required.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "select_checkpoint", ROOT / "scripts" / "select_checkpoint.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_run_manifest(run_dir: Path, *, validation_split: str | None = None) -> None:
    manifest = {
        "run_name": "test-run",
        "data": {
            "segments_sha256": "abc123",
            "split_seed": 42,
            "validation_split_path": validation_split or "splits/validation.csv",
            "test_split_path": "splits/test.csv",
        },
    }
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


class CompositeMetricTest(unittest.TestCase):
    """Unit tests for _composite_metric (ADR-0031/ADR-0041)."""

    def test_equal_weights(self) -> None:
        mod = _load_script()
        result = mod._composite_metric(bleu=0.4, preservation_nospace=0.6)
        self.assertAlmostEqual(result, 0.5)

    def test_perfect_scores(self) -> None:
        mod = _load_script()
        result = mod._composite_metric(bleu=1.0, preservation_nospace=1.0)
        self.assertAlmostEqual(result, 1.0)

    def test_zero_scores(self) -> None:
        mod = _load_script()
        result = mod._composite_metric(bleu=0.0, preservation_nospace=0.0)
        self.assertAlmostEqual(result, 0.0)

    def test_bleu_dominated(self) -> None:
        mod = _load_script()
        result = mod._composite_metric(bleu=0.8, preservation_nospace=0.0)
        self.assertAlmostEqual(result, 0.4)


class FindCheckpointsTest(unittest.TestCase):
    """Unit tests for _find_checkpoints."""

    def test_finds_numeric_checkpoint_dirs(self) -> None:
        mod = _load_script()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "checkpoint-1000").mkdir()
            (run_dir / "checkpoint-2000").mkdir()
            (run_dir / "not-a-checkpoint").mkdir()
            (run_dir / "checkpoint-abc").mkdir()

            found = mod._find_checkpoints(run_dir)
            names = [p.name for p in found]

        self.assertEqual(names, ["checkpoint-1000", "checkpoint-2000"])

    def test_empty_dir_returns_empty(self) -> None:
        mod = _load_script()
        with tempfile.TemporaryDirectory() as tmp:
            result = mod._find_checkpoints(Path(tmp))
        self.assertEqual(result, [])

    def test_nonexistent_dir_returns_empty(self) -> None:
        mod = _load_script()
        result = mod._find_checkpoints(Path("/nonexistent/path/xyz"))
        self.assertEqual(result, [])


class WriteManifestTest(unittest.TestCase):
    """Unit tests for _write_manifest."""

    def test_manifest_written_correctly(self) -> None:
        mod = _load_script()
        winner = {
            "checkpoint": "/run/checkpoint-48000",
            "bleu": 0.325,
            "preservation_nospace": 0.954,
            "composite": 0.6395,
        }
        scores = [
            winner,
            {"checkpoint": "/run/checkpoint-45000", "bleu": 0.310,
             "preservation_nospace": 0.940, "composite": 0.625},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            path = mod._write_manifest(run_dir, scores, winner)
            manifest = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(path.name, "checkpoint_selection_manifest.json")
        self.assertEqual(manifest["selected_checkpoint"], "/run/checkpoint-48000")
        self.assertAlmostEqual(manifest["selected_scores"]["bleu"], 0.325)
        self.assertAlmostEqual(manifest["selected_scores"]["composite"], 0.6395)
        self.assertEqual(len(manifest["all_checkpoints"]), 2)
        self.assertEqual(manifest["adr"], "ADR-0041")
        self.assertIn("generated_at", manifest)


class DryRunTest(unittest.TestCase):
    """Integration test: dry-run discovers checkpoints, writes nothing."""

    def _run_script(self, argv: list[str]) -> "subprocess.CompletedProcess[str]":
        import subprocess
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "select_checkpoint.py")] + argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_dry_run_exits_zero_with_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "checkpoint-48000").mkdir()
            _write_run_manifest(run_dir)

            result = self._run_script(["--run-dir", str(run_dir), "--dry-run"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("DRY-RUN", result.stdout)
        self.assertIn("checkpoint-48000", result.stdout)

    def test_dry_run_exits_one_when_no_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _write_run_manifest(run_dir)

            result = self._run_script(["--run-dir", str(run_dir), "--dry-run"])
        self.assertNotEqual(result.returncode, 0)

    def test_missing_run_dir_exits_nonzero(self) -> None:
        result = self._run_script(["--run-dir", "/nonexistent/path/xyz", "--dry-run"])
        self.assertNotEqual(result.returncode, 0)

    def test_missing_manifest_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "checkpoint-1000").mkdir()
            # No run_manifest.json written
            result = self._run_script(["--run-dir", str(run_dir), "--dry-run"])
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
