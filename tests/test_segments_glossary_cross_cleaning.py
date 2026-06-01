from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.cleanup.segments_glossary_cross import pipeline as cross  # noqa: E402


class SegmentsGlossaryCrossCleaningTest(unittest.TestCase):
    def test_common_word_high_missing_rate_removes_glossary_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_glossary(paths["glossary"], [("1", "今日", "오늘")])
            write_segments(
                paths["segments"],
                [
                    ("1", "今日奖励", "일일 보상"),
                    ("2", "今日任务", "일일 임무"),
                    ("3", "今日礼包", "일일 패키지"),
                    ("4", "今日副本", "일일 던전"),
                    ("5", "今日活动", "일일 이벤트"),
                ],
            )

            result = cross.run_pipeline(
                paths["segments"],
                paths["glossary"],
                paths["rules"],
                paths["glossary_config"],
                paths["review"],
                apply=False,
            )

        self.assertEqual(result.removed_glossary_noise_rows, 1)
        self.assertEqual(result.removed_segment_conflict_rows, 0)

    def test_strong_term_with_preserved_evidence_removes_conflicting_segment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_glossary(paths["glossary"], [("1", "技能", "스킬")])
            write_segments(
                paths["segments"],
                [
                    ("1", "技能升级", "스킬 강화"),
                    ("2", "技能效果", "스킬 효과"),
                    ("3", "技能伤害", "스킬 피해"),
                    ("4", "释放技能", "기술 사용"),
                ],
            )

            result = cross.run_pipeline(
                paths["segments"],
                paths["glossary"],
                paths["rules"],
                paths["glossary_config"],
                paths["review"],
                apply=False,
            )

            removed = read_csv(paths["review"] / "removed_segment_terminology_conflicts.csv")

        self.assertEqual(result.removed_segment_conflict_rows, 1)
        self.assertEqual(removed[0]["original_segment_id"], "4")
        self.assertIn("技能=>스킬", removed[0]["missing_strong_terms"])

    def test_weak_preserved_evidence_keeps_strong_term_in_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_glossary(paths["glossary"], [("1", "传送", "전송")])
            write_segments(
                paths["segments"],
                [
                    ("1", "传送成功", "텔레포트 성공"),
                    ("2", "传送失败", "텔레포트 실패"),
                    ("3", "传送阵", "텔레포트진"),
                ],
            )

            result = cross.run_pipeline(
                paths["segments"],
                paths["glossary"],
                paths["rules"],
                paths["glossary_config"],
                paths["review"],
                apply=False,
            )
            term_summary = read_csv(paths["review"] / "cross_cleaning_term_summary.csv")

        self.assertEqual(result.removed_segment_conflict_rows, 0)
        self.assertEqual(term_summary[0]["term_action"], "TERM_NEEDS_REVIEW")

    def test_apply_rewrites_continuous_ids_and_preserves_original_review_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_glossary(
                paths["glossary"],
                [("1", "今日", "오늘"), ("2", "技能", "스킬")],
            )
            write_segments(
                paths["segments"],
                [
                    ("1", "今日奖励", "일일 보상"),
                    ("2", "今日任务", "일일 임무"),
                    ("3", "今日礼包", "일일 패키지"),
                    ("4", "今日副本", "일일 던전"),
                    ("5", "今日活动", "일일 이벤트"),
                    ("6", "技能升级", "스킬 강화"),
                    ("7", "技能效果", "스킬 효과"),
                    ("8", "技能伤害", "스킬 피해"),
                    ("9", "释放技能", "기술 사용"),
                ],
            )

            result = cross.run_pipeline(
                paths["segments"],
                paths["glossary"],
                paths["rules"],
                paths["glossary_config"],
                paths["review"],
                apply=True,
            )
            glossary = read_csv(paths["glossary"])
            segments = read_csv(paths["segments"])
            removed_glossary = read_csv(paths["review"] / "removed_glossary_cross_noise.csv")
            removed_segments = read_csv(
                paths["review"] / "removed_segment_terminology_conflicts.csv"
            )

        self.assertEqual(result.output_glossary_rows, 1)
        self.assertEqual(glossary[0]["term_id"], "1")
        self.assertEqual(glossary[0]["zh-CN"], "技能")
        self.assertEqual([row["segment_id"] for row in segments], [str(i) for i in range(1, 9)])
        self.assertEqual(removed_glossary[0]["original_term_id"], "1")
        self.assertEqual(removed_segments[0]["original_segment_id"], "9")

    def test_strict_apply_removes_unenforceable_terms_and_all_remaining_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_glossary(
                paths["glossary"],
                [("1", "今日", "오늘"), ("2", "技能", "스킬")],
            )
            write_segments(
                paths["segments"],
                [
                    ("1", "今日奖励", "일일 보상"),
                    ("2", "今日任务", "일일 임무"),
                    ("3", "今日礼包", "일일 패키지"),
                    ("4", "今日副本", "일일 던전"),
                    ("5", "今日活动", "일일 이벤트"),
                    ("6", "技能升级", "스킬 강화"),
                    ("7", "技能效果", "스킬 효과"),
                    ("8", "技能伤害", "스킬 피해"),
                    ("9", "释放技能", "기술 사용"),
                ],
            )

            strict_plan = cross.run_pipeline(
                paths["segments"],
                paths["glossary"],
                paths["rules"],
                paths["glossary_config"],
                paths["review"],
                mode="strict-dry-run",
            )
            self.assertEqual(strict_plan.strict_unenforceable_glossary_rows, 1)
            self.assertEqual(strict_plan.strict_removed_segment_mismatch_rows, 1)

            cross.run_pipeline(
                paths["segments"],
                paths["glossary"],
                paths["rules"],
                paths["glossary_config"],
                paths["review"],
                mode="strict-apply",
            )
            strict_check = cross.run_pipeline(
                paths["segments"],
                paths["glossary"],
                paths["rules"],
                paths["glossary_config"],
                paths["review"],
                mode="strict-check",
            )
            glossary = read_csv(paths["glossary"])
            segments = read_csv(paths["segments"])

        self.assertEqual(strict_check.strict_current_mismatch_rows, 0)
        self.assertEqual([row["zh-CN"] for row in glossary], ["技能"])
        self.assertEqual([row["segment_id"] for row in segments], [str(i) for i in range(1, 9)])

    def test_strict_check_does_not_overwrite_apply_review_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_glossary(paths["glossary"], [("1", "今日", "오늘"), ("2", "技能", "스킬")])
            write_segments(
                paths["segments"],
                [
                    ("1", "今日奖励", "일일 보상"),
                    ("2", "今日任务", "일일 임무"),
                    ("3", "今日礼包", "일일 패키지"),
                    ("4", "技能升级", "스킬 강화"),
                    ("5", "技能效果", "스킬 효과"),
                    ("6", "技能伤害", "스킬 피해"),
                    ("7", "释放技能", "기술 사용"),
                ],
            )
            cross.run_pipeline(
                paths["segments"],
                paths["glossary"],
                paths["rules"],
                paths["glossary_config"],
                paths["review"],
                mode="strict-apply",
            )
            before = read_csv(paths["review"] / "strict_removed_segment_glossary_mismatch.csv")

            cross.run_pipeline(
                paths["segments"],
                paths["glossary"],
                paths["rules"],
                paths["glossary_config"],
                paths["review"],
                mode="strict-check",
            )
            after = read_csv(paths["review"] / "strict_removed_segment_glossary_mismatch.csv")

        self.assertEqual(len(before), 1)
        self.assertEqual(after, before)

    def test_strict_treats_natural_phrase_variant_as_unenforceable_glossary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_glossary(paths["glossary"], [("1", "造成伤害", "입힌 피해")])
            write_segments(
                paths["segments"],
                [
                    ("1", "造成伤害", "입힌 피해"),
                    ("2", "对目标造成伤害", "대상에게 피해를 입힙니다"),
                    ("3", "对敌人造成伤害", "적에게 피해를 줍니다"),
                    ("4", "造成伤害并眩晕", "피해를 주고 기절시킵니다"),
                    ("5", "造成大量伤害", "큰 피해를 입힙니다"),
                ],
            )

            result = cross.run_pipeline(
                paths["segments"],
                paths["glossary"],
                paths["rules"],
                paths["glossary_config"],
                paths["review"],
                mode="strict-dry-run",
            )
            summary = read_csv(paths["review"] / "cross_cleaning_term_summary.csv")

        self.assertEqual(result.strict_unenforceable_glossary_rows, 1)
        self.assertEqual(result.strict_removed_segment_mismatch_rows, 0)
        self.assertEqual(summary[0]["strict_enforceability_reason"], "not_enforceable_in_segments")

    def test_strict_keeps_empirically_stable_term_and_removes_mismatch_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_glossary(paths["glossary"], [("1", "道具", "아이템")])
            write_segments(
                paths["segments"],
                [
                    ("1", "使用道具", "아이템 사용"),
                    ("2", "道具不足", "아이템 부족"),
                    ("3", "获得道具", "아이템 획득"),
                    ("4", "道具说明", "아이템 설명"),
                    ("5", "购买道具", "물품 구매"),
                ],
            )

            result = cross.run_pipeline(
                paths["segments"],
                paths["glossary"],
                paths["rules"],
                paths["glossary_config"],
                paths["review"],
                mode="strict-dry-run",
            )
            summary = read_csv(paths["review"] / "cross_cleaning_term_summary.csv")

        self.assertEqual(result.strict_unenforceable_glossary_rows, 0)
        self.assertEqual(result.strict_removed_segment_mismatch_rows, 1)
        self.assertEqual(summary[0]["strict_enforceability_reason"], "empirical_stable_translation")


