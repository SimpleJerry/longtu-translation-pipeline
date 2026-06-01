"""Orchestration for segment LLM cleanup (ADR-0026, ADR-0030).

Extracted verbatim from the former ``scripts/segments_llm_cleanup_pipeline.py``
under ADR-0033. Wires the sync and Batch API paths, the resumable chunked-batch
path, per-batch classification with retries, and the final result assembly.

The Batch API helpers (upload/create/wait/download) are imported here as module
globals so tests can ``patch.object(pipeline, "upload_batch_input_file", ...)``
exactly as they patched the original single-file module.
"""

from __future__ import annotations

import json
import math
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

from .._batch_state import _load_state, _now_iso, _save_state_atomic
from .features import build_features
from .io import make_batches, read_glossary, read_segments, write_raw_batch, write_segments
from .models import (
    Client,
    CleanupResult,
    Decision,
    GlossaryTerm,
    RowOutcome,
    SegmentRow,
)
from .prompts import build_request_payload
from .response import parse_and_validate_response
from .review import write_review_files
from .validation import build_outcome


def run_cleanup(
    segments_path: Path,
    glossary_path: Path,
    review_dir: Path,
    apply_changes: bool,
    batch_size: int = 25,
    max_retries: int = 3,
    sample_review_rows: int = 50,
    temperature: float = 0.0,
    timeout: int = 180,
    base_url: str | None = None,
    model: str | None = None,
    env: Mapping[str, str] | None = None,
    client: Client | None = None,
    batch_mode: str = "sync",
    max_output_tokens: int | None = None,
    poll_interval_sec: int = 60,
    max_wait_sec: int = 24 * 3600,
    completion_window: str = "24h",
    n_chunks: int = 1,
) -> CleanupResult:
    if batch_mode not in ("sync", "batch"):
        raise RuntimeError(f"Invalid batch-mode: {batch_mode}")
    validate_positive_int("batch-size", batch_size)
    validate_positive_int("max-retries", max_retries)
    validate_positive_int("timeout", timeout)
    validate_nonnegative_int("sample-review-rows", sample_review_rows)
    if max_output_tokens is not None:
        validate_positive_int("max-output-tokens", max_output_tokens)
    client_config = resolve_client_config(env or os.environ, base_url, model)

    segments = read_segments(segments_path)
    glossary = read_glossary(glossary_path)
    glossary_sorted = sorted(glossary, key=lambda term: len(term.zh), reverse=True)
    review_dir.mkdir(parents=True, exist_ok=True)

    # Each microbatch of 50 segments can need up to ~10k output tokens when many
    # REWRITE_KO decisions include long Korean rewrites and verbose reasons.
    # batch_size * 300 gives ~15 000 for batch_size=50, near the model ceiling,
    # which prevents virtually all truncation without wasting money (max_tokens
    # only caps; actual usage is whatever the model generates).
    effective_max_output_tokens = (
        max_output_tokens if max_output_tokens is not None
        else min(batch_size * 300, 16000)
    )

    if batch_mode == "sync":
        outcomes, total_usage = run_sync_path(
            segments=segments,
            glossary_sorted=glossary_sorted,
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
        outcomes, total_usage = run_batch_path(
            segments=segments,
            glossary_sorted=glossary_sorted,
            review_dir=review_dir,
            client_config=client_config,
            batch_size=batch_size,
            temperature=temperature,
            max_output_tokens=effective_max_output_tokens,
            poll_interval_sec=poll_interval_sec,
            max_wait_sec=max_wait_sec,
            completion_window=completion_window,
            n_chunks=n_chunks,
        )

    write_review_files(
        review_dir,
        outcomes,
        total_usage,
        client_config,
        apply_changes,
        sample_review_rows,
    )
    if apply_changes:
        write_segments(segments_path, outcomes)

    action_counts: dict[str, int] = {}
    for outcome in outcomes:
        action_counts[outcome.final_action] = action_counts.get(outcome.final_action, 0) + 1

    return CleanupResult(
        mode="apply" if apply_changes else "dry-run",
        input_rows=len(segments),
        output_rows=sum(1 for outcome in outcomes if outcome.final_action != "REMOVE"),
        kept_rows=sum(1 for outcome in outcomes if outcome.final_action == "KEEP"),
        removed_rows=sum(1 for outcome in outcomes if outcome.final_action == "REMOVE"),
        rewritten_rows=sum(1 for outcome in outcomes if outcome.final_action == "REWRITE"),
        rewrite_failed_rows=sum(
            1 for outcome in outcomes if outcome.validation_status == "REWRITE_REJECTED"
        ),
        review_rows=sum(1 for outcome in outcomes if outcome.final_action == "REVIEW"),
        review_dir=review_dir,
        model=client_config.model,
        total_prompt_tokens=total_usage["prompt_tokens"],
        total_completion_tokens=total_usage["completion_tokens"],
        total_tokens=total_usage["total_tokens"],
        action_counts=action_counts,
    )


def run_sync_path(
    segments: list[SegmentRow],
    glossary_sorted: list[GlossaryTerm],
    review_dir: Path,
    client_config: ClientConfig,
    client: Client | None,
    batch_size: int,
    max_retries: int,
    temperature: float,
    timeout: int,
    max_output_tokens: int | None,
) -> tuple[list[RowOutcome], dict[str, int]]:
    """Original synchronous per-batch /v1/chat/completions path.

    Retained for unit tests, small ad-hoc debugging runs, and as a fallback
    when the Batch API is unavailable. Raw responses are written under
    ``raw_batches/`` exactly as before.
    """
    raw_dir = review_dir / "raw_batches"
    raw_dir.mkdir(parents=True, exist_ok=True)
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    api_client = client or call_chat_completion
    outcomes: list[RowOutcome] = []
    for batch_no, batch in enumerate(make_batches(segments, batch_size), 1):
        response, decisions = classify_batch(
            batch_no=batch_no,
            batch=batch,
            glossary_sorted=glossary_sorted,
            client_config=client_config,
            client=api_client,
            raw_dir=raw_dir,
            max_retries=max_retries,
            temperature=temperature,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )
        _accumulate_usage(total_usage, response.get("usage", {}))
        outcomes.extend(_build_outcomes_for_batch(batch, decisions, glossary_sorted))
    return outcomes, total_usage


def run_batch_path(
    segments: list[SegmentRow],
    glossary_sorted: list[GlossaryTerm],
    review_dir: Path,
    client_config: ClientConfig,
    batch_size: int,
    temperature: float,
    max_output_tokens: int | None,
    poll_interval_sec: int,
    max_wait_sec: int,
    completion_window: str,
    n_chunks: int = 1,
) -> tuple[list[RowOutcome], dict[str, int]]:
    """OpenAI Batch API path: submit one or more jobs for the whole corpus.

    When n_chunks > 1, the corpus is split into n_chunks sequential batch jobs
    so each job stays under the org's enqueued-token limit.  State is persisted
    in batch_state_chunked.json; resumable across restarts.

    When n_chunks == 1 (default), the original single-job path is used with
    batch_state.json for state.
    """
    if n_chunks > 1:
        return _run_chunked_batch_path(
            segments=segments,
            glossary_sorted=glossary_sorted,
            review_dir=review_dir,
            client_config=client_config,
            batch_size=batch_size,
            n_chunks=n_chunks,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            poll_interval_sec=poll_interval_sec,
            max_wait_sec=max_wait_sec,
            completion_window=completion_window,
        )
    batch_input_dir = review_dir / "batch_input"
    batch_output_dir = review_dir / "batch_output"
    batch_input_dir.mkdir(parents=True, exist_ok=True)
    batch_output_dir.mkdir(parents=True, exist_ok=True)
    input_jsonl = batch_input_dir / "all.jsonl"
    output_jsonl = batch_output_dir / "result.jsonl"
    state_path = review_dir / "batch_state.json"

    micro_batches = make_batches(segments, batch_size)
    state = _load_state(state_path) or {"phase": "init"}

    if state.get("phase") == "init":
        _write_batch_input_jsonl(
            input_jsonl,
            micro_batches,
            glossary_sorted,
            client_config.model,
            temperature,
            max_output_tokens,
        )
        state = {
            "phase": "input_written",
            "model": client_config.model,
            "batch_size": batch_size,
            "n_micro_batches": len(micro_batches),
            "n_rows": len(segments),
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
            metadata={"source": "segments_llm_cleanup_pipeline"},
        )
        state.update(
            {
                "phase": "submitted",
                "batch_id": batch_id,
                "submitted_at": _now_iso(),
            }
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
        # Resuming after a previous successful download: re-parse the file.
        by_custom_id = _parse_existing_output_jsonl(output_jsonl)

    return _process_batch_results(micro_batches, glossary_sorted, by_custom_id)


def _accumulate_usage(total: dict[str, int], usage: Mapping[str, Any]) -> None:
    for key, value in usage.items():
        if key in total and isinstance(value, int):
            total[key] += value


def _build_outcomes_for_batch(
    batch: list[SegmentRow],
    decisions: list[Decision],
    glossary_sorted: list[GlossaryTerm],
) -> list[RowOutcome]:
    decisions_by_id = {decision.segment_id: decision for decision in decisions}
    outcomes: list[RowOutcome] = []
    for row in batch:
        features = build_features(row, glossary_sorted)
        outcomes.append(build_outcome(row, decisions_by_id[row.segment_id], features))
    return outcomes


def _segment_custom_id(batch_no: int) -> str:
    return f"seg-batch-{batch_no:04d}"


def _write_batch_input_jsonl(
    path: Path,
    micro_batches: list[list[SegmentRow]],
    glossary_sorted: list[GlossaryTerm],
    model: str,
    temperature: float,
    max_output_tokens: int | None,
) -> None:
    with path.open("w", encoding="utf-8") as f:
        for batch_no, batch in enumerate(micro_batches, 1):
            payload = build_request_payload(
                model, batch, glossary_sorted, temperature, max_output_tokens
            )
            line = build_batch_request_line(_segment_custom_id(batch_no), payload)
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


def _process_batch_results(
    micro_batches: list[list[SegmentRow]],
    glossary_sorted: list[GlossaryTerm],
    by_custom_id: dict[str, dict[str, Any]],
) -> tuple[list[RowOutcome], dict[str, int]]:
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    outcomes: list[RowOutcome] = []
    for batch_no, batch in enumerate(micro_batches, 1):
        custom_id = _segment_custom_id(batch_no)
        entry = by_custom_id.get(custom_id)
        if entry is None:
            raise RuntimeError(f"Batch output missing custom_id={custom_id}")
        if entry.get("error"):
            raise RuntimeError(
                f"Batch output line {custom_id} returned error: {entry['error']}"
            )
        response_obj = entry.get("response") or {}
        body = response_obj.get("body") or {}
        if not isinstance(body, dict):
            raise RuntimeError(f"Batch line {custom_id} has non-dict response.body.")
        _accumulate_usage(total_usage, body.get("usage", {}) or {})
        decisions = parse_and_validate_response(body, batch)
        decisions = [
            Decision(
                segment_id=d.segment_id,
                action=d.action,
                reason=d.reason,
                corrected_ko=d.corrected_ko,
                batch_no=batch_no,
            )
            for d in decisions
        ]
        outcomes.extend(_build_outcomes_for_batch(batch, decisions, glossary_sorted))
    return outcomes, total_usage


def _parse_existing_output_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        raise RuntimeError(f"Expected previously downloaded batch output at {path}.")
    by_custom_id: dict[str, dict[str, Any]] = {}
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        entry = json.loads(stripped)
        custom_id = entry.get("custom_id")
        if not isinstance(custom_id, str) or not custom_id:
            raise RuntimeError(f"{path} line {line_no} missing custom_id.")
        if custom_id in by_custom_id:
            raise RuntimeError(f"Duplicate custom_id in {path}: {custom_id}")
        by_custom_id[custom_id] = entry
    return by_custom_id


def _write_batch_input_jsonl_offset(
    path: Path,
    micro_batches: list[list[SegmentRow]],
    glossary_sorted: list[GlossaryTerm],
    model: str,
    temperature: float,
    max_output_tokens: int | None,
    start_batch_no: int,
) -> None:
    """Like _write_batch_input_jsonl but custom_ids start from start_batch_no."""
    with path.open("w", encoding="utf-8") as f:
        for batch_no, batch in enumerate(micro_batches, start_batch_no):
            payload = build_request_payload(
                model, batch, glossary_sorted, temperature, max_output_tokens
            )
            line = build_batch_request_line(_segment_custom_id(batch_no), payload)
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


def _run_chunked_batch_path(
    segments: list[SegmentRow],
    glossary_sorted: list[GlossaryTerm],
    review_dir: Path,
    client_config: ClientConfig,
    batch_size: int,
    n_chunks: int,
    temperature: float,
    max_output_tokens: int | None,
    poll_interval_sec: int,
    max_wait_sec: int,
    completion_window: str,
) -> tuple[list[RowOutcome], dict[str, int]]:
    """Submit the corpus as n_chunks sequential batch jobs to stay under enqueued-token limits.

    Each chunk is fully completed (downloaded) before the next is uploaded.
    State is persisted in batch_state_chunked.json; resumable across restarts.
    """
    batch_input_dir = review_dir / "batch_input"
    batch_output_dir = review_dir / "batch_output"
    batch_input_dir.mkdir(parents=True, exist_ok=True)
    batch_output_dir.mkdir(parents=True, exist_ok=True)
    state_path = review_dir / "batch_state_chunked.json"

    micro_batches = make_batches(segments, batch_size)
    # Auto-calculate chunk_size from token budget so --batch-chunks and
    # max_output_tokens never decouple.  Empirical avg input tokens per
    # micro-batch (batch_size=50 on segments.csv): ~3500.  Keep 200k headroom
    # below the 2M org enqueued-token limit to avoid off-by-one rejections.
    _effective_max_out = max_output_tokens if max_output_tokens is not None else 15000
    _tokens_per_mb = 3500 + _effective_max_out
    _auto_chunk_size = max(1, int(1_800_000 / _tokens_per_mb))
    # n_chunks > 1 acts as an explicit lower bound (more chunks = smaller
    # chunk_size), so honour the stricter of the two constraints.
    if n_chunks > 1:
        chunk_size = min(_auto_chunk_size, math.ceil(len(micro_batches) / n_chunks))
    else:
        chunk_size = _auto_chunk_size
    chunks_mb = [
        micro_batches[i : i + chunk_size]
        for i in range(0, len(micro_batches), chunk_size)
    ]
    actual_n_chunks = len(chunks_mb)

    state = _load_state(state_path) or {
        "phase": "chunked",
        "model": client_config.model,
        "batch_size": batch_size,
        "n_chunks": actual_n_chunks,
        "n_micro_batches": len(micro_batches),
        "n_rows": len(segments),
        "chunks": [{"phase": "init"} for _ in range(actual_n_chunks)],
    }

    by_custom_id: dict[str, dict[str, Any]] = {}

    start_batch_no = 1
    for i, mb_chunk in enumerate(chunks_mb):
        chunk_state = state["chunks"][i]
        input_jsonl = batch_input_dir / f"chunk_{i:03d}.jsonl"
        output_jsonl = batch_output_dir / f"result_{i:03d}.jsonl"

        if chunk_state.get("phase") == "init":
            _write_batch_input_jsonl_offset(
                input_jsonl,
                mb_chunk,
                glossary_sorted,
                client_config.model,
                temperature,
                max_output_tokens,
                start_batch_no,
            )
            chunk_state["phase"] = "input_written"
            _save_state_atomic(state_path, state)

        if chunk_state["phase"] == "input_written":
            file_id = upload_batch_input_file(input_jsonl, client_config)
            chunk_state.update({"phase": "uploaded", "input_file_id": file_id})
            _save_state_atomic(state_path, state)

        if chunk_state["phase"] == "uploaded":
            batch_id = create_batch(
                chunk_state["input_file_id"],
                client_config,
                completion_window=completion_window,
                metadata={
                    "source": "segments_llm_cleanup_pipeline",
                    "chunk": str(i),
                    "n_chunks": str(actual_n_chunks),
                },
            )
            chunk_state.update(
                {"phase": "submitted", "batch_id": batch_id, "submitted_at": _now_iso()}
            )
            _save_state_atomic(state_path, state)

        if chunk_state["phase"] == "submitted":
            def _on_poll(batch_obj: dict[str, Any], _cs: dict[str, Any] = chunk_state) -> None:
                _cs["last_status"] = batch_obj.get("status")
                _save_state_atomic(state_path, state)

            batch_obj = wait_for_batch(
                chunk_state["batch_id"],
                client_config,
                poll_interval_sec=poll_interval_sec,
                max_wait_sec=max_wait_sec,
                progress_cb=_on_poll,
            )
            output_file_id = batch_obj.get("output_file_id")
            if not output_file_id:
                raise RuntimeError(
                    f"Chunk {i} batch {chunk_state['batch_id']} has no output_file_id."
                )
            chunk_state.update(
                {
                    "phase": "completed",
                    "output_file_id": output_file_id,
                    "error_file_id": batch_obj.get("error_file_id"),
                    "completed_at": _now_iso(),
                }
            )
            _save_state_atomic(state_path, state)

        if chunk_state["phase"] == "completed":
            chunk_by_id = download_batch_output(
                chunk_state["output_file_id"], client_config, output_jsonl
            )
            by_custom_id.update(chunk_by_id)
            chunk_state["phase"] = "downloaded"
            _save_state_atomic(state_path, state)
        else:
            by_custom_id.update(_parse_existing_output_jsonl(output_jsonl))

        start_batch_no += len(mb_chunk)

    return _process_batch_results(micro_batches, glossary_sorted, by_custom_id)


def classify_batch(
    batch_no: int,
    batch: list[SegmentRow],
    glossary_sorted: list[GlossaryTerm],
    client_config: ClientConfig,
    client: Client,
    raw_dir: Path,
    max_retries: int,
    temperature: float,
    timeout: int,
    max_output_tokens: int | None = None,
) -> tuple[dict[str, Any], list[Decision]]:
    request_payload = build_request_payload(
        client_config.model, batch, glossary_sorted, temperature, max_output_tokens
    )
    last_error = ""
    for attempt in range(1, max_retries + 1):
        response: dict[str, Any] | None = None
        try:
            response = client(request_payload, client_config, temperature, timeout)
            write_raw_batch(raw_dir, batch_no, attempt, request_payload, response, None)
            decisions = parse_and_validate_response(response, batch)
            decisions = [
                Decision(
                    segment_id=decision.segment_id,
                    action=decision.action,
                    reason=decision.reason,
                    corrected_ko=decision.corrected_ko,
                    batch_no=batch_no,
                )
                for decision in decisions
            ]
            return response, decisions
        except RuntimeError as exc:
            last_error = str(exc)
            write_raw_batch(raw_dir, batch_no, attempt, request_payload, response, last_error)
            if attempt < max_retries:
                time.sleep(min(2**attempt, 8))
    raise RuntimeError(f"Batch {batch_no} failed after {max_retries} attempts: {last_error}")


def validate_positive_int(name: str, value: int) -> None:
    if value < 1:
        raise RuntimeError(f"{name} must be >= 1.")


def validate_nonnegative_int(name: str, value: int) -> None:
    if value < 0:
        raise RuntimeError(f"{name} must be >= 0.")
