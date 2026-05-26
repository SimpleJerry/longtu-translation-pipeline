from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import llm_common  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
