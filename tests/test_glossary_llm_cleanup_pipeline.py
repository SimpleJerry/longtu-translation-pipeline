from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from longtu_translation_pipeline.cleanup.glossary_llm import (
    models,
    pipeline,
    prompts,
)
from longtu_translation_pipeline.cleanup.glossary_llm import response as resp


class GlossaryLlmCleanupTest(unittest.TestCase):
    def test_apply_rewrites_only_keep_rows_with_continuous_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            glossary = root / "glossary.csv"
            review = root / "review"
            write_glossary(
                glossary,
                [
                    ("1", "暴击", "치명타"),
                    ("2", "月亮", "달"),
                    ("3", "神秘宝箱", "신비한 보물상자"),
                ],
            )
            client = StaticClient(
                {
                    "1": ("KEEP_GAME_TERM", "combat attribute"),
                    "2": ("REMOVE_COMMON_WORD", "ordinary noun"),
                    "3": ("KEEP_GAME_TERM", "item name"),
                }
            )

            result = pipeline.run_cleanup(
                glossary_path=glossary,
                review_dir=review,
                apply_changes=True,
                batch_size=2,
                env=valid_env(),
                client=client,
            )

            output = read_csv(glossary)
            removed = read_csv(review / "removed_glossary_llm.csv")

        self.assertEqual(result.input_rows, 3)
        self.assertEqual(result.kept_rows, 2)
        self.assertEqual(result.removed_rows, 1)
        self.assertEqual([row["term_id"] for row in output], ["1", "2"])
        self.assertEqual({row["zh-CN"] for row in output}, {"暴击", "神秘宝箱"})
        self.assertEqual(removed[0]["original_term_id"], "2")

    def test_dry_run_does_not_rewrite_glossary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            glossary = root / "glossary.csv"
            review = root / "review"
            write_glossary(glossary, [("1", "月亮", "달")])
            before = glossary.read_text(encoding="utf-8-sig")

            pipeline.run_cleanup(
                glossary_path=glossary,
                review_dir=review,
                apply_changes=False,
                env=valid_env(),
                client=StaticClient({"1": ("REMOVE_COMMON_WORD", "ordinary noun")}),
            )

            after = glossary.read_text(encoding="utf-8-sig")

        self.assertEqual(after, before)

    def test_missing_environment_fails_before_writing_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            glossary = root / "glossary.csv"
            review = root / "review"
            write_glossary(glossary, [("1", "暴击", "치명타")])

            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                pipeline.run_cleanup(
                    glossary_path=glossary,
                    review_dir=review,
                    apply_changes=True,
                    env={},
                    client=StaticClient({"1": ("KEEP_GAME_TERM", "game term")}),
                )

            self.assertFalse(review.exists())

    def test_missing_model_fails_before_writing_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            glossary = root / "glossary.csv"
            review = root / "review"
            write_glossary(glossary, [("1", "暴击", "치명타")])

            with self.assertRaisesRegex(RuntimeError, "LLM_MODEL"):
                pipeline.run_cleanup(
                    glossary_path=glossary,
                    review_dir=review,
                    apply_changes=True,
                    env={"OPENAI_API_KEY": "key"},
                    client=StaticClient({"1": ("KEEP_GAME_TERM", "game term")}),
                )

            self.assertFalse(review.exists())

    def test_invalid_action_is_rejected(self) -> None:
        response = response_for(
            [{"term_id": "1", "action": "KEEP", "reason": "bad action"}]
        )
        batch = [models.GlossaryRow("1", "暴击", "치명타")]

        with self.assertRaisesRegex(RuntimeError, "Invalid action"):
            resp.parse_and_validate_response(response, batch)

    def test_missing_row_retries_whole_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            glossary = root / "glossary.csv"
            review = root / "review"
            write_glossary(glossary, [("1", "暴击", "치명타"), ("2", "月亮", "달")])
            client = RetryClient(
                [
                    response_for(
                        [
                            {
                                "term_id": "1",
                                "action": "KEEP_GAME_TERM",
                                "reason": "game term",
                            }
                        ]
                    ),
                    response_for(
                        [
                            {
                                "term_id": "1",
                                "action": "KEEP_GAME_TERM",
                                "reason": "game term",
                            },
                            {
                                "term_id": "2",
                                "action": "REMOVE_COMMON_WORD",
                                "reason": "ordinary noun",
                            },
                        ]
                    ),
                ]
            )

            result = pipeline.run_cleanup(
                glossary_path=glossary,
                review_dir=review,
                apply_changes=False,
                batch_size=2,
                max_retries=2,
                env=valid_env(),
                client=client,
            )

        self.assertEqual(client.calls, 2)
        self.assertEqual(result.removed_rows, 1)

    def test_duplicate_row_is_rejected(self) -> None:
        response = response_for(
            [
                {"term_id": "1", "action": "KEEP_GAME_TERM", "reason": "game term"},
                {
                    "term_id": "1",
                    "action": "REMOVE_COMMON_WORD",
                    "reason": "duplicate",
                },
            ]
        )
        batch = [models.GlossaryRow("1", "暴击", "치명타")]

        with self.assertRaisesRegex(RuntimeError, "Duplicate term_id"):
            resp.parse_and_validate_response(response, batch)

    def test_json_wrapped_in_text_is_accepted(self) -> None:
        response = {
            "choices": [
                {
                    "message": {
                        "content": 'Here is JSON:\n{"results":[{"term_id":"1","action":"KEEP_GAME_TERM","reason":"game term"}]}'
                    }
                }
            ]
        }
        batch = [models.GlossaryRow("1", "暴击", "치명타")]

        decisions = resp.parse_and_validate_response(response, batch)

        self.assertEqual(decisions[0].action, "KEEP_GAME_TERM")


