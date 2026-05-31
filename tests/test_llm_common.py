from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.llm import client as llm_common  # noqa: E402


CFG = llm_common.ClientConfig(api_key="test-key", base_url="https://api.test/v1", model="gpt-test")


def _fake_urlopen(payload: Any, *, status: int = 200) -> MagicMock:
    """Build a context-manager-compatible mock for urllib.request.urlopen."""
    body = payload if isinstance(payload, (bytes, bytearray)) else json.dumps(payload).encode("utf-8")
    response = MagicMock()
    response.read.return_value = body
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    return response


def _http_error(code: int, body: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="http://x", code=code, msg="err", hdrs=None, fp=io.BytesIO(body.encode("utf-8"))
    )


class ResolveClientConfigTest(unittest.TestCase):
    def test_raises_when_api_key_missing(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
            llm_common.resolve_client_config({"LLM_MODEL": "gpt-4"})

    def test_raises_when_api_key_empty(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
            llm_common.resolve_client_config({"OPENAI_API_KEY": "  ", "LLM_MODEL": "gpt-4"})

    def test_raises_when_model_missing(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "LLM_MODEL"):
            llm_common.resolve_client_config({"OPENAI_API_KEY": "test-key"})

    def test_raises_when_model_empty(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "LLM_MODEL"):
            llm_common.resolve_client_config({"OPENAI_API_KEY": "test-key", "LLM_MODEL": ""})

    def test_returns_config_with_required_fields(self) -> None:
        config = llm_common.resolve_client_config(
            {"OPENAI_API_KEY": "my-key", "LLM_MODEL": "gpt-4o"}
        )
        self.assertEqual(config.api_key, "my-key")
        self.assertEqual(config.model, "gpt-4o")
        self.assertEqual(config.base_url, "https://api.openai.com/v1")

    def test_base_url_override_takes_precedence(self) -> None:
        config = llm_common.resolve_client_config(
            {"OPENAI_API_KEY": "k", "LLM_MODEL": "m", "OPENAI_BASE_URL": "http://env/v1"},
            base_url_override="http://override/v1",
        )
        self.assertEqual(config.base_url, "http://override/v1")

    def test_trailing_slash_stripped_from_base_url(self) -> None:
        config = llm_common.resolve_client_config(
            {"OPENAI_API_KEY": "k", "LLM_MODEL": "m", "OPENAI_BASE_URL": "http://host/v1/"}
        )
        self.assertEqual(config.base_url, "http://host/v1")

    def test_model_override_takes_precedence(self) -> None:
        config = llm_common.resolve_client_config(
            {"OPENAI_API_KEY": "k", "LLM_MODEL": "env-model"},
            model_override="override-model",
        )
        self.assertEqual(config.model, "override-model")


class ParseJsonContentTest(unittest.TestCase):
    def test_accepts_plain_json(self) -> None:
        result = llm_common.parse_json_content('{"results": []}')
        self.assertEqual(result, {"results": []})

    def test_accepts_json_in_backtick_fences(self) -> None:
        content = '```json\n{"results": [{"id": "1"}]}\n```'
        result = llm_common.parse_json_content(content)
        self.assertEqual(result["results"][0]["id"], "1")

    def test_accepts_json_wrapped_in_prose(self) -> None:
        content = 'Here is the output:\n{"results": []} done.'
        result = llm_common.parse_json_content(content)
        self.assertEqual(result, {"results": []})

    def test_raises_on_non_json_content(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "not JSON"):
            llm_common.parse_json_content("this is just plain text with no braces")

    def test_raises_on_malformed_json(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "could not be parsed"):
            llm_common.parse_json_content("{bad: json content here}")

    def test_raises_when_result_is_not_object(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "JSON object"):
            llm_common.parse_json_content("[1, 2, 3]")


class ClientConfigTest(unittest.TestCase):
    def test_is_frozen(self) -> None:
        config = llm_common.ClientConfig(api_key="k", base_url="http://x", model="m")
        with self.assertRaises((AttributeError, TypeError)):
            config.api_key = "other"  # type: ignore[misc]

    def test_fields(self) -> None:
        config = llm_common.ClientConfig(api_key="k", base_url="http://x", model="m")
        self.assertEqual(config.api_key, "k")
        self.assertEqual(config.base_url, "http://x")
        self.assertEqual(config.model, "m")


class BuildBatchRequestLineTest(unittest.TestCase):
    def test_wraps_payload(self) -> None:
        line = llm_common.build_batch_request_line(
            "seg-batch-0001", {"model": "m", "messages": [{"role": "user", "content": "hi"}]}
        )
        self.assertEqual(line["custom_id"], "seg-batch-0001")
        self.assertEqual(line["method"], "POST")
        self.assertEqual(line["url"], "/v1/chat/completions")
        self.assertEqual(line["body"]["model"], "m")

    def test_rejects_empty_custom_id(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "custom_id"):
            llm_common.build_batch_request_line("", {"model": "m"})

    def test_rejects_non_dict_payload(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "chat_payload"):
            llm_common.build_batch_request_line("c", "not a dict")  # type: ignore[arg-type]


class UploadBatchInputFileTest(unittest.TestCase):
    def test_uploads_and_returns_file_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jsonl = Path(tmp) / "in.jsonl"
            jsonl.write_text('{"custom_id":"c1","method":"POST","url":"/v1/chat/completions","body":{}}\n', encoding="utf-8")
            with patch("longtu_translation_pipeline.llm.client.urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_urlopen({"id": "file_abc", "object": "file"})
                file_id = llm_common.upload_batch_input_file(jsonl, CFG)
            self.assertEqual(file_id, "file_abc")
            # Verify the Request used multipart/form-data and Authorization header.
            args, _ = mock_open.call_args
            request = args[0]
            self.assertEqual(request.method, "POST")
            self.assertIn("multipart/form-data; boundary=", request.headers["Content-type"])
            self.assertEqual(request.headers["Authorization"], "Bearer test-key")
            # Body must contain the purpose=batch field and the filename.
            self.assertIn(b'name="purpose"', request.data)
            self.assertIn(b"batch", request.data)
            self.assertIn(b'filename="in.jsonl"', request.data)

    def test_raises_when_jsonl_missing(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "not found"):
            llm_common.upload_batch_input_file(Path("/nonexistent/file.jsonl"), CFG)

    def test_raises_when_response_missing_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jsonl = Path(tmp) / "in.jsonl"
            jsonl.write_text("x\n", encoding="utf-8")
            with patch("longtu_translation_pipeline.llm.client.urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_urlopen({"object": "file"})
                with self.assertRaisesRegex(RuntimeError, "missing 'id'"):
                    llm_common.upload_batch_input_file(jsonl, CFG)

    def test_propagates_http_error_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jsonl = Path(tmp) / "in.jsonl"
            jsonl.write_text("x\n", encoding="utf-8")
            with patch("longtu_translation_pipeline.llm.client.urllib.request.urlopen", side_effect=_http_error(400, "bad purpose")):
                with self.assertRaisesRegex(RuntimeError, "HTTP 400.*bad purpose"):
                    llm_common.upload_batch_input_file(jsonl, CFG)


class CreateBatchTest(unittest.TestCase):
    def test_posts_batch_request_and_returns_id(self) -> None:
        with patch("longtu_translation_pipeline.llm.client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _fake_urlopen({"id": "batch_xyz", "status": "validating"})
            batch_id = llm_common.create_batch(
                "file_abc", CFG, completion_window="24h", metadata={"job": "t-a1"}
            )
        self.assertEqual(batch_id, "batch_xyz")
        request = mock_open.call_args[0][0]
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent["input_file_id"], "file_abc")
        self.assertEqual(sent["endpoint"], "/v1/chat/completions")
        self.assertEqual(sent["completion_window"], "24h")
        self.assertEqual(sent["metadata"], {"job": "t-a1"})
        self.assertEqual(request.headers["Content-type"], "application/json")

    def test_raises_when_response_missing_id(self) -> None:
        with patch("longtu_translation_pipeline.llm.client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _fake_urlopen({"status": "validating"})
            with self.assertRaisesRegex(RuntimeError, "missing 'id'"):
                llm_common.create_batch("file_abc", CFG)


class GetBatchTest(unittest.TestCase):
    def test_returns_batch_dict(self) -> None:
        with patch("longtu_translation_pipeline.llm.client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _fake_urlopen({"id": "b1", "status": "in_progress"})
            result = llm_common.get_batch("b1", CFG)
        self.assertEqual(result["status"], "in_progress")
        request = mock_open.call_args[0][0]
        self.assertEqual(request.method, "GET")
        self.assertTrue(request.full_url.endswith("/batches/b1"))

    def test_raises_when_id_blank(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "batch_id is required"):
            llm_common.get_batch("", CFG)


class WaitForBatchTest(unittest.TestCase):
    def test_returns_when_completed(self) -> None:
        statuses = iter([
            {"id": "b", "status": "validating"},
            {"id": "b", "status": "in_progress"},
            {"id": "b", "status": "completed", "output_file_id": "file_out"},
        ])
        sleeps: list[float] = []
        with patch("longtu_translation_pipeline.llm.client.urllib.request.urlopen") as mock_open:
            mock_open.side_effect = [_fake_urlopen(s) for s in statuses]
            batch = llm_common.wait_for_batch(
                "b",
                CFG,
                poll_interval_sec=1,
                max_wait_sec=10,
                sleep_fn=sleeps.append,
                now_fn=iter([0, 1, 2, 3, 4]).__next__,
            )
        self.assertEqual(batch["status"], "completed")
        self.assertEqual(batch["output_file_id"], "file_out")
        # Two sleeps before the third (terminal) poll.
        self.assertEqual(sleeps, [1, 1])

    def test_raises_on_failed_status(self) -> None:
        with patch("longtu_translation_pipeline.llm.client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _fake_urlopen(
                {"id": "b", "status": "failed", "errors": {"data": [{"message": "boom"}]}}
            )
            with self.assertRaisesRegex(RuntimeError, "non-completed status 'failed'.*boom"):
                llm_common.wait_for_batch(
                    "b", CFG, poll_interval_sec=1, max_wait_sec=10,
                    sleep_fn=lambda _x: None, now_fn=iter([0, 1]).__next__,
                )

    def test_raises_on_max_wait_exceeded(self) -> None:
        with patch("longtu_translation_pipeline.llm.client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _fake_urlopen({"id": "b", "status": "in_progress"})
            with self.assertRaisesRegex(RuntimeError, "did not complete"):
                llm_common.wait_for_batch(
                    "b", CFG,
                    poll_interval_sec=1, max_wait_sec=1,
                    sleep_fn=lambda _x: None,
                    now_fn=iter([0, 2]).__next__,
                )

    def test_progress_cb_fires_each_poll(self) -> None:
        seen: list[str] = []
        with patch("longtu_translation_pipeline.llm.client.urllib.request.urlopen") as mock_open:
            mock_open.side_effect = [
                _fake_urlopen({"id": "b", "status": "in_progress"}),
                _fake_urlopen({"id": "b", "status": "completed"}),
            ]
            llm_common.wait_for_batch(
                "b", CFG,
                poll_interval_sec=1, max_wait_sec=10,
                progress_cb=lambda b: seen.append(b["status"]),
                sleep_fn=lambda _x: None,
                now_fn=iter([0, 1, 2]).__next__,
            )
        self.assertEqual(seen, ["in_progress", "completed"])

    def test_rejects_invalid_poll_interval(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "poll_interval_sec"):
            llm_common.wait_for_batch("b", CFG, poll_interval_sec=0, max_wait_sec=10)

    def test_rejects_max_wait_smaller_than_poll(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "max_wait_sec"):
            llm_common.wait_for_batch("b", CFG, poll_interval_sec=60, max_wait_sec=30)


class DownloadBatchOutputTest(unittest.TestCase):
    def test_writes_and_parses_jsonl(self) -> None:
        output = (
            b'{"id":"r1","custom_id":"seg-batch-0001","response":{"status_code":200,"body":{"choices":[{"message":{"content":"{}"}}]}},"error":null}\n'
            b'{"id":"r2","custom_id":"seg-batch-0002","response":null,"error":{"code":"x","message":"y"}}\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out.jsonl"
            with patch("longtu_translation_pipeline.llm.client.urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_urlopen(output)
                by_id = llm_common.download_batch_output("file_out", CFG, dest)
            self.assertEqual(dest.read_bytes(), output)
        self.assertEqual(set(by_id), {"seg-batch-0001", "seg-batch-0002"})
        self.assertEqual(by_id["seg-batch-0001"]["response"]["status_code"], 200)
        self.assertEqual(by_id["seg-batch-0002"]["error"]["code"], "x")

    def test_raises_on_duplicate_custom_id(self) -> None:
        output = (
            b'{"custom_id":"c","response":null,"error":null}\n'
            b'{"custom_id":"c","response":null,"error":null}\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch("longtu_translation_pipeline.llm.client.urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_urlopen(output)
                with self.assertRaisesRegex(RuntimeError, "Duplicate custom_id"):
                    llm_common.download_batch_output("f", CFG, Path(tmp) / "o.jsonl")

    def test_raises_on_missing_custom_id(self) -> None:
        output = b'{"response":null}\n'
        with tempfile.TemporaryDirectory() as tmp:
            with patch("longtu_translation_pipeline.llm.client.urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_urlopen(output)
                with self.assertRaisesRegex(RuntimeError, "missing custom_id"):
                    llm_common.download_batch_output("f", CFG, Path(tmp) / "o.jsonl")

    def test_raises_on_invalid_jsonl_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("longtu_translation_pipeline.llm.client.urllib.request.urlopen") as mock_open:
                mock_open.return_value = _fake_urlopen(b"not json\n")
                with self.assertRaisesRegex(RuntimeError, "not JSON"):
                    llm_common.download_batch_output("f", CFG, Path(tmp) / "o.jsonl")

    def test_rejects_blank_output_file_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "output_file_id"):
                llm_common.download_batch_output("", CFG, Path(tmp) / "o.jsonl")


if __name__ == "__main__":
    unittest.main()
