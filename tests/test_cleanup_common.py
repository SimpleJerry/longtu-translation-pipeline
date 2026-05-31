from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.cleanup.common import (  # noqa: E402
    compile_regexes,
    ensure_csv_columns,
    read_json_config,
    read_term_file,
    sha256,
)


class Sha256Test(unittest.TestCase):
    def test_known_content_produces_known_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "file.txt"
            p.write_bytes(b"hello")
            expected = hashlib.sha256(b"hello").hexdigest().upper()
            self.assertEqual(sha256(p), expected)

    def test_returns_uppercase_hex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "file.txt"
            p.write_bytes(b"test content")
            result = sha256(p)
            self.assertEqual(result, result.upper())
            self.assertTrue(all(c in "0123456789ABCDEF" for c in result))


class ReadTermFileTest(unittest.TestCase):
    def test_happy_path_bom_and_trailing_newline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "terms.txt"
            # UTF-8 BOM + three terms + trailing newline
            p.write_bytes("﻿Alpha\nBeta\nGamma\n".encode("utf-8"))
            terms = read_term_file(p, "test")
            self.assertEqual(terms, ["Alpha", "Beta", "Gamma"])

    def test_comments_and_blank_lines_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "terms.txt"
            p.write_text("# comment\n\nAlpha\n# another\nBeta\n", encoding="utf-8")
            terms = read_term_file(p, "test")
            self.assertEqual(terms, ["Alpha", "Beta"])

    def test_duplicate_raises_runtime_error_with_line_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "terms.txt"
            p.write_text("Alpha\nBeta\nAlpha\n", encoding="utf-8")
            with self.assertRaises(RuntimeError) as ctx:
                read_term_file(p, "test")
            self.assertIn("3", str(ctx.exception))

    def test_empty_file_after_stripping_raises_runtime_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "terms.txt"
            p.write_text("# only comments\n\n", encoding="utf-8")
            with self.assertRaises(RuntimeError) as ctx:
                read_term_file(p, "test")
            self.assertIn("empty", str(ctx.exception).lower())

    def test_missing_file_raises_runtime_error_with_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "nonexistent.txt"
            with self.assertRaises(RuntimeError) as ctx:
                read_term_file(p, "test")
            self.assertIn(str(p), str(ctx.exception))


class ReadJsonConfigTest(unittest.TestCase):
    def test_happy_path_returns_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "config.json"
            p.write_text(json.dumps({"key": "value"}), encoding="utf-8")
            result = read_json_config(p)
            self.assertIsInstance(result, dict)
            self.assertEqual(result["key"], "value")

    def test_top_level_array_raises_runtime_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "config.json"
            p.write_text(json.dumps(["a", "b"]), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                read_json_config(p)

    def test_missing_file_raises_runtime_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "missing.json"
            with self.assertRaises(RuntimeError) as ctx:
                read_json_config(p)
            self.assertIn(str(p), str(ctx.exception))


class CompileRegexesTest(unittest.TestCase):
    def test_happy_path_returns_patterns(self) -> None:
        import re
        rules = {"regex": {"digits": r"\d+", "word": r"\w+"}}
        result = compile_regexes(rules)
        self.assertIsInstance(result["digits"], re.Pattern)
        self.assertIsInstance(result["word"], re.Pattern)

    def test_missing_regex_key_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            compile_regexes({"other": {}})

    def test_empty_regex_dict_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            compile_regexes({"regex": {}})

    def test_non_dict_regex_value_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            compile_regexes({"regex": ["not", "a", "dict"]})


class EnsureCsvColumnsTest(unittest.TestCase):
    def _make_reader(self, fieldnames: list[str]) -> csv.DictReader:
        header = ",".join(fieldnames)
        return csv.DictReader(io.StringIO(header + "\n"))

    def test_happy_path_no_exception(self) -> None:
        reader = self._make_reader(["col_a", "col_b", "col_c"])
        ensure_csv_columns(reader, ["col_a", "col_b"], Path("file.csv"))

    def test_missing_column_raises_with_column_name_and_path(self) -> None:
        reader = self._make_reader(["col_a"])
        with self.assertRaises(RuntimeError) as ctx:
            ensure_csv_columns(reader, ["col_a", "col_missing"], Path("data/file.csv"))
        msg = str(ctx.exception)
        self.assertIn("col_missing", msg)
        self.assertIn("file.csv", msg)


if __name__ == "__main__":
    unittest.main()
