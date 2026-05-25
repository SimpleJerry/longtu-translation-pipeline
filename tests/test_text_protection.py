from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.text_protection import (  # noqa: E402
    GlossaryTerm,
    load_glossary_terms,
    mark_source_glossary_terms,
    protect_training_pair,
    strip_glossary_markers,
)


class TextProtectionTest(unittest.TestCase):
    def test_load_glossary_terms_sorts_by_source_length(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=["term_id", "zh-CN", "ko"])
            writer.writeheader()
            writer.writerow({"term_id": "1", "zh-CN": "神", "ko": "신"})
            writer.writerow({"term_id": "2", "zh-CN": "神秘宝箱", "ko": "신비한 보물상자"})
            path = Path(f.name)

        try:
            terms = load_glossary_terms(path)
        finally:
            path.unlink()

        self.assertEqual([term.zh_cn for term in terms], ["神秘宝箱", "神"])

    def test_glossary_terms_are_marked_on_source_and_target(self) -> None:
        result = protect_training_pair(
            "打开神秘宝箱",
            "신비한 보물상자 열기",
            [GlossaryTerm("神秘宝箱", "신비한 보물상자")],
        )

        self.assertEqual(result.source_text, "打开<start>神秘宝箱<end>")
        self.assertEqual(result.target_text, "<start>신비한 보물상자<end> 열기")
        self.assertEqual(result.metadata["glossary_terms_applied"], 1)

    def test_overlapping_terms_use_longest_first(self) -> None:
        result = protect_training_pair(
            "神秘宝箱",
            "신비한 보물상자",
            [GlossaryTerm("神秘宝箱", "신비한 보물상자"), GlossaryTerm("神", "신")],
        )

        self.assertIn("<start>神秘宝箱<end>", result.source_text)
        self.assertNotIn("<start>神<end>", result.source_text)

    def test_existing_glossary_markers_are_not_marked_again(self) -> None:
        result = protect_training_pair(
            "<start>神秘宝箱<end>",
            "<start>신비한 보물상자<end>",
            [GlossaryTerm("神秘宝箱", "신비한 보물상자")],
        )

        self.assertEqual(result.source_text.count("<start>"), 1)
        self.assertEqual(result.target_text.count("<start>"), 1)
        self.assertEqual(result.metadata["glossary_terms_applied"], 0)

    def test_machine_placeholders_are_kept_as_plain_text(self) -> None:
        result = protect_training_pair(
            "挑战次数:{0}/{1}",
            "도전 횟수: {0}/{1}",
            [],
        )

        self.assertEqual(result.source_text, "挑战次数:{0}/{1}")
        self.assertEqual(result.target_text, "도전 횟수: {0}/{1}")

    def test_source_only_marker_does_not_require_target_text(self) -> None:
        marked, count = mark_source_glossary_terms(
            "挑战BOSS和BOSS层",
            [GlossaryTerm("BOSS层", "BOSS층"), GlossaryTerm("BOSS", "보스")],
        )

        self.assertEqual(marked, "挑战<start>BOSS<end>和<start>BOSS层<end>")
        self.assertEqual(count, 2)

    def test_tags_are_not_replaced_with_code_tokens(self) -> None:
        result = protect_training_pair("<c=green>2%</c>", "<c=green>2%</c>", [])

        self.assertEqual(result.source_text, "<c=green>2%</c>")
        self.assertEqual(result.target_text, "<c=green>2%</c>")
        self.assertNotIn("<code_" + "id=", result.source_text + result.target_text)

    def test_strip_glossary_markers_keeps_visible_text(self) -> None:
        self.assertEqual(strip_glossary_markers("<start>神秘宝箱<end>"), "神秘宝箱")
        self.assertEqual(strip_glossary_markers("<start>신비한 보물상자<end>"), "신비한 보물상자")


if __name__ == "__main__":
    unittest.main()
