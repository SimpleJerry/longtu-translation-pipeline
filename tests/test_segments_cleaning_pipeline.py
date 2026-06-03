from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from longtu_translation_pipeline.cleanup.segments_cleaning import pipeline as segments
from longtu_translation_pipeline.cleanup.segments_cleaning import classify as sc_classify


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


def collect(rows: list[dict[str, str]]):
    return segments.collect_initial_items(
        rows,
        glossary_pairs=set(),
        patterns=make_patterns(),
        thresholds={"sentence_like_keep_threshold": 0.55},
        sentence_markers=[],
    )


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


class MarkupStrippingTest(unittest.TestCase):
    def setUp(self) -> None:
        self._patterns = make_patterns()

    def _strip(self, text: str) -> str:
        return segments.strip_presentation_tags(text, self._patterns)

    def test_color_tag_stripped_content_kept(self) -> None:
        self.assertEqual(self._strip("<c=red>foo</c>"), "foo")

    def test_simple_c_tag_stripped(self) -> None:
        self.assertEqual(self._strip("<c>bar</c>"), "bar")

    def test_nested_color_tags_stripped(self) -> None:
        self.assertEqual(self._strip("<c=red><c=blue>text</c></c>"), "text")

    def test_hlgreen_tag_stripped(self) -> None:
        # <hlgreen> is a presentation tag; </hlgreen> is matched by </c>-family,
        # so we test <hlgreen> alone followed by the closing </c> variant
        result = self._strip("<hlgreen>hi</c>")
        self.assertNotIn("<hlgreen>", result)
        self.assertIn("hi", result)

    def test_percentage_preserved(self) -> None:
        self.assertEqual(self._strip("2%"), "2%")

    def test_no_tags_unchanged(self) -> None:
        self.assertEqual(self._strip("hello world"), "hello world")

    def test_cjk_space_collapsed_after_strip(self) -> None:
        # After stripping a tag between CJK characters the extra space is removed
        result = self._strip("你<c=red>好</c>朋友")
        self.assertNotIn("  ", result)
        self.assertIn("好", result)


class SymmetricWrapperTest(unittest.TestCase):
    def setUp(self) -> None:
        self._patterns = make_patterns()

    def _match(self, text: str):
        return segments.wrapper_match(text, self._patterns)

    def test_brace_quote_wrapper_name(self) -> None:
        result = self._match('{"foo"}')
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "brace_quote_wrapper")

    def test_brace_quote_wrapper_value(self) -> None:
        result = self._match('{"foo"}')
        self.assertEqual(result[1], "foo")

    def test_quote_wrapper_name(self) -> None:
        result = self._match('"hello"')
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "quote_wrapper")

    def test_quote_wrapper_value(self) -> None:
        result = self._match('"hello"')
        self.assertEqual(result[1], "hello")

    def test_paren_wrapper_name(self) -> None:
        result = self._match("（内容）")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "paren_wrapper")

    def test_paren_wrapper_value(self) -> None:
        result = self._match("（内容）")
        self.assertEqual(result[1], "内容")

    def test_plain_text_no_wrapper(self) -> None:
        self.assertIsNone(self._match("foo bar"))

    def test_asymmetric_brace_not_matched(self) -> None:
        self.assertIsNone(self._match('{"foo"'))

    def test_symmetric_same_type_both_sides_unwrapped(self) -> None:
        row = {"segment_id": "1", "zh-CN": '{"确认"}', "ko": '{"확인"}'}
        result = segments.normalize_row(
            row,
            patterns=self._patterns,
            normalized_markup=[],
            normalized_wrappers=[],
            markup_mismatch_review=[],
        )
        self.assertEqual(result["zh-CN"], "确认")
        self.assertEqual(result["ko"], "확인")

    def test_asymmetric_wrapper_one_side_not_unwrapped(self) -> None:
        row = {"segment_id": "1", "zh-CN": '{"确认"}', "ko": "확인"}
        result = segments.normalize_row(
            row,
            patterns=self._patterns,
            normalized_markup=[],
            normalized_wrappers=[],
            markup_mismatch_review=[],
        )
        self.assertEqual(result["zh-CN"], '{"确认"}')
        self.assertEqual(result["ko"], "확인")


class ParseTupleLikeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._patterns = make_patterns()

    def test_brace_tuple_three_elements(self) -> None:
        result = segments.parse_tuple_like('{"a", "b", "c"}', self._patterns)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3)

    def test_bracket_tuple_two_elements(self) -> None:
        result = segments.parse_tuple_like('["x", "y"]', self._patterns)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)

    def test_no_quoted_comma_returns_none(self) -> None:
        result = segments.parse_tuple_like("{foo bar}", self._patterns)
        self.assertIsNone(result)

    def test_single_element_returns_none(self) -> None:
        result = segments.parse_tuple_like('{"only one"}', self._patterns)
        self.assertIsNone(result)


class StructuredTupleSplitTest(unittest.TestCase):
    def test_well_formed_aligned_tuple_splits_into_children(self) -> None:
        # Use bracket form: brace form {"..."} matches brace_quote_wrapper and gets unwrapped first
        rows = [{"segment_id": "5", "zh-CN": '["你好", "再见"]', "ko": '["안녕", "잘 가"]'}]
        audit, split_review, *_ = collect(rows)
        split_items = [item for item in audit if item["original_segment_id"] == "5"]
        self.assertEqual(len(split_items), 2)
        self.assertEqual(split_items[0]["split_index"], "1")
        self.assertEqual(split_items[0]["zh-CN"], "你好")

    def test_misaligned_tuple_flagged_not_split(self) -> None:
        # zh has 2 elements, ko has 1 → alignment fails → REMOVE_STRUCTURED_UNPARSED
        rows = [{"segment_id": "6", "zh-CN": '["你好", "再见"]', "ko": '["안녕"]'}]
        audit, *_ = collect(rows)
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["action"], "REMOVE_STRUCTURED_UNPARSED")
        self.assertEqual(audit[0]["reason"], "tuple_parse_or_alignment_failed")


class PlaceholderMismatchTest(unittest.TestCase):
    def _placeholder_review(self, zh: str, ko: str) -> list[dict[str, str]]:
        _, _, placeholder_review, *_ = collect([{"segment_id": "1", "zh-CN": zh, "ko": ko}])
        return placeholder_review

    def test_source_has_extra_placeholder_flagged(self) -> None:
        review = self._placeholder_review("获得{0}{1}", "{0} 획득")
        self.assertEqual(len(review), 1)
        self.assertIn("{1}", review[0]["zh_placeholders"])

    def test_target_has_extra_placeholder_flagged(self) -> None:
        review = self._placeholder_review("获得{0}", "{0}{1} 획득")
        self.assertEqual(len(review), 1)

    def test_matching_placeholders_not_flagged(self) -> None:
        review = self._placeholder_review("获得{0}{1}", "{0}{1} 획득")
        self.assertEqual(len(review), 0)


class NonSegmentFragmentTest(unittest.TestCase):
    def test_single_cjk_with_placeholder_kept(self) -> None:
        item = classify("艮{0}", "{0}간")
        self.assertEqual(item["action"], "KEEP")
        self.assertEqual(item["semantic_action"], "SKIP_PLACEHOLDER")


class TargetContaminationTest(unittest.TestCase):
    def test_empty_ko_removed_as_empty(self) -> None:
        item = classify("你好", "")
        self.assertEqual(item["action"], "REMOVE_EMPTY")
        self.assertEqual(item["reason"], "empty_after_split")

    def test_ko_contains_cjk_removed(self) -> None:
        item = classify("你好", "你好")
        self.assertEqual(item["action"], "REMOVE_TARGET_LANGUAGE_CONTAMINATION")
        self.assertEqual(item["reason"], "ko_contains_cjk")

    def test_ko_without_hangul_removed(self) -> None:
        item = classify("hello", "hello")
        self.assertEqual(item["action"], "REMOVE_TARGET_LANGUAGE_CONTAMINATION")
        self.assertEqual(item["reason"], "ko_without_hangul")

    def test_valid_hangul_kept(self) -> None:
        item = classify("안녕", "안녕하세요")
        self.assertEqual(item["action"], "KEEP")


