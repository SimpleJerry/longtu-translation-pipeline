from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import segments_llm_cleanup_pipeline as segments_llm  # noqa: E402


class SegmentsLlmCleanupTest(unittest.TestCase):
    def test_payload_excludes_local_prejudgment_fields(self) -> None:
        payload = segments_llm.build_request_payload(
            model="test-model",
            batch=[segments_llm.SegmentRow("1", "六壬秘境85级", "六壬秘境85级")],
            glossary_sorted=[segments_llm.GlossaryTerm("1", "秘境", "비경")],
            temperature=0.0,
        )
        user_payload = json.loads(payload["messages"][1]["content"])
        row = user_payload["rows"][0]

        self.assertEqual(row["segment_id"], "1")
        self.assertIn("placeholder_tokens", row)
        self.assertIn("glossary_terms", row)
        self.assertNotIn("target_contamination", row)
        self.assertNotIn("structured_hint", row)

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

    def test_invalid_action_falls_back_to_review_uncertain(self) -> None:
        """Since cdfa1b6 (RF-029 follow-up), parse_and_validate_response degrades
        gracefully: an unrecognised action no longer raises RuntimeError; it
        emits a warning and replaces the decision with REVIEW_UNCERTAIN so the
        rest of the batch survives. This was discovered during the real T-A1
        full-corpus run, where truncated outputs occasionally mangled an action
        token and the strict-raise behaviour killed the whole micro-batch."""
        response = response_for(
            [{"segment_id": "1", "action": "KEEP", "reason": "bad", "corrected_ko": ""}]
        )
        batch = [segments_llm.SegmentRow("1", "技能升级", "스킬 강화")]

        decisions = segments_llm.parse_and_validate_response(response, batch)

        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].segment_id, "1")
        self.assertEqual(decisions[0].action, segments_llm.REVIEW_ACTION)

    def test_missing_row_falls_back_to_review_uncertain(self) -> None:
        """Since cdfa1b6 (RF-029 follow-up), a missing segment_id no longer
        triggers a whole-batch retry. The single missing row is filled with a
        REVIEW_UNCERTAIN placeholder and the run continues; the retry loop
        therefore makes exactly one call. The user-visible cost is one
        REVIEW_UNCERTAIN row instead of N×max_retries duplicate batches when
        the upstream truncates."""
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

        self.assertEqual(client.calls, 1)
        self.assertEqual(result.kept_rows, 1)
        self.assertEqual(result.review_rows, 1)

    def test_repeated_reason_writes_warning_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_segments(
                paths["segments"],
                [(str(index), f"测试文本{index}", f"테스트 문장 {index}") for index in range(1, 6)],
            )
            write_glossary(paths["glossary"], [("1", "测试", "테스트")])
            client = StaticClient(
                {
                    str(index): ("KEEP_SEGMENT", "valid training pair", "")
                    for index in range(1, 6)
                }
            )

            segments_llm.run_cleanup(
                segments_path=paths["segments"],
                glossary_path=paths["glossary"],
                review_dir=paths["review"],
                apply_changes=False,
                batch_size=5,
                env=valid_env(),
                client=client,
            )
            summary = read_metric_csv(paths["review"] / "segments_llm_summary.csv")
            warnings = read_csv(paths["review"] / "segments_llm_warnings.csv")

        self.assertEqual(summary["reason_repetition_warning_batches"], "1")
        self.assertEqual(summary["max_reason_repetition_count"], "5")
        self.assertEqual(warnings[0]["warning_type"], "batch_reason_repetition_warning")

    def test_review_uncertain_keeps_original_and_writes_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_segments(paths["segments"], [("1", "帮派红包", "길드 보상")])
            write_glossary(paths["glossary"], [("1", "帮派", "길드")])
            client = StaticClient(
                {
                    "1": (
                        "REVIEW_UNCERTAIN",
                        "Korean may be too free for this source",
                        "",
                    )
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
            sample = read_csv(paths["review"] / "segments_llm_sample_review.csv")

        self.assertEqual(result.review_rows, 1)
        self.assertEqual(output[0]["ko"], "길드 보상")
        self.assertEqual(sample[0]["final_action"], "REVIEW")
        self.assertEqual(sample[0]["original_segment_id"], "1")


class SegmentsLlmBatchModeTest(unittest.TestCase):
    """End-to-end batch path tests with all Batch API calls mocked.

    These tests verify that:
      (1) `build_request_payload` now emits `response_format` (json_schema
          strict) and `max_tokens` (parallel_tool_calls was dropped in
          cdfa1b6 because Batch API rejects it when no tools are used).
      (2) `run_batch_path` writes the input JSONL with one line per
          micro-batch keyed by `seg-batch-NNNN`.
      (3) State transitions through init → input_written → uploaded →
          submitted → completed → downloaded, persisted in
          `batch_state.json` atomically.
      (4) Resumption: if `batch_state.json` already shows the batch is
          submitted, we do not re-upload nor re-create the batch.
    """

    def test_payload_includes_response_format_and_max_tokens(self) -> None:
        payload = segments_llm.build_request_payload(
            model="gpt-4.1-mini",
            batch=[segments_llm.SegmentRow("1", "技能", "스킬")],
            glossary_sorted=[],
            temperature=0.0,
            max_output_tokens=2250,
        )
        # parallel_tool_calls was dropped in cdfa1b6: Batch API rejects it
        # when no tools are specified, and sync API silently ignored it.
        self.assertNotIn("parallel_tool_calls", payload)
        self.assertEqual(payload["max_tokens"], 2250)
        rf = payload["response_format"]
        self.assertEqual(rf["type"], "json_schema")
        self.assertTrue(rf["json_schema"]["strict"])
        schema_props = rf["json_schema"]["schema"]["properties"]["results"]["items"]["properties"]
        self.assertIn("segment_id", schema_props)
        self.assertIn("corrected_ko", schema_props)
        # Action enum reflects the live VALID_ACTIONS set.
        self.assertEqual(
            set(schema_props["action"]["enum"]),
            set(segments_llm.VALID_ACTIONS),
        )

    def test_payload_omits_max_tokens_when_unset(self) -> None:
        payload = segments_llm.build_request_payload(
            model="m",
            batch=[segments_llm.SegmentRow("1", "x", "x")],
            glossary_sorted=[],
            temperature=0.0,
        )
        self.assertNotIn("max_tokens", payload)

    def test_end_to_end_batch_path_writes_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_segments(
                paths["segments"],
                [
                    ("1", "暴击伤害", "치명타 피해"),
                    ("2", "技能升级", "기술 강화"),
                    ("3", "六壬秘境85级", "六壬秘境85级"),
                ],
            )
            write_glossary(paths["glossary"], [("1", "技能", "스킬")])

            recorded: dict[str, Any] = {}

            def fake_upload(jsonl_path, cfg, timeout=600):
                recorded["uploaded_path"] = Path(jsonl_path)
                recorded["uploaded_bytes"] = Path(jsonl_path).read_bytes()
                return "file_abc"

            def fake_create(file_id, cfg, *, endpoint="/v1/chat/completions",
                            completion_window="24h", metadata=None, timeout=60):
                recorded["created_for"] = file_id
                recorded["completion_window"] = completion_window
                recorded["metadata"] = metadata
                return "batch_xyz"

            def fake_wait(batch_id, cfg, *, poll_interval_sec=60,
                          max_wait_sec=24*3600, progress_cb=None,
                          sleep_fn=None, now_fn=None, timeout=60):
                if progress_cb:
                    progress_cb({"status": "in_progress"})
                    progress_cb({"status": "completed"})
                return {"id": batch_id, "status": "completed",
                        "output_file_id": "file_out"}

            def fake_download(output_file_id, cfg, dest_path, timeout=600):
                # Produce one line per micro-batch in the expected output shape.
                actions = {
                    "1": ("KEEP_SEGMENT", "good pair", ""),
                    "2": ("REWRITE_KO", "terminology fix", "스킬 강화"),
                    "3": ("REMOVE_TARGET_CONTAMINATION", "ko mirrors zh", ""),
                }
                # batch_size=50 puts all 3 rows in one micro-batch.
                results = [
                    {"segment_id": sid, "action": a, "reason": r, "corrected_ko": ck}
                    for sid, (a, r, ck) in actions.items()
                ]
                body = {
                    "choices": [{"message": {"content": json.dumps({"results": results})}}],
                    "usage": {"prompt_tokens": 700, "completion_tokens": 250,
                              "total_tokens": 950},
                }
                line = {
                    "custom_id": "seg-batch-0001",
                    "response": {"status_code": 200, "body": body},
                    "error": None,
                }
                Path(dest_path).write_text(json.dumps(line) + "\n", encoding="utf-8")
                return {"seg-batch-0001": line}

            with patch.object(segments_llm, "upload_batch_input_file", fake_upload), \
                 patch.object(segments_llm, "create_batch", fake_create), \
                 patch.object(segments_llm, "wait_for_batch", fake_wait), \
                 patch.object(segments_llm, "download_batch_output", fake_download):
                result = segments_llm.run_cleanup(
                    segments_path=paths["segments"],
                    glossary_path=paths["glossary"],
                    review_dir=paths["review"],
                    apply_changes=True,
                    batch_mode="batch",
                    batch_size=50,
                    max_output_tokens=2250,
                    env=valid_env(),
                )

            # Output segments rewritten: row 3 removed, row 2 ko corrected.
            output = read_csv(paths["segments"])
            self.assertEqual([row["segment_id"] for row in output], ["1", "2"])
            self.assertEqual(output[1]["ko"], "스킬 강화")

            # Result counts.
            self.assertEqual(result.input_rows, 3)
            self.assertEqual(result.kept_rows, 1)
            self.assertEqual(result.rewritten_rows, 1)
            self.assertEqual(result.removed_rows, 1)
            self.assertEqual(result.total_prompt_tokens, 700)
            self.assertEqual(result.total_completion_tokens, 250)

            # JSONL input was written and uploaded.
            self.assertTrue((paths["review"] / "batch_input" / "all.jsonl").is_file())
            uploaded = recorded["uploaded_bytes"].decode("utf-8").strip().splitlines()
            self.assertEqual(len(uploaded), 1)
            first = json.loads(uploaded[0])
            self.assertEqual(first["custom_id"], "seg-batch-0001")
            self.assertEqual(first["url"], "/v1/chat/completions")
            self.assertEqual(first["body"]["model"], "test-model")
            self.assertEqual(first["body"]["max_tokens"], 2250)
            # parallel_tool_calls intentionally absent (cdfa1b6).
            self.assertNotIn("parallel_tool_calls", first["body"])
            self.assertEqual(first["body"]["response_format"]["type"], "json_schema")
            self.assertEqual(recorded["created_for"], "file_abc")
            self.assertEqual(recorded["completion_window"], "24h")
            self.assertEqual(recorded["metadata"], {"source": "segments_llm_cleanup_pipeline"})

            # Final state file recorded the completed transition.
            state = json.loads((paths["review"] / "batch_state.json").read_text("utf-8"))
            self.assertEqual(state["phase"], "downloaded")
            self.assertEqual(state["batch_id"], "batch_xyz")
            self.assertEqual(state["output_file_id"], "file_out")

    def test_resumes_from_existing_downloaded_state(self) -> None:
        """If batch_state.json says phase=downloaded and the result.jsonl
        exists, we must NOT re-upload, re-create, re-wait, or re-download."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_segments(paths["segments"], [("1", "技能", "스킬"), ("2", "暴击", "치명타")])
            write_glossary(paths["glossary"], [("1", "技能", "스킬")])

            review_dir = paths["review"]
            (review_dir / "batch_output").mkdir(parents=True)
            (review_dir / "batch_input").mkdir(parents=True)
            # Seed a downloaded result file matching micro-batch keys.
            results = [
                {"segment_id": "1", "action": "KEEP_SEGMENT", "reason": "ok", "corrected_ko": ""},
                {"segment_id": "2", "action": "KEEP_SEGMENT", "reason": "ok", "corrected_ko": ""},
            ]
            body = {
                "choices": [{"message": {"content": json.dumps({"results": results})}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130},
            }
            line = {"custom_id": "seg-batch-0001",
                    "response": {"status_code": 200, "body": body}, "error": None}
            (review_dir / "batch_output" / "result.jsonl").write_text(
                json.dumps(line) + "\n", encoding="utf-8"
            )
            (review_dir / "batch_state.json").write_text(
                json.dumps({"phase": "downloaded", "batch_id": "old_batch",
                            "input_file_id": "old_file", "output_file_id": "file_out"}),
                encoding="utf-8",
            )

            calls: dict[str, int] = {"upload": 0, "create": 0, "wait": 0, "download": 0}

            def fail_upload(*a, **k):
                calls["upload"] += 1
                raise AssertionError("must not re-upload when resuming downloaded state")

            def fail_create(*a, **k):
                calls["create"] += 1
                raise AssertionError("must not re-create batch when resuming")

            def fail_wait(*a, **k):
                calls["wait"] += 1
                raise AssertionError("must not re-wait when resuming")

            def fail_download(*a, **k):
                calls["download"] += 1
                raise AssertionError("must not re-download when resuming")

            with patch.object(segments_llm, "upload_batch_input_file", fail_upload), \
                 patch.object(segments_llm, "create_batch", fail_create), \
                 patch.object(segments_llm, "wait_for_batch", fail_wait), \
                 patch.object(segments_llm, "download_batch_output", fail_download):
                result = segments_llm.run_cleanup(
                    segments_path=paths["segments"],
                    glossary_path=paths["glossary"],
                    review_dir=review_dir,
                    apply_changes=False,
                    batch_mode="batch",
                    batch_size=50,
                    env=valid_env(),
                )
            self.assertEqual(calls, {"upload": 0, "create": 0, "wait": 0, "download": 0})
            self.assertEqual(result.kept_rows, 2)
            self.assertEqual(result.total_prompt_tokens, 100)

    def test_batch_line_with_error_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_project(tmp)
            write_segments(paths["segments"], [("1", "x", "x")])
            write_glossary(paths["glossary"], [("1", "x", "x")])

            def fake_upload(*a, **k): return "file_abc"
            def fake_create(*a, **k): return "batch_x"
            def fake_wait(*a, **k):
                return {"status": "completed", "output_file_id": "file_out"}
            def fake_download(output_file_id, cfg, dest_path, timeout=600):
                line = {"custom_id": "seg-batch-0001", "response": None,
                        "error": {"code": "rate_limited", "message": "too fast"}}
                Path(dest_path).write_text(json.dumps(line) + "\n", encoding="utf-8")
                return {"seg-batch-0001": line}

            with patch.object(segments_llm, "upload_batch_input_file", fake_upload), \
                 patch.object(segments_llm, "create_batch", fake_create), \
                 patch.object(segments_llm, "wait_for_batch", fake_wait), \
                 patch.object(segments_llm, "download_batch_output", fake_download):
                with self.assertRaisesRegex(RuntimeError, "rate_limited"):
                    segments_llm.run_cleanup(
                        segments_path=paths["segments"],
                        glossary_path=paths["glossary"],
                        review_dir=paths["review"],
                        apply_changes=False,
                        batch_mode="batch",
                        batch_size=50,
                        env=valid_env(),
                    )


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


def read_metric_csv(path: Path) -> dict[str, str]:
    return {row["metric"]: row["value"] for row in read_csv(path)}


if __name__ == "__main__":
    unittest.main()