class GlossaryLlmBatchModeTest(unittest.TestCase):
    def test_payload_includes_response_format_and_max_tokens(self) -> None:
        payload = prompts.build_request_payload(
            "gpt-4.1-mini",
            [models.GlossaryRow("1", "暴击", "치명타")],
            temperature=0.0,
            max_output_tokens=1500,
        )
        self.assertEqual(payload["parallel_tool_calls"], False)
        self.assertEqual(payload["max_tokens"], 1500)
        rf = payload["response_format"]
        self.assertEqual(rf["type"], "json_schema")
        self.assertTrue(rf["json_schema"]["strict"])
        self.assertEqual(
            set(rf["json_schema"]["schema"]["properties"]["results"]["items"]
                  ["properties"]["action"]["enum"]),
            set(models.VALID_ACTIONS),
        )

    def test_end_to_end_batch_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            glossary = root / "glossary.csv"
            review = root / "review"
            write_glossary(
                glossary,
                [("1", "暴击", "치명타"), ("2", "月亮", "달"), ("3", "神秘宝箱", "신비한 보물상자")],
            )

            recorded: dict[str, Any] = {}

            def fake_upload(jsonl_path, cfg, timeout=600):
                recorded["uploaded_bytes"] = Path(jsonl_path).read_bytes()
                return "file_g"

            def fake_create(file_id, cfg, *, endpoint="/v1/chat/completions",
                            completion_window="24h", metadata=None, timeout=60):
                recorded["metadata"] = metadata
                return "batch_g"

            def fake_wait(*a, **k):
                if k.get("progress_cb"):
                    k["progress_cb"]({"status": "completed"})
                return {"status": "completed", "output_file_id": "file_g_out"}

            def fake_download(output_file_id, cfg, dest_path, timeout=600):
                results = [
                    {"term_id": "1", "action": "KEEP_GAME_TERM", "reason": "combat"},
                    {"term_id": "2", "action": "REMOVE_COMMON_WORD", "reason": "ordinary"},
                    {"term_id": "3", "action": "KEEP_GAME_TERM", "reason": "item"},
                ]
                body = {
                    "choices": [{"message": {"content": json.dumps({"results": results})}}],
                    "usage": {"prompt_tokens": 200, "completion_tokens": 60,
                              "total_tokens": 260},
                }
                line = {"custom_id": "glo-batch-0001",
                        "response": {"status_code": 200, "body": body}, "error": None}
                Path(dest_path).write_text(json.dumps(line) + "\n", encoding="utf-8")
                return {"glo-batch-0001": line}

            with patch.object(pipeline,"upload_batch_input_file", fake_upload), \
                 patch.object(pipeline,"create_batch", fake_create), \
                 patch.object(pipeline,"wait_for_batch", fake_wait), \
                 patch.object(pipeline,"download_batch_output", fake_download):
                result = pipeline.run_cleanup(
                    glossary_path=glossary,
                    review_dir=review,
                    apply_changes=True,
                    batch_mode="batch",
                    batch_size=50,
                    env=valid_env(),
                )

            output = read_csv(glossary)
            self.assertEqual([row["term_id"] for row in output], ["1", "2"])
            self.assertEqual(result.kept_rows, 2)
            self.assertEqual(result.removed_rows, 1)
            self.assertEqual(result.total_prompt_tokens, 200)
            uploaded = recorded["uploaded_bytes"].decode("utf-8").strip().splitlines()
            self.assertEqual(len(uploaded), 1)
            first = json.loads(uploaded[0])
            self.assertEqual(first["custom_id"], "glo-batch-0001")
            self.assertEqual(first["body"]["response_format"]["type"], "json_schema")
            self.assertEqual(recorded["metadata"],
                             {"source": "glossary_llm_cleanup_pipeline"})
            state = json.loads((review / "batch_state.json").read_text("utf-8"))
            self.assertEqual(state["phase"], "downloaded")


class StaticClient:
    def __init__(self, actions: dict[str, tuple[str, str]]) -> None:
        self.actions = actions

    def __call__(
        self,
        payload: dict[str, Any],
        config: models.ClientConfig,
        temperature: float,
        timeout: int,
    ) -> dict[str, Any]:
        del config, temperature, timeout
        user_payload = json.loads(payload["messages"][1]["content"])
        results = []
        for row in user_payload["rows"]:
            action, reason = self.actions[row["term_id"]]
            results.append(
                {"term_id": row["term_id"], "action": action, "reason": reason}
            )
        return response_for(results, prompt_tokens=10, completion_tokens=5)


class RetryClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls = 0

    def __call__(
        self,
        payload: dict[str, Any],
        config: models.ClientConfig,
        temperature: float,
        timeout: int,
    ) -> dict[str, Any]:
        del payload, config, temperature, timeout
        response = self.responses[self.calls]
        self.calls += 1
        return response


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
