"""Shared LLM client utilities for OpenAI-compatible chat completion endpoints.

Provides the four symbols consumed by both LLM cleanup pipelines:
ClientConfig, resolve_client_config, call_chat_completion, parse_json_content.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping

__all__ = [
    "ClientConfig",
    "resolve_client_config",
    "call_chat_completion",
    "parse_json_content",
]


@dataclass(frozen=True)
class ClientConfig:
    api_key: str
    base_url: str
    model: str


def resolve_client_config(
    env: Mapping[str, str],
    base_url_override: str | None = None,
    model_override: str | None = None,
) -> ClientConfig:
    api_key = env.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required before any LLM cleanup run.")

    model = (model_override or env.get("LLM_MODEL", "")).strip()
    if not model:
        raise RuntimeError("LLM_MODEL is required; the repository does not hard-code it.")

    base_url = (
        base_url_override
        or env.get("OPENAI_BASE_URL", "")
        or "https://api.openai.com/v1"
    ).strip()
    if not base_url:
        raise RuntimeError("OPENAI_BASE_URL resolved to an empty value.")

    return ClientConfig(api_key=api_key, base_url=base_url.rstrip("/"), model=model)


def call_chat_completion(
    payload: dict[str, Any],
    client_config: ClientConfig,
    temperature: float,
    timeout: int,
) -> dict[str, Any]:
    del temperature
    url = f"{client_config.base_url}/chat/completions"
    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {client_config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from LLM API: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach LLM API: {exc}") from exc

    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LLM API returned invalid JSON envelope: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("LLM API response envelope must be a JSON object.")
    return parsed


def parse_json_content(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise RuntimeError("LLM response content is not JSON.")
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"LLM response JSON could not be parsed: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("LLM response content must be a JSON object.")
    return parsed
