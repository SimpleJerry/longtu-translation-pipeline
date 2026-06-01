"""LLM transport for OpenAI-compatible chat completion and Batch API endpoints.

Re-exports the client surface from :mod:`longtu_translation_pipeline.llm.client`
so callers can ``from longtu_translation_pipeline.llm import ClientConfig, ...``.
Extracted from the former ``scripts/llm_common.py`` under ADR-0033.
"""

from __future__ import annotations

from .client import (
    BATCH_TERMINAL_STATUSES,
    ClientConfig,
    build_batch_request_line,
    call_chat_completion,
    create_batch,
    download_batch_output,
    get_batch,
    parse_json_content,
    resolve_client_config,
    upload_batch_input_file,
    wait_for_batch,
)

__all__ = [
    "ClientConfig",
    "resolve_client_config",
    "call_chat_completion",
    "parse_json_content",
    "build_batch_request_line",
    "upload_batch_input_file",
    "create_batch",
    "get_batch",
    "wait_for_batch",
    "download_batch_output",
    "BATCH_TERMINAL_STATUSES",
]
