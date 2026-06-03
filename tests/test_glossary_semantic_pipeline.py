"""Characterization tests for the semantic glossary cleanup pipeline.

These tests were added under ADR-0033 *before* extracting
``scripts/glossary_semantic_pipeline.py`` into ``src/`` so that the subsequent
pure-move refactor has a behavior baseline. The original file shipped without
tests; this locks in the local, deterministic behavior that does not require a
heavy NLP model download (jieba / Stanza / kiwipiepy / embeddings are exercised
only at orchestration time and are out of scope here).

Assertions favor semantic invariants and structural outcomes over exact
score magic numbers, so they remain stable across the extraction and are not
coupled to the precise weights in ``configs/glossary/rules.json``.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import MagicMock, patch

from longtu_translation_pipeline.cleanup.glossary_semantic import pipeline as gsp

ROOT = Path(__file__).resolve().parents[1]


def setUpModule() -> None:
    # Load the real repository config once: reproducible, text-only, no model
    # download. Populates the module globals RULES / PATTERNS / LEXICONS that the
    # lexicon- and score-dependent helpers read.
    gsp.load_pipeline_config(ROOT / "configs" / "glossary")


class PureHelpersTest(unittest.TestCase):
    def test_has_cjk(self) -> None:
        self.assertTrue(gsp.has_cjk("技能"))
        self.assertFalse(gsp.has_cjk("skill 123"))
        self.assertFalse(gsp.has_cjk(""))

    def test_has_hangul(self) -> None:
        self.assertTrue(gsp.has_hangul("스킬"))
        self.assertFalse(gsp.has_hangul("abc"))
        self.assertFalse(gsp.has_hangul("技能"))

    def test_batched(self) -> None:
        self.assertEqual(
            gsp.batched(["a", "b", "c", "d", "e"], 2),
            [["a", "b"], ["c", "d"], ["e"]],
        )
        self.assertEqual(gsp.batched([], 3), [])
        self.assertEqual(gsp.batched(["a"], 5), [["a"]])

    def test_root_is_non_noun(self) -> None:
        self.assertTrue(gsp.root_is_non_noun("x/VERB/root y"))
        self.assertTrue(gsp.root_is_non_noun("x/ADJ/root"))
        self.assertFalse(gsp.root_is_non_noun("x/NOUN/root"))
        self.assertFalse(gsp.root_is_non_noun("x/PROPN/root"))


class ConfigDependentHelpersTest(unittest.TestCase):
    def test_split_compound_splits_known_suffix(self) -> None:
        # 石 is a configured compound suffix; the stem must be returned with it.
        stem, suffix = gsp.split_compound("红宝石")
        self.assertEqual(suffix, "石")
        self.assertEqual(stem, "红宝")

    def test_split_compound_no_suffix_returns_empty(self) -> None:
        self.assertEqual(gsp.split_compound("技能"), ("", ""))

    def test_build_compound_families_groups_by_stem(self) -> None:
        rows = [
            {"zh-CN": "红宝石"},
            {"zh-CN": "蓝宝石"},
            {"zh-CN": "技能"},
        ]
        families = gsp.build_compound_families(rows)
        self.assertEqual(families.get("红宝"), {"石"})
        self.assertEqual(families.get("蓝宝"), {"石"})
        self.assertNotIn("技能", families)

    def test_has_game_anchor(self) -> None:
        self.assertTrue(gsp.has_game_anchor("BOSS"))

    def test_is_proper_like_propn_root(self) -> None:
        self.assertTrue(gsp.is_proper_like("x/PROPN/root"))
        self.assertFalse(gsp.is_proper_like("x/NOUN/root"))


class ScoreInvariantsTest(unittest.TestCase):
    """Scores are clamped to [0, 1]; clear-signal inputs outrank empty ones."""

    def test_game_term_score_in_unit_range(self) -> None:
        for value in (
            gsp.game_term_score("BOSS", "보스", 0.0),
            gsp.game_term_score("随便", "아무", 0.0),
            gsp.game_term_score("随便", "아무", 1.0),
        ):
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_game_term_score_anchor_beats_plain(self) -> None:
        anchored = gsp.game_term_score("BOSS", "보스", 0.0)
        plain = gsp.game_term_score("随便", "아무", 0.0)
        self.assertGreater(anchored, plain)
        self.assertEqual(plain, 0.0)

    def test_game_term_score_embedding_signal_lifts_plain(self) -> None:
        no_signal = gsp.game_term_score("随便", "아무", 0.0)
        high_embedding = gsp.game_term_score("随便", "아무", 1.0)
        self.assertGreater(high_embedding, no_signal)

    def test_general_and_common_and_domain_scores_in_unit_range(self) -> None:
        gws = gsp.general_word_score("打", "치다", "打/VERB/root")
        cns = gsp.common_noun_score("随便", "아무", 0.5, 0.5, 3.0, 3.0, 0.0)
        dss = gsp.domain_specificity_score("BOSS", "보스", "x/PROPN/root", 1.0, 0.0)
        for value in (gws, cns, dss):
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)


class SafeZipfFrequencyTest(unittest.TestCase):
    def test_empty_text_returns_sentinel(self) -> None:
        self.assertEqual(gsp.safe_zipf_frequency("", "zh"), -1.0)

    def test_known_word_is_nonnegative_and_cached(self) -> None:
        value = gsp.safe_zipf_frequency("的", "zh")
        # wordfreq may be absent (-> -1.0 sentinel) or present (-> >= 0); either
        # way the value is cached under the (text, lang) key after the call.
        self.assertIn(("的", "zh"), gsp.ZIPF_CACHE)
        self.assertEqual(gsp.ZIPF_CACHE[("的", "zh")], value)


class EnforceStrictPairsTest(unittest.TestCase):
    """ADR-0018 / strict-pair logic: merge compatible duplicates, remove conflicts."""

    @staticmethod
    def _item(zh: str, ko: str, action: str = "KEEP_HIGH", **extra: str) -> dict:
        row = {"zh-CN": zh, "ko": ko}
        row.update(extra)
        return {"row": row, "action": action, "reasons": []}

    def test_distinct_pairs_are_kept(self) -> None:
        classified = [self._item("技能", "스킬"), self._item("暴击", "치명타")]
        gsp.enforce_strict_pairs(classified)
        self.assertEqual([it["action"] for it in classified], ["KEEP_HIGH", "KEEP_HIGH"])

    def test_duplicate_pair_without_conflict_is_merged(self) -> None:
        classified = [
            self._item("技能", "스킬", en="skill"),
            self._item("技能", "스킬", ja=""),
        ]
        gsp.enforce_strict_pairs(classified)
        self.assertEqual(
            [it["action"] for it in classified],
            ["KEEP_HIGH", "MERGED_DUPLICATE"],
        )

    def test_duplicate_pair_with_other_language_conflict_is_removed(self) -> None:
        classified = [
            self._item("技能", "스킬", en="skill"),
            self._item("技能", "스킬", en="ability"),
        ]
        gsp.enforce_strict_pairs(classified)
        self.assertEqual(
            [it["action"] for it in classified],
            ["KEEP_HIGH", "AUTO_REMOVE"],
        )

    def test_same_zh_different_ko_both_removed(self) -> None:
        classified = [self._item("技能", "스킬"), self._item("技能", "기술")]
        gsp.enforce_strict_pairs(classified)
        self.assertEqual([it["action"] for it in classified], ["AUTO_REMOVE", "AUTO_REMOVE"])

    def test_same_ko_different_zh_both_removed(self) -> None:
        classified = [self._item("技能", "스킬"), self._item("기술입력", "스킬")]
        gsp.enforce_strict_pairs(classified)
        self.assertEqual([it["action"] for it in classified], ["AUTO_REMOVE", "AUTO_REMOVE"])


class ZhNounScoreGlossaryTest(unittest.TestCase):
    """zh_noun_score: config-weighted jieba + stanza scoring (ADR-0033 step 9a)."""

    def test_empty_text_returns_zero(self) -> None:
        score, evidence = gsp.zh_noun_score("", {})
        self.assertEqual(score, 0.0)
        self.assertEqual(evidence, "")

    def test_all_noun_tokens_raise_score(self) -> None:
        mock_pseg = MagicMock()
        mock_pseg.cut.return_value = [("BOSS", "n"), ("战", "n")]
        stanza = {"upos": ["NOUN", "NOUN"], "root_upos": "NOUN", "summary": "BOSS/NOUN/root 战/NOUN/nmod", "deprels": ["root", "nmod"]}
        with patch.dict(sys.modules, {"jieba": MagicMock(), "jieba.posseg": mock_pseg}):
            score, evidence = gsp.zh_noun_score("BOSS战", stanza)
        self.assertGreater(score, 0.5)
        self.assertIn("jieba=", evidence)

    def test_score_in_unit_range(self) -> None:
        mock_pseg = MagicMock()
        mock_pseg.cut.return_value = [("技能", "v")]  # verb tag → lower score
        with patch.dict(sys.modules, {"jieba": MagicMock(), "jieba.posseg": mock_pseg}):
            score, _ = gsp.zh_noun_score("技能", {"upos": ["VERB"]})
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_empty_jieba_empty_stanza_returns_nonnegative(self) -> None:
        mock_pseg = MagicMock()
        mock_pseg.cut.return_value = []
        with patch.dict(sys.modules, {"jieba": MagicMock(), "jieba.posseg": mock_pseg}):
            score, _ = gsp.zh_noun_score("技能", {})
        self.assertGreaterEqual(score, 0.0)


class KoNounScoreGlossaryTest(unittest.TestCase):
    """ko_noun_score: kiwi injected + stanza coefficient logic (ADR-0033 step 9a)."""

    @staticmethod
    def _tok(tag: str, form: str = "x") -> MagicMock:
        t = MagicMock()
        t.tag = tag
        t.form = form
        return t

    def test_empty_text_returns_zero(self) -> None:
        score, evidence = gsp.ko_noun_score("", MagicMock(), {})
        self.assertEqual(score, 0.0)
        self.assertEqual(evidence, "")

    def test_all_noun_tokens_raise_score(self) -> None:
        kiwi = MagicMock()
        kiwi.tokenize.return_value = [self._tok("NNG", "기술"), self._tok("NNG", "공격")]
        stanza = {"upos": ["NOUN", "NOUN"], "root_upos": "NOUN", "summary": "기술/NOUN/root 공격/NOUN/nmod"}
        score, evidence = gsp.ko_noun_score("기술공격", kiwi, stanza)
        self.assertGreater(score, 0.5)
        self.assertIn("kiwi=", evidence)

    def test_score_in_unit_range(self) -> None:
        kiwi = MagicMock()
        kiwi.tokenize.return_value = [self._tok("VV", "한다")]
        score, _ = gsp.ko_noun_score("한다", kiwi, {})
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class BuildStanzaCacheGlossaryTest(unittest.TestCase):
    """build_stanza_cache in glossary_semantic context (ADR-0033 step 9a)."""

    def test_empty_values_returns_empty_cache(self) -> None:
        mock_pipeline = MagicMock()
        result = gsp.build_stanza_cache(mock_pipeline, [], batch_size=64, label="t")
        self.assertEqual(result, {})
        mock_pipeline.bulk_process.assert_not_called()

    def test_cache_keyed_by_input_text(self) -> None:
        mock_doc = MagicMock()
        mock_doc.sentences = []
        mock_pipeline = MagicMock()
        mock_pipeline.bulk_process.return_value = [mock_doc]
        result = gsp.build_stanza_cache(mock_pipeline, ["技能"], batch_size=64, label="t")
        self.assertIn("技能", result)
        self.assertIn("upos", result["技能"])


class EncodeSimAndGameScoresTest(unittest.TestCase):
    """encode_similarities_and_game_scores: numpy dot-product logic with mocked model."""

    def test_returns_three_arrays_of_correct_length(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not available")
        n, dim = 2, 4
        rows = [{"zh-CN": f"w{i}", "ko": f"k{i}"} for i in range(n)]
        vec_n = np.ones((n, dim), dtype="float32") / n
        vec_1 = np.ones((1, dim), dtype="float32")
        mock_model = MagicMock()
        mock_model.encode.side_effect = [vec_n, vec_n, vec_1, vec_1]  # zh, ko, game_seed, common_seed
        sims, game_scores, generic_scores = gsp.encode_similarities_and_game_scores(
            mock_model, rows,
            game_seed_terms=["seed_a"],
            common_noun_seed_terms=["seed_b"],
        )
        self.assertEqual(len(sims), n)
        self.assertEqual(len(game_scores), n)
        self.assertEqual(len(generic_scores), n)

    def test_empty_ko_row_gives_zero_similarity(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not available")
        rows = [{"zh-CN": "技能", "ko": ""}]
        dim = 4
        z = np.zeros((1, dim), dtype="float32")
        s = np.ones((1, dim), dtype="float32")
        mock_model = MagicMock()
        mock_model.encode.side_effect = [z, z, s, s]
        sims, _, _ = gsp.encode_similarities_and_game_scores(
            mock_model, rows, game_seed_terms=["a"], common_noun_seed_terms=["b"]
        )
        self.assertEqual(float(sims[0]), 0.0)


class ClassifyRowsTest(unittest.TestCase):
    """classify_rows: decision logic with injected NLP data; config pre-loaded by setUpModule."""

    @staticmethod
    def _make_rows(pairs: list) -> list[dict]:
        return [
            {"zh-CN": zh, "ko": ko, "original_term_id": str(i + 1),
             **{lang: "" for lang in gsp.LANGS if lang not in ("zh-CN", "ko")}}
            for i, (zh, ko) in enumerate(pairs)
        ]

    def test_result_length_matches_input(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not available")
        rows = self._make_rows([("BOSS", "보스"), ("技能", "스킬")])
        kiwi = MagicMock()
        kiwi.tokenize.return_value = []
        n = len(rows)
        result = gsp.classify_rows(
            rows,
            segment_text={"zh-CN": "BOSS", "ko": "보스", "zh-CN_upper": "BOSS", "ko_upper": "보스"},
            families={},
            zh_stanza={},
            ko_stanza={},
            kiwi=kiwi,
            similarities=np.zeros(n),
            game_embedding_scores=np.zeros(n),
            generic_embedding_scores=np.zeros(n),
            embedding_model="test",
            embedding_device="cpu",
        )
        self.assertEqual(len(result), n)

    def test_missing_ko_triggers_auto_remove(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not available")
        rows = self._make_rows([("技能", "")])
        kiwi = MagicMock()
        kiwi.tokenize.return_value = []
        result = gsp.classify_rows(
            rows,
            segment_text={"zh-CN": "", "ko": "", "zh-CN_upper": "", "ko_upper": ""},
            families={},
            zh_stanza={},
            ko_stanza={},
            kiwi=kiwi,
            similarities=np.zeros(1),
            game_embedding_scores=np.zeros(1),
            generic_embedding_scores=np.zeros(1),
            embedding_model="test",
            embedding_device="cpu",
        )
        self.assertEqual(result[0]["action"], "AUTO_REMOVE")
        self.assertIn("missing_ko_for_zh_ko_glossary", result[0]["reasons"])


class WriteOutputsTest(unittest.TestCase):
    """write_outputs: CSV output structure; config pre-loaded by setUpModule."""

    @staticmethod
    def _make_item(action: str = "AUTO_KEEP") -> dict:
        row = {"original_term_id": "1", "zh-CN": "技能", "ko": "스킬"}
        row.update({lang: "" for lang in gsp.LANGS if lang not in row})
        return {
            "row": row, "action": action, "reasons": ["test"],
            "term_score": 0.8, "noun_score": 0.7, "zh_noun_score": 0.7,
            "ko_noun_score": 0.7, "product_evidence_score": 0.5,
            "compound_score": 0.0, "bilingual_score": 0.85,
            "general_word_score": 0.1, "game_term_score": 0.8,
            "common_noun_score": 0.2, "domain_specificity_score": 0.6,
            "game_embedding_score": 0.8, "generic_embedding_score": 0.2,
            "zh_zipf_frequency": 3.0, "ko_zipf_frequency": 2.5,
            "embedding_model": "test-model", "embedding_device": "cpu",
            "zh_segment_count": 3, "ko_segment_count": 2,
            "stem": "", "suffix": "", "family_size": 0,
            "zh_pos": "NOUN/root", "ko_pos": "NNG",
        }

    def test_audit_and_glossary_files_are_created(self) -> None:
        keep = self._make_item("AUTO_KEEP")
        remove = self._make_item("AUTO_REMOVE")
        classified = [keep, remove]
        by_pair = gsp.enforce_strict_pairs(classified)
        with tempfile.TemporaryDirectory() as tmpdir:
            review_dir = Path(tmpdir) / "review"
            review_dir.mkdir()
            glossary_path = Path(tmpdir) / "glossary.csv"
            glossary_path.write_text("term_id,zh-CN,ko\n1,技能,스킬\n", encoding="utf-8-sig")
            summary: OrderedDict = OrderedDict([("mode", "dry-run")])
            gsp.write_outputs(
                classified=classified,
                by_pair=by_pair,
                glossary_path=glossary_path,
                review_dir=review_dir,
                summary=summary,
            )
            self.assertTrue((review_dir / "glossary_semantic_audit.csv").exists())
            self.assertTrue((review_dir / "removed_glossary_semantic_cleanup.csv").exists())
            self.assertTrue(glossary_path.exists())

    def test_summary_is_updated_with_counts(self) -> None:
        keep = self._make_item("AUTO_KEEP")
        remove = self._make_item("AUTO_REMOVE")
        classified = [keep, remove]
        by_pair = gsp.enforce_strict_pairs(classified)
        with tempfile.TemporaryDirectory() as tmpdir:
            review_dir = Path(tmpdir) / "review"
            review_dir.mkdir()
            glossary_path = Path(tmpdir) / "glossary.csv"
            glossary_path.write_text("term_id,zh-CN,ko\n1,技能,스킬\n", encoding="utf-8-sig")
            summary: OrderedDict = OrderedDict([("mode", "dry-run")])
            gsp.write_outputs(
                classified=classified,
                by_pair=by_pair,
                glossary_path=glossary_path,
                review_dir=review_dir,
                summary=summary,
            )
            self.assertIn("auto_remove_rows", summary)
            self.assertEqual(summary["auto_remove_rows"], 1)
            self.assertIn("auto_keep_rows", summary)


if __name__ == "__main__":
    unittest.main()