class UtilityFunctionTest(unittest.TestCase):
    def test_has_cjk_true(self) -> None:
        self.assertTrue(segments.has_cjk("你好"))

    def test_has_cjk_false_latin(self) -> None:
        self.assertFalse(segments.has_cjk("hello"))

    def test_has_hangul_true(self) -> None:
        self.assertTrue(segments.has_hangul("안녕"))

    def test_has_hangul_false_latin(self) -> None:
        self.assertFalse(segments.has_hangul("hello"))

    def test_pure_cjk_len_single_char(self) -> None:
        self.assertEqual(segments.pure_cjk_len("艮"), 1)

    def test_pure_cjk_len_mixed_returns_zero(self) -> None:
        self.assertEqual(segments.pure_cjk_len("艮{0}"), 0)

    def test_pure_cjk_len_empty_returns_zero(self) -> None:
        self.assertEqual(segments.pure_cjk_len(""), 0)


class SentenceLikeScoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self._patterns = make_patterns()

    def _score(self, zh: str, ko: str, markers: list[str] | None = None) -> float:
        return segments.sentence_like_score(
            zh,
            ko,
            patterns=self._patterns,
            sentence_markers=markers or [],
        )

    def test_placeholder_gives_max_score(self) -> None:
        score = self._score("获得{0}", "{0} 획득")
        self.assertGreaterEqual(score, 1.0)

    def test_sentence_punctuation_adds_to_score(self) -> None:
        score = self._score("你好！", "안녕하세요!")
        self.assertGreater(score, 0.0)

    def test_no_markers_empty_text_score_zero(self) -> None:
        score = self._score("abc", "def")
        self.assertEqual(score, 0.0)

    def test_ko_sentence_end_adds_to_score(self) -> None:
        score = self._score("감사합니다", "감사합니다")
        self.assertGreater(score, 0.0)


class ZhNounScoreTest(unittest.TestCase):
    """zh_noun_score: jieba + stanza coefficient logic (ADR-0033 characterization)."""

    def test_empty_text_returns_zero(self) -> None:
        score, evidence = segments.zh_noun_score("", {})
        self.assertEqual(score, 0.0)
        self.assertEqual(evidence, "")

    def test_all_noun_tokens_raise_score(self) -> None:
        mock_pseg = MagicMock()
        mock_pseg.cut.return_value = [("技能", "n"), ("攻击", "n")]
        stanza = {"upos": ["NOUN", "NOUN"], "summary": "技能/NOUN 攻击/NOUN"}
        with patch.dict(sys.modules, {"jieba": MagicMock(), "jieba.posseg": mock_pseg}):
            score, evidence = segments.zh_noun_score("技能攻击", stanza)
        # raw = 0.15 + 0.45*1.0 + 0.40*1.0 + 0.08 (alpha digit) → clamped 1.0
        self.assertGreater(score, 0.5)
        self.assertIn("jieba=", evidence)

    def test_empty_jieba_empty_stanza_gives_baseline(self) -> None:
        mock_pseg = MagicMock()
        mock_pseg.cut.return_value = []
        with patch.dict(sys.modules, {"jieba": MagicMock(), "jieba.posseg": mock_pseg}):
            score, _ = segments.zh_noun_score("技能", {})
        # 0.15 + 0 + 0; has_cjk → no CJK penalty; no alpha → no bonus
        self.assertAlmostEqual(score, 0.15, places=6)

    def test_score_in_unit_range(self) -> None:
        mock_pseg = MagicMock()
        mock_pseg.cut.return_value = [("x", "n")]
        with patch.dict(sys.modules, {"jieba": MagicMock(), "jieba.posseg": mock_pseg}):
            score, _ = segments.zh_noun_score("x", {"upos": ["NOUN"]})
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class KoNounScoreTest(unittest.TestCase):
    """ko_noun_score: kiwipiepy (injected) + stanza coefficient logic."""

    @staticmethod
    def _tok(tag: str, form: str = "x") -> MagicMock:
        t = MagicMock()
        t.tag = tag
        t.form = form
        return t

    def test_empty_text_returns_zero(self) -> None:
        score, evidence = segments.ko_noun_score("", MagicMock(), {})
        self.assertEqual(score, 0.0)
        self.assertEqual(evidence, "")

    def test_all_noun_tokens_raise_score(self) -> None:
        kiwi = MagicMock()
        kiwi.tokenize.return_value = [self._tok("NNG", "기술"), self._tok("NNG", "공격")]
        stanza = {"upos": ["NOUN", "NOUN"], "summary": "기술/NOUN 공격/NOUN"}
        score, evidence = segments.ko_noun_score("기술공격", kiwi, stanza)
        # 0.15 + 0.45*1.0 + 0.35*1.0 + 0.10 (noun_final) = 1.05 → clamped 1.0
        self.assertEqual(score, 1.0)
        self.assertIn("kiwi=", evidence)

    def test_verb_final_reduces_score_to_zero(self) -> None:
        kiwi = MagicMock()
        kiwi.tokenize.return_value = [self._tok("VV", "한다")]
        score, _ = segments.ko_noun_score("한다", kiwi, {})
        # 0.15 + 0 + 0 − 0.25 (VV in verb_final_tags) = −0.10 → clamped 0.0
        self.assertEqual(score, 0.0)

    def test_score_in_unit_range(self) -> None:
        kiwi = MagicMock()
        kiwi.tokenize.return_value = [self._tok("NNG", "기술")]
        score, _ = segments.ko_noun_score("기술", kiwi, {"upos": ["NOUN"]})
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class BuildStanzaCacheTest(unittest.TestCase):
    """build_stanza_cache: pipeline mock → dict keyed by text."""

    def test_empty_values_returns_empty_cache(self) -> None:
        mock_pipeline = MagicMock()
        result = segments.build_stanza_cache(mock_pipeline, [], batch_size=64, label="t")
        self.assertEqual(result, {})
        mock_pipeline.bulk_process.assert_not_called()

    def test_cache_keyed_by_input_text(self) -> None:
        mock_doc = MagicMock()
        mock_doc.sentences = []
        mock_pipeline = MagicMock()
        mock_pipeline.bulk_process.return_value = [mock_doc]
        result = segments.build_stanza_cache(mock_pipeline, ["技能"], batch_size=64, label="t")
        self.assertIn("技能", result)
        self.assertIn("upos", result["技能"])


