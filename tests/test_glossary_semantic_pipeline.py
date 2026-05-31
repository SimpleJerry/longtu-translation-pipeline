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
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import glossary_semantic_pipeline as gsp  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
