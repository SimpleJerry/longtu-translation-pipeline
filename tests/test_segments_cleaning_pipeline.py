from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import segments_cleaning_pipeline as segments  # noqa: E402


def make_patterns() -> dict[str, re.Pattern[str]]:
    rules = {
        "regex": {
            "machine_placeholder": r"%[sd]|\{\d+\}|<[^>]+>|\$\{[^}]+\}",
            "presentation_tag": r"</?c(?:\s*=\s*[^>]+)?>|<hlgreen>",
            "angle_tag": r"<[^>]+>",
            "machine_angle_placeholder": r"<(?:key\d+|server|name|start|middle|end|code_id=[^>]+)>",
            "brace_quote_wrapper": r'^\s*\{\s*"(.*)"\s*\}\s*$',
            "quote_wrapper": r'^\s*"(.*)"\s*$',
            "paren_wrapper": r"^\s*[（(](.*)[）)]\s*$",
            "sentence_punctuation": r"[。！？!?；;]",
            "tuple_wrapper": r"^\s*[\{\[].*[\}\]]\s*$",
            "tuple_like": r'^\s*[\{\[].*"\s*,.*[\}\]]\s*$',
            "zh_sentence_end": r"[吗呢吧了着过啊呀哦嘛啦]$",
            "ko_sentence_end": r"(?:다|요|니다|세요|습니까|까요|합니다|됩니다)[.!?。！？]?$",
        }
    }
    return segments.compile_regexes(rules)


def classify(zh: str, ko: str) -> dict[str, str]:
    item = segments.base_audit_item(
        row={"segment_id": "1", "zh-CN": zh, "ko": ko},
        split_index=0,
        zh=zh,
        ko=ko,
    )
    segments.initial_classify(
        item,
        glossary_pairs=set(),
        patterns=make_patterns(),
        thresholds={"sentence_like_keep_threshold": 0.55},
        sentence_markers=[],
    )
    return item


class SegmentsCleaningPipelineTest(unittest.TestCase):
    def test_single_cjk_fragment_is_auto_removed(self) -> None:
        item = classify("艮", "간")

        self.assertEqual(item["action"], "REMOVE_NON_SEGMENT_FRAGMENT")
        self.assertEqual(item["reason"], "pure_cjk_single_char_fragment")
        self.assertEqual(item["semantic_action"], "AUTO_REMOVE_NON_SEGMENT_FRAGMENT")

    def test_target_with_cjk_is_auto_removed(self) -> None:
        item = classify("六壬秘境85级", "六壬秘境85级")

        self.assertEqual(item["action"], "REMOVE_TARGET_LANGUAGE_CONTAMINATION")
        self.assertEqual(item["reason"], "ko_contains_cjk")

    def test_target_without_hangul_is_auto_removed_even_with_placeholder(self) -> None:
        item = classify("{0}/{1}", "{0}/{1}")

        self.assertEqual(item["action"], "REMOVE_TARGET_LANGUAGE_CONTAMINATION")
        self.assertEqual(item["reason"], "ko_without_hangul")

    def test_placeholder_with_korean_target_is_still_kept_for_audit(self) -> None:
        item = classify("获得{0}", "{0} 획득")

        self.assertEqual(item["action"], "KEEP")
        self.assertEqual(item["semantic_action"], "SKIP_PLACEHOLDER")
        self.assertEqual(item["reason"], "placeholder_kept")


if __name__ == "__main__":
    unittest.main()