class EncodeSemanticScoresTest(unittest.TestCase):
    """encode_semantic_scores: numpy dot-product logic with mocked model."""

    def test_empty_items_returns_empty(self) -> None:
        result = segments.encode_semantic_scores(
            model=MagicMock(), items=[], glossary_terms=[], seed_terms=["s"]
        )
        self.assertEqual(result, ([], [], ""))

    def test_returns_correct_length_and_method(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not available")
        n, dim = 2, 4
        vec = (np.ones((n, dim), dtype="float32") / n)
        seed_vec = (np.ones((1, dim), dtype="float32") / 1)
        mock_model = MagicMock()
        mock_model.encode.side_effect = [vec, seed_vec]  # zh, seed (no glossary)
        items = [{"zh-CN": f"w{i}"} for i in range(n)]
        gl, sl, method = segments.encode_semantic_scores(
            model=mock_model, items=items, glossary_terms=[], seed_terms=["seed"]
        )
        self.assertEqual(len(gl), n)
        self.assertEqual(len(sl), n)
        self.assertEqual(method, "max_zh_embedding")

    def test_exact_seed_in_zh_forces_similarity_to_one(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not available")
        dim = 4
        vec = np.zeros((1, dim), dtype="float32")
        seed_vec = np.ones((1, dim), dtype="float32")
        mock_model = MagicMock()
        mock_model.encode.side_effect = [vec, seed_vec]
        items = [{"zh-CN": "seed_word"}]
        _, sl, _ = segments.encode_semantic_scores(
            model=mock_model, items=items, glossary_terms=[], seed_terms=["seed_word"]
        )
        self.assertEqual(sl[0], 1.0)


class ScoreSemanticCandidatesTest(unittest.TestCase):
    """score_semantic_candidates: decision logic with all NLP backends mocked."""

    _THRESHOLDS: dict = {
        "semantic_term_remove_threshold": 0.68,
        "semantic_term_review_threshold": 0.56,
        "noun_score_min": 0.55,
        "sentence_like_keep_threshold": 0.55,
        "glossary_similarity_threshold": 0.70,
        "term_seed_similarity_threshold": 0.72,
    }
    _WEIGHTS: dict = {
        "noun_score": 0.38,
        "glossary_similarity": 0.30,
        "term_seed_similarity": 0.27,
        "sentence_like_penalty": 0.25,
    }

    @staticmethod
    def _make_item(zh: str = "技能", ko: str = "기술", sls: str = "0.0000") -> dict:
        return {
            "original_segment_id": "1", "split_index": "0",
            "action": "KEEP", "reason": "kept",
            "semantic_action": "PENDING_SEMANTIC", "semantic_term_score": "",
            "noun_score": "", "zh_noun_score": "", "ko_noun_score": "",
            "glossary_similarity": "", "term_seed_similarity": "",
            "sentence_like_score": sls, "embedding_model": "", "embedding_device": "",
            "zh_pos": "", "ko_pos": "", "zh-CN": zh, "ko": ko,
        }

    def _run(
        self,
        items: list,
        zh_noun_rv: tuple,
        ko_noun_rv: tuple,
        gl_scores: list,
        seed_scores: list,
    ) -> tuple:
        mock_kiwi_mod = MagicMock()
        mock_kiwi_mod.Kiwi = MagicMock(return_value=MagicMock())
        with patch.object(sc_classify, "load_stanza_pipelines",
                          return_value=(MagicMock(), MagicMock())), \
             patch.object(sc_classify, "build_stanza_cache",
                          side_effect=[{}, {}]), \
             patch.object(sc_classify, "load_embedding_model",
                          return_value=(MagicMock(), "test-model", "cpu")), \
             patch.object(sc_classify, "encode_semantic_scores",
                          return_value=(gl_scores, seed_scores, "test_method")), \
             patch.object(sc_classify, "zh_noun_score",
                          return_value=zh_noun_rv), \
             patch.object(sc_classify, "ko_noun_score",
                          return_value=ko_noun_rv), \
             patch.dict(sys.modules, {"kiwipiepy": mock_kiwi_mod}):
            return segments.score_semantic_candidates(
                items,
                glossary_terms=[], seed_terms=[],
                patterns={},
                thresholds=self._THRESHOLDS,
                weights=self._WEIGHTS,
                hf_home=Path("/tmp"),
                stanza_dir=Path("/tmp"),
                embedding_model="test",
                embedding_fallback="fallback",
            )

    def test_empty_list_returns_empty_strings(self) -> None:
        result = segments.score_semantic_candidates(
            [], glossary_terms=[], seed_terms=[], patterns={},
            thresholds=self._THRESHOLDS, weights=self._WEIGHTS,
            hf_home=Path("/tmp"), stanza_dir=Path("/tmp"),
            embedding_model="test", embedding_fallback="fallback",
        )
        self.assertEqual(result, ("", "", ""))

    def test_high_score_item_becomes_remove_term_like(self) -> None:
        # noun=0.8 (≥0.55), glossary=0.8 (≥0.70) → neighborhood met
        # semantic = 0.38*0.8 + 0.30*0.8 + 0.27*0.8 = 0.76 ≥ 0.68 → REMOVE
        item = self._make_item("技能", "기술")
        actual_model, device, method = self._run(
            [item],
            zh_noun_rv=(0.8, ""), ko_noun_rv=(0.8, ""),
            gl_scores=[0.8], seed_scores=[0.8],
        )
        self.assertEqual(item["action"], "REMOVE_TERM_LIKE")
        self.assertEqual(item["semantic_action"], "AUTO_REMOVE_SEMANTIC_TERM_ENTITY")
        self.assertEqual(actual_model, "test-model")

    def test_low_score_item_becomes_keep_semantic_segment(self) -> None:
        # noun=0.2 < noun_min=0.55 → cannot trigger remove/review → KEEP
        item = self._make_item("走走", "가보자")
        self._run(
            [item],
            zh_noun_rv=(0.2, ""), ko_noun_rv=(0.2, ""),
            gl_scores=[0.1], seed_scores=[0.1],
        )
        self.assertNotEqual(item["action"], "REMOVE_TERM_LIKE")
        self.assertEqual(item["semantic_action"], "KEEP_SEMANTIC_SEGMENT")


if __name__ == "__main__":
    unittest.main()
