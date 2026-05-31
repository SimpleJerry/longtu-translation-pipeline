"""Orchestration for glossary LLM cleanup (ADR-0025, ADR-0030).

Extracted verbatim from the former ``scripts/glossary_llm_cleanup_pipeline.py``
under ADR-0033. Wires the sync and Batch API paths, per-batch classification
with retries, and the final result assembly.

The Batch API helpers (upload/create/wait/download) are imported here as module
globals so tests can ``patch.object(pipeline, "upload_batch_input_file", ...)``
exactly as they patched the original single-file module.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Mapping

from longtu_translation_pipeline.llm import (
    ClientConfig,
    build_batch_request_line,
    call_chat_completion,
    create_batch,
    download_batch_output,
    resolve_client_config,
    upload_batch_input_file,
    wait_for_batch,
)

from .batch_state import _load_state, _now_iso, _save_state_atomic
from .io import (
    make_batches,
    read_glossary,
    write_clean_glossary,
    write_csv,
    write_raw_batch,
    write_removed_csv,
)
from .models import (
    AUDIT_FIELDS,
    CleanupResult,
    Client,
    Decision,
    GlossaryRow,
    SUMMARY_FIELDS,
)
from .prompts import build_request_payload
from .response import parse_and_validate_response
from .review import build_audit_rows, build_summary_rows


def run_cleanup(
    glossary_path: Path,
    review_dir: Path,
    apply_changes: bool,
    batch_size: int = 50,
    max_retries: int = 3,
    temperature: float = 0.0,
    timeout: int = 120,
    base_url: str | None = None,
    model: str | None = None,
    env: Mapping[str, str] | None = None,
    client: Client | None = None,
    batch_mode: str = "sync",
    max_output_tokens: int | None = None,
    poll_interval_sec: int = 60,
    max_wait_sec: int = 24 * 3600,
    completion_window: str = "24h",
) -> CleanupResult:
    if batch_mode not in ("sync", "batch"):
        raise RuntimeError(f"Invalid batch-mode: {batch_mode}")
    rows = read_glossary(glossary_path)
    validate_positive_int("batch-size", batch_size)
    validate_positive_int("max-retries", max_retries)
    validate_positive_int("timeout", timeout)
    if max_output_tokens is not None:
        validate_positive_int("max-output-tokens", max_output_tokens)

    client_config = resolve_client_config(env or os.environ, base_url, model)
    review_dir.mkdir(parents=True, exist_ok=True)

    effective_max_output_tokens = (
        max_output_tokens if max_output_tokens is not None else batch_size * 30
    )

    if batch_mode == "sync":
        decisions, total_usage = _run_sync_path(
            rows=rows,
            review_dir=review_dir,
            client_config=client_config,
            client=client,
            batch_size=batch_size,
            max_retries=max_retries,
            temperature=temperature,
            timeout=timeout,
            max_output_tokens=effective_max_output_tokens,
        )
    else:
        decisions, total_usage = _run_batch_path(
            rows=rows,
            review_dir=review_dir,
            client_config=client_config,
            batch_size=batch_size,
            temperature=temperature,
            max_output_tokens=effective_max_output_tokens,
            poll_interval_sec=poll_interval_sec,
            max_wait_sec=max_wait_sec,
            completion_window=completion_window,
        )

    audit_rows = build_audit_rows(rows, decisions)
    removed_rows = [row for row in audit_rows if row["keep"] == "NO"]
    write_csv(review_dir / "llm_glossary_audit.csv", AUDIT_FIELDS, audit_rows)
    write_removed_csv(review_dir / "removed_glossary_llm.csv", removed_rows)
    summary_rows = build_summary_rows(
        mode="apply" if apply_changes else "dry-run",
        rows=rows,
        audit_rows=audit_rows,
        client_config=client_config,
        total_usage=total_usage,
    )
    write_csv(review_dir / "llm_glossary_summary.csv", SUMMARY_FIELDS, summary_rows)

    if apply_changes:
        write_clean_glossary(glossary_path, rows, decisions)

    action_counts: dict[str, int] = {}
    for row in audit_rows:
        action_counts[row["action"]] = action_counts.get(row["action"], 0) + 1

    return CleanupResult(
        mode="apply" if apply_changes else "dry-run",
        input_rows=len(rows),
        kept_rows=sum(1 for row in audit_rows if row["keep"] == "YES"),
        removed_rows=len(removed_rows),
        review_dir=review_dir,
        model=client_config.model,
        total_prompt_tokens=total_usage["prompt_tokens"],
        total_completion_tokens=total_usage["completion_tokens"],
        total_tokens=total_usage["total_tokens"],
        action_counts=action_counts,
    )


def _run_sync_path(
    rows: list[GlossaryRow],
    review_dir: Path,
    client_config: ClientConfig,
    client: Client | None,
    batch_size: int,
    max_retries: int,
    temperature: float,
    timeout: int,
    max_output_tokens: int | None,
) -> tuple[dict[str, Decision], dict[str, int]]:
    raw_dir = review_dir / "raw_batches"
    raw_dir.mkdir(parents=True, exist_ok=True)
    decisions: dict[str, Decision] = {}
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    api_client = client or call_chat_completion
    for batch_no, batch in enumerate(make_batches(rows, batch_size), 1):
        response, batch_decisions = classify_batch(
            batch_no=batch_no,
            batch=batch,
            client_config=client_config,
            client=api_client,
            raw_dir=raw_dir,
            max_retries=max_retries,
            temperature=temperature,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )
        for key, value in response.get("usage", {}).items():
            if key in total_usage and isinstance(value, int):
                total_usage[key] += value
        decisions.update({d.term_id: d for d in batch_decisions})
    return decisions, total_usage


def _glossary_custom_id(batch_no: int) -> str:
    return f"glo-batch-{batch_no:04d}"


def _run_batch_path(
    rows: list[GlossaryRow],
    review_dir: Path,
    client_config: ClientConfig,
    batch_size: int,
    temperature: float,
    max_output_tokens: int | None,
    poll_interval_sec: int,
    max_wait_sec: int,
    completion_window: str,
) -> tuple[dict[str, Decision], dict[str, int]]:
    """OpenAI Batch API path for glossary cleanup.

    Same state-machine shape as the segments pipeline: build JSONL → upload
    → create_batch → poll → download → parse, with ``batch_state.json``
    persisted atomically after each transition to support resume.
    """
    batch_input_dir = review_dir / "batch_input"
    batch_output_dir = review_dir / "batch_output"
    batch_input_dir.mkdir(parents=True, exist_ok=True)
    batch_output_dir.mkdir(parents=True, exist_ok=True)
    input_jsonl = batch_input_dir / "all.jsonl"
    output_jsonl = batch_output_dir / "result.jsonl"
    state_path = review_dir / "batch_state.json"

    micro_batches = make_batches(rows, batch_size)
    state = _load_state(state_path) or {"phase": "init"}

    if state.get("phase") == "init":
        with input_jsonl.open("w", encoding="utf-8") as f:
            for batch_no, batch in enumerate(micro_batches, 1):
                payload = build_request_payload(
                    client_config.model, batch, temperature, max_output_tokens
                )
                line = build_batch_request_line(_glossary_custom_id(batch_no), payload)
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        state = {
            "phase": "input_written",
            "model": client_config.model,
            "batch_size": batch_size,
            "n_micro_batches": len(micro_batches),
            "n_rows": len(rows),
            "submitted_at": None,
            "completed_at": None,
        }
        _save_state_atomic(state_path, state)

    if state["phase"] == "input_written":
        file_id = upload_batch_input_file(input_jsonl, client_config)
        state.update({"phase": "uploaded", "input_file_id": file_id})
        _save_state_atomic(state_path, state)

    if state["phase"] == "uploaded":
        batch_id = create_batch(
            state["input_file_id"],
            client_config,
            completion_window=completion_window,
            metadata={"source": "glossary_llm_cleanup_pipeline"},
        )
        state.update(
            {"phase": "submitted", "batch_id": batch_id, "submitted_at": _now_iso()}
        )
        _save_state_atomic(state_path, state)

    if state["phase"] == "submitted":
        def _on_poll(batch_obj: dict[str, Any]) -> None:
            state["last_status"] = batch_obj.get("status")
            _save_state_atomic(state_path, state)

        batch_obj = wait_for_batch(
            state["batch_id"],
            client_config,
            poll_interval_sec=poll_interval_sec,
            max_wait_sec=max_wait_sec,
            progress_cb=_on_poll,
        )
        output_file_id = batch_obj.get("output_file_id")
        if not output_file_id:
            raise RuntimeError(
                f"Completed batch {state['batch_id']} has no output_file_id."
            )
        state.update(
            {
                "phase": "completed",
                "output_file_id": output_file_id,
                "error_file_id": batch_obj.get("error_file_id"),
                "completed_at": _now_iso(),
            }
        )
        _save_state_atomic(state_path, state)

    if state["phase"] == "completed":
        by_custom_id = download_batch_output(
            state["output_file_id"], client_config, output_jsonl
        )
        state["phase"] = "downloaded"
        _save_state_atomic(state_path, state)
    else:
        by_custom_id = _parse_existing_output_jsonl(output_jsonl)

    decisions: dict[str, Decision] = {}
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for batch_no, batch in enumerate(micro_batches, 1):
        custom_id = _glossary_custom_id(batch_no)
        entry = by_custom_id.get(custom_id)
        if entry is None:
            raise RuntimeError(f"Batch output missing custom_id={custom_id}")
        if entry.get("error"):
            raise RuntimeError(
                f"Batch line {custom_id} returned error: {entry['error']}"
            )
        response_obj = entry.get("response") or {}
        body = response_obj.get("body") or {}
        if not isinstance(body, dict):
            raise RuntimeError(f"Batch line {custom_id} has non-dict response.body.")
        for key, value in (body.get("usage") or {}).items():
            if key in total_usage and isinstance(value, int):
                total_usage[key] += value
        for d in parse_and_validate_response(body, batch):
            decisions[d.term_id] = d
    return decisions, total_usage


def _parse_existing_output_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        raise RuntimeError(f"Expected previously downloaded batch output at {path}.")
    out: dict[str, dict[str, Any]] = {}
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        entry = json.loads(stripped)
        custom_id = entry.get("custom_id")
        if not isinstance(custom_id, str) or not custom_id:
            raise RuntimeError(f"{path} line {line_no} missing custom_id.")
        if custom_id in out:
            raise RuntimeError(f"Duplicate custom_id in {path}: {custom_id}")
        out[custom_id] = entry
    return out


def validate_positive_int(name: str, value: int) -> None:
    if value < 1:
        raise RuntimeError(f"{name} must be >= 1.")


def classify_batch(
    batch_no: int,
    batch: list[GlossaryRow],
    client_config: ClientConfig,
    client: Client,
    raw_dir: Path,
    max_retries: int,
    temperature: float,
    timeout: int,
    max_output_tokens: int | None = None,
) -> tuple[dict[str, Any], list[Decision]]:
    request_payload = build_request_payload(
        client_config.model, batch, temperature, max_output_tokens
    )
    last_error = ""
    for attempt in range(1, max_retries + 1):
        response: dict[str, Any] | None = None
        try:
            response = client(request_payload, client_config, temperature, timeout)
            write_raw_batch(raw_dir, batch_no, attempt, request_payload, response, None)
            decisions = parse_and_validate_response(response, batch)
            return response, decisions
        except RuntimeError as exc:
            last_error = str(exc)
            write_raw_batch(raw_dir, batch_no, attempt, request_payload, response, last_error)
            if attempt < max_retries:
                time.sleep(min(2**attempt, 8))
    raise RuntimeError(f"Batch {batch_no} failed after {max_retries} attempts: {last_error}")