def make_project(tmp: str) -> dict[str, Path]:
    root = Path(tmp)
    glossary_config = root / "configs" / "glossary"
    glossary_config.mkdir(parents=True)
    review = root / "review"
    rules = root / "rules.json"
    rules.write_text(
        json.dumps(
            {
                "thresholds": {
                    "min_term_occurrences": 3,
                    "glossary_noise_missing_rate": 0.65,
                    "segment_conflict_missing_rate_max": 0.6,
                    "segment_conflict_preserved_min": 3,
                    "strong_domain_score_min": 0.65,
                    "weak_score_min": 0.85,
                    "strict_unenforceable_missing_rate": 0.85,
                    "strict_unenforceable_high_missing_rate": 0.95,
                    "domain_enforce_missing_rate_max": 0.6,
                    "domain_enforce_preserved_min": 3,
                    "empirical_enforce_preserved_min": 3,
                    "empirical_enforce_preserved_rate_min": 0.8,
                },
                "scores": {
                    "domain_anchor": 0.9,
                    "game_seed": 0.85,
                    "acronym": 0.9,
                    "noun_suffix": 0.65,
                    "compound_suffix": 0.7,
                    "length_four_plus": 0.35,
                    "length_six_plus": 0.5,
                    "weak_exact": 1.0,
                    "short_weak": 0.6,
                    "common_word": 0.85,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_term_file(glossary_config / "general_words_zh.txt", ["今日"])
    write_term_file(glossary_config / "common_nouns_zh.txt", ["月亮"])
    write_term_file(glossary_config / "nonterm_exact.txt", ["今日"])
    write_term_file(glossary_config / "game_anchors.txt", ["技能", "副本", "传送", "伤害"])
    write_term_file(glossary_config / "game_term_seeds.txt", ["技能", "传送", "造成伤害"])
    write_term_file(glossary_config / "acronym_whitelist.txt", ["BOSS"])
    write_term_file(glossary_config / "noun_suffixes.txt", ["技能", "副本"])
    write_term_file(glossary_config / "compound_suffixes.txt", ["宝箱"])
    return {
        "segments": root / "segments.csv",
        "glossary": root / "glossary.csv",
        "rules": rules,
        "glossary_config": glossary_config,
        "review": review,
    }


def write_term_file(path: Path, values: list[str]) -> None:
    path.write_text("\n".join(values) + "\n", encoding="utf-8")


def write_glossary(path: Path, rows: list[tuple[str, str, str]]) -> None:
    write_csv(path, ["term_id", "zh-CN", "ko"], rows)


def write_segments(path: Path, rows: list[tuple[str, str, str]]) -> None:
    write_csv(path, ["segment_id", "zh-CN", "ko"], rows)


def write_csv(path: Path, fieldnames: list[str], rows: list[tuple[str, str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(fieldnames)
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    unittest.main()
