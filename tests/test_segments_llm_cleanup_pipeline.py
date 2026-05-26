from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import segments_llm_cleanup_pipeline as segments_llm  # noqa: E402


class SegmentsLlmCleanupTest(unittest.TestCase):
    def test_apply_removes_rewrites_and_keeps_continuous_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_segments(
                paths["segments"],
                [
                    ("1", "暴击伤害", "치명타 피해"),
                    ("2", "六壬秘境85级", "六壬秘境85级"),
                    ("3", "技能升级", "기술 강화"),
                ],
            )
            write_glossary(paths["glossary"], [("1", "技能", "스킬")])
            client = StaticClient(
                {
                    "1": ("KEEP_SEGMENT", "good pair", ""),
                    "2": ("REMOVE_TARGET_CONTAMINATION", "target contains Chinese", ""),
                    "3": ("REWRITE_KO", "terminology fix", "스킬 강화"),
                }
            )

            result = segments_llm.run_cleanup(
                segments_path=paths["segments"],
                glossary_path=paths["glossary"],
                review_dir=paths["review"],
                apply_changes=True,
                env=valid_env(),
                client=client,
            )
            output = read_csv(paths["segments"])
            rewritten = read_csv(paths["review"] / "rewritten_segments_llm.csv")
            removed = read_csv(paths["review"] / "removed_segments_llm.csv")

        self.assertEqual(result.output_rows, 2)
        self.assertEqual(result.removed_rows, 1)
        self.assertEqual(result.rewritten_rows, 1)
        self.assertEqual([row["segment_id"] for row in output], ["1", "2"])
        self.assertEqual(output[1]["zh-CN"], "技能升级")
        self.assertEqual(output[1]["ko"], "스킬 강화")
        self.assertEqual(rewritten[0]["original_segment_id"], "3")
        self.assertEqual(removed[0]["original_segment_id"], "2")

    def test_rewrite_missing_placeholder_is_rejected_and_keeps_original(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_segments(paths["segments"], [("1", "挑战次数:{0}", "도전 횟수: {0}")])
            write_glossary(paths["glossary"], [("1", "挑战", "도전")])
            client = StaticClient({"1": ("REWRITE_KO", "bad placeholder", "도전 횟수")})

            result = segments_llm.run_cleanup(
                segments_path=paths["segments"],
                glossary_path=paths["glossary"],
                review_dir=paths["review"],
                apply_changes=True,
                env=valid_env(),
                client=client,
            )
            output = read_csv(paths["segments"])
            failed = read_csv(paths["review"] / "rewrite_failed_segments_llm.csv")

        self.assertEqual(result.rewrite_failed_rows, 1)
        self.assertEqual(result.removed_rows, 0)
        self.assertEqual(output[0]["ko"], "도전 횟수: {0}")
        self.assertIn("placeholder_missing", failed[0]["validation_errors"])

    def test_rewrite_missing_glossary_term_is_rejected(self) -> None:
        row = segments_llm.SegmentRow("1", "技能升级", "기술 강화")
        features = segments_llm.SegmentFeatures(
            placeholders=[],
            glossary_terms=[segments_llm.GlossaryTerm("1", "技能", "스킬")],
            target_contamination=False,
            structured_hint=False,
        )

        errors = segments_llm.validate_rewrite(row, "기술 강화", features)

        self.assertIn("glossary_term_missing", errors)

    def test_rewrite_extra_placeholder_is_rejected(self) -> None:
        row = segments_llm.SegmentRow("1", "挑战次数", "도전 횟수")
        features = segments_llm.SegmentFeatures(
            placeholders=[],
            glossary_terms=[],
            target_contamination=False,
            structured_hint=False,
        )

        errors = segments_llm.validate_rewrite(row, "도전 횟수 {0}", features)

        self.assertIn("placeholder_extra", errors)

    def test_contaminated_rewrite_failure_removes_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_segments(paths["segments"], [("1", "六壬秘境85级", "六壬秘境85级")])
            write_glossary(paths["glossary"], [("1", "秘境", "비경")])
            client = StaticClient({"1": ("REWRITE_KO", "bad rewrite", "六壬秘境85级")})

            result = segments_llm.run_cleanup(
                segments_path=paths["segments"],
                glossary_path=paths["glossary"],
                review_dir=paths["review"],
                apply_changes=True,
                env=valid_env(),
                client=client,
            )
            output = read_csv(paths["segments"])

        self.assertEqual(result.removed_rows, 1)
        self.assertEqual(output, [])

    def test_missing_environment_fails_before_writing_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_segments(paths["segments"], [("1", "技能升级", "스킬 강화")])
            write_glossary(paths["glossary"], [("1", "技能", "스킬")])

            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                segments_llm.run_cleanup(
                    segments_path=paths["segments"],
                    glossary_path=paths["glossary"],
                    review_dir=paths["review"],
                    apply_changes=True,
                    env={},
                    client=StaticClient({"1": ("KEEP_SEGMENT", "good pair", "")}),
                )

            self.assertFalse(paths["review"].exists())

    def test_invalid_action_is_rejected(self) -> None:
        response = response_for(
            [{"segment_id": "1", "action": "KEEP", "reason": "bad", "corrected_ko": ""}]
        )
        batch = [segments_llm.SegmentRow("1", "技能升级", "스킬 강화")]

        with self.assertRaisesRegex(RuntimeError, "Invalid action"):
            segments_llm.parse_and_validate_response(response, batch)

    def test_missing_row_retries_whole_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_segments(
                paths["segments"],
                [("1", "技能升级", "스킬 강화"), ("2", "暴击伤害", "치명타 피해")],
            )
            write_glossary(paths["glossary"], [("1", "技能", "스킬")])
            client = RetryClient(
                [
                    response_for(
                        [
                            {
                                "segment_id": "1",
                                "action": "KEEP_SEGMENT",
                                "reason": "good",
                                "corrected_ko": "",
                            }
                        ]
                    ),
                    response_for(
                        [
                            {
                                "segment_id": "1",
                                "action": "KEEP_SEGMENT",
                                "reason": "good",
                                "corrected_ko": "",
                            },
                            {
                                "segment_id": "2",
                                "action": "KEEP_SEGMENT",
                                "reason": "good",
                                "corrected_ko": "",
                            },
                        ]
                    ),
                ]
            )

            result = segments_llm.run_cleanup(
                segments_path=paths["segments"],
                glossary_path=paths["glossary"],
                review_dir=paths["review"],
                apply_changes=False,
                batch_size=2,
                max_retries=2,
                env=valid_env(),
                client=client,
            )

        self.assertEqual(client.calls, 2)
        self.assertEqual(result.kept_rows, 2)


class StaticClient:
    def __init__(self, actions: dict[str, tuple[str, str, str]]) -> None:
        self.actions = actions

    def __call__(
        self,
        payload: dict[str, Any],
        config: Any,
        temperature: float,
        timeout: int,
    ) -> dict[str, Any]:
        del config, temperature, timeout
        user_payload = json.loads(payload["messages"][1]["content"])
        results = []
        for row in user_payload["rows"]:
            action, reason, corrected_ko = self.actions[row["segment_id"]]
            results.append(
                {
                    "segment_id": row["segment_id"],
                    "action": action,
                    "reason": reason,
                    "corrected_ko": corrected_ko,
                }
            )
        return response_for(results, prompt_tokens=10, completion_tokens=5)


class RetryClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls = 0

    def __call__(
        self,
        payload: dict[str, Any],
        config: Any,
        temperature: float,
        timeout: int,
    ) -> dict[str, Any]:
        del payload, config, temperature, timeout
        response = self.responses[self.calls]
        self.calls += 1
        return response


def make_project(tmp: str) -> dict[str, Path]:
    root = Path(tmp)
    return {
        "segments": root / "segments.csv",
        "glossary": root / "glossary.csv",
        "review": root / "review",
    }


def valid_env() -> dict[str, str]:
    return {"OPENAI_API_KEY": "test-key", "LLM_MODEL": "test-model"}


def response_for(
    results: list[dict[str, str]], prompt_tokens: int = 0, completion_tokens: int = 0
) -> dict[str, Any]:
    return {
        "choices": [
            {"message": {"content": json.dumps({"results": results}, ensure_ascii=False)}}
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def write_segments(path: Path, rows: list[tuple[str, str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["segment_id", "zh-CN", "ko"])
        writer.writerows(rows)


def write_glossary(path: Path, rows: list[tuple[str, str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["term_id", "zh-CN", "ko"])
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    unittest.main()
