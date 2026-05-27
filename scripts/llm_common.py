"""Shared LLM client utilities for OpenAI-compatible chat completion endpoints.

Provides the four symbols consumed by both LLM cleanup pipelines:
ClientConfig, resolve_client_config, call_chat_completion, parse_json_content.

Also provides Batch API helpers (build_batch_request_line,
upload_batch_input_file, create_batch, get_batch, wait_for_batch,
download_batch_output) for the cost-optimised cleanup mode that submits
all micro-batches as a single async batch job to /v1/batches.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

__all__ = [
    "ClientConfig",
    "resolve_client_config",
    "call_chat_completion",
    "parse_json_content",
    # Batch API helpers
    "build_batch_request_line",
    "upload_batch_input_file",
    "create_batch",
    "get_batch",
    "wait_for_batch",
    "download_batch_output",
    "BATCH_TERMINAL_STATUSES",
]

BATCH_TERMINAL_STATUSES = frozenset(
    {"completed", "failed", "expired", "cancelled", "cancelling"}
)


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


# ---------------------------------------------------------------------------
# Batch API helpers
# ---------------------------------------------------------------------------
#
# The four functions below implement just enough of OpenAI's Batch API to
# submit a single JSONL file of /v1/chat/completions requests, poll the
# resulting batch job until a terminal state, and download the output
# JSONL.  No third-party dependency is introduced: multipart upload is
# hand-rolled with a generated boundary, matching the rest of the module's
# urllib-only contract (audit-2026-05-26 §P0-1: single transport surface).
#
# Each helper takes ``ClientConfig`` so the same env-derived API key /
# base URL / model contract applies, and raises ``RuntimeError`` with the
# upstream body on HTTP error so the caller's existing error handling
# (retry loops, raw-batch dumps) keeps working unchanged.


def build_batch_request_line(custom_id: str, chat_payload: dict[str, Any]) -> dict[str, Any]:
    """Wrap a chat completion payload as one line of an /v1/batches input file.

    ``custom_id`` must be unique within the JSONL and is the only way to
    correlate output lines back to micro-batches once the batch completes.
    """
    if not custom_id or not isinstance(custom_id, str):
        raise RuntimeError("batch custom_id must be a non-empty string.")
    if not isinstance(chat_payload, dict):
        raise RuntimeError("batch chat_payload must be a dict.")
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": chat_payload,
    }


def _http_request(
    method: str,
    url: str,
    cfg: ClientConfig,
    *,
    json_body: dict[str, Any] | None = None,
    raw_body: bytes | None = None,
    extra_headers: Mapping[str, str] | None = None,
    timeout: int = 120,
    return_bytes: bool = False,
) -> Any:
    """Low-level urllib helper shared by all Batch API calls.

    Returns parsed JSON dict by default, or raw bytes when ``return_bytes``
    is set (used by the file-content download).  Errors include the body
    text so the caller sees what OpenAI complained about.
    """
    headers: dict[str, str] = {"Authorization": f"Bearer {cfg.api_key}"}
    data: bytes | None = None
    if json_body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
    elif raw_body is not None:
        data = raw_body
    if extra_headers:
        headers.update(extra_headers)

    request = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach {url}: {exc}") from exc

    if return_bytes:
        return payload

    text = payload.decode("utf-8")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{url} returned invalid JSON: {exc}: {text[:200]}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{url} response envelope must be a JSON object.")
    return parsed


def upload_batch_input_file(
    jsonl_path: Path,
    cfg: ClientConfig,
    *,
    timeout: int = 600,
) -> str:
    """Upload a JSONL file with ``purpose=batch`` and return its file_id.

    The upload uses multipart/form-data hand-rolled to keep urllib's
    zero-dependency footprint.  Large JSONL files are read fully into
    memory; for the ~66k row segments corpus this is < 20 MiB.
    """
    jsonl_path = Path(jsonl_path)
    if not jsonl_path.is_file():
        raise RuntimeError(f"Batch input JSONL not found: {jsonl_path}")
    file_bytes = jsonl_path.read_bytes()

    boundary = f"----LongtuBatch{uuid.uuid4().hex}"
    crlf = b"\r\n"
    parts: list[bytes] = []
    parts.append(f"--{boundary}".encode("ascii"))
    parts.append(b'Content-Disposition: form-data; name="purpose"')
    parts.append(b"")
    parts.append(b"batch")
    parts.append(f"--{boundary}".encode("ascii"))
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{jsonl_path.name}"'
        .encode("utf-8")
    )
    parts.append(b"Content-Type: application/jsonl")
    parts.append(b"")
    parts.append(file_bytes)
    parts.append(f"--{boundary}--".encode("ascii"))
    parts.append(b"")
    body = crlf.join(parts)

    response = _http_request(
        "POST",
        f"{cfg.base_url}/files",
        cfg,
        raw_body=body,
        extra_headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        timeout=timeout,
    )
    file_id = response.get("id")
    if not isinstance(file_id, str) or not file_id:
        raise RuntimeError(f"/v1/files response missing 'id': {response}")
    return file_id


def create_batch(
    file_id: str,
    cfg: ClientConfig,
    *,
    endpoint: str = "/v1/chat/completions",
    completion_window: str = "24h",
    metadata: Mapping[str, str] | None = None,
    timeout: int = 60,
) -> str:
    """Create a batch job for the uploaded JSONL and return its batch_id."""
    body: dict[str, Any] = {
        "input_file_id": file_id,
        "endpoint": endpoint,
        "completion_window": completion_window,
    }
    if metadata:
        body["metadata"] = dict(metadata)
    response = _http_request(
        "POST", f"{cfg.base_url}/batches", cfg, json_body=body, timeout=timeout
    )
    batch_id = response.get("id")
    if not isinstance(batch_id, str) or not batch_id:
        raise RuntimeError(f"/v1/batches response missing 'id': {response}")
    return batch_id


def get_batch(batch_id: str, cfg: ClientConfig, *, timeout: int = 60) -> dict[str, Any]:
    """Fetch the current state of a batch job."""
    if not batch_id:
        raise RuntimeError("batch_id is required.")
    return _http_request(
        "GET", f"{cfg.base_url}/batches/{batch_id}", cfg, timeout=timeout
    )


def wait_for_batch(
    batch_id: str,
    cfg: ClientConfig,
    *,
    poll_interval_sec: int = 60,
    max_wait_sec: int = 24 * 3600,
    progress_cb: Callable[[dict[str, Any]], None] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], float] = time.time,
    timeout: int = 60,
) -> dict[str, Any]:
    """Block until the batch reaches a terminal status, then return it.

    Raises ``RuntimeError`` on any non-completed terminal status (failed,
    expired, cancelled, cancelling) or when ``max_wait_sec`` elapses.
    ``progress_cb`` is invoked once per poll with the latest batch object;
    use it from the caller to persist intermediate state.
    """
    if poll_interval_sec < 1:
        raise RuntimeError("poll_interval_sec must be >= 1.")
    if max_wait_sec < poll_interval_sec:
        raise RuntimeError("max_wait_sec must be >= poll_interval_sec.")

    deadline = now_fn() + max_wait_sec
    while True:
        batch = get_batch(batch_id, cfg, timeout=timeout)
        status = batch.get("status", "")
        if progress_cb is not None:
            progress_cb(batch)
        if status == "completed":
            return batch
        if status in BATCH_TERMINAL_STATUSES:
            errors = batch.get("errors")
            raise RuntimeError(
                f"Batch {batch_id} ended in non-completed status '{status}'. errors={errors}"
            )
        if now_fn() >= deadline:
            raise RuntimeError(
                f"Batch {batch_id} did not complete within {max_wait_sec}s "
                f"(last status='{status}')."
            )
        sleep_fn(poll_interval_sec)


def download_batch_output(
    output_file_id: str,
    cfg: ClientConfig,
    dest_path: Path,
    *,
    timeout: int = 600,
) -> dict[str, dict[str, Any]]:
    """Download a batch output JSONL to ``dest_path`` and parse it by custom_id.

    Returns a dict keyed by ``custom_id``; each value is the raw output
    line (with ``response`` and ``error`` sub-objects).  The caller is
    responsible for inspecting ``.error`` and ``.response.body``.
    """
    if not output_file_id:
        raise RuntimeError("output_file_id is required.")
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    payload = _http_request(
        "GET",
        f"{cfg.base_url}/files/{output_file_id}/content",
        cfg,
        return_bytes=True,
        timeout=timeout,
    )
    dest_path.write_bytes(payload)

    by_custom_id: dict[str, dict[str, Any]] = {}
    for line_no, line in enumerate(payload.decode("utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entry = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Batch output line {line_no} is not JSON: {exc}: {stripped[:200]}"
            ) from exc
        if not isinstance(entry, dict):
            raise RuntimeError(f"Batch output line {line_no} is not a JSON object.")
        custom_id = entry.get("custom_id")
        if not isinstance(custom_id, str) or not custom_id:
            raise RuntimeError(f"Batch output line {line_no} missing custom_id.")
        if custom_id in by_custom_id:
            raise RuntimeError(f"Duplicate custom_id in batch output: {custom_id}")
        by_custom_id[custom_id] = entry
    return by_custom_id
