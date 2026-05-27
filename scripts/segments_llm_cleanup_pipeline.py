"""Full-corpus LLM cleanup for Chinese-Korean segment pairs.

This pipeline sends the current ``data/segments.csv`` rows to an
OpenAI-compatible chat completions endpoint.  Unlike glossary cleanup, segment
cleanup may apply a Korean rewrite, but only after local validation confirms
that the rewritten target is still Korean, preserves placeholders, and keeps
matched glossary terms.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

try:
    from cleanup_common import ensure_csv_columns
    from llm_common import (
        ClientConfig,
        build_batch_request_line,
        call_chat_completion,
        create_batch,
        download_batch_output,
        parse_json_content,
        resolve_client_config,
        upload_batch_input_file,
        wait_for_batch,
    )
except ModuleNotFoundError:  # pragma: no cover - import fallback for tests
    from scripts.cleanup_common import ensure_csv_columns
    from scripts.llm_common import (
        ClientConfig,
        build_batch_request_line,
        call_chat_completion,
        create_batch,
        download_batch_output,
        parse_json_content,
        resolve_client_config,
        upload_batch_input_file,
        wait_for_batch,
    )


SEGMENT_SCHEMA = ["segment_id", "zh-CN", "ko"]
GLOSSARY_SCHEMA = ["term_id", "zh-CN", "ko"]

KEEP_ACTION = "KEEP_SEGMENT"
REWRITE_ACTION = "REWRITE_KO"
REVIEW_ACTION = "REVIEW_UNCERTAIN"
REMOVE_ACTIONS = {
    "REMOVE_NON_SEGMENT",
    "REMOVE_BAD_PAIR",
    "REMOVE_TARGET_CONTAMINATION",
}
VALID_ACTIONS = {KEEP_ACTION, REWRITE_ACTION, REVIEW_ACTION, *REMOVE_ACTIONS}

AUDIT_FIELDS = [
    "original_segment_id",
    "final_action",
    "llm_action",
    "validation_status",
    "reason",
    "validation_errors",
    "placeholder_tokens",
    "glossary_terms",
    "target_contamination",
    "structured_hint",
    "zh-CN",
    "original_ko",
    "corrected_ko",
    "final_ko",
]
REMOVED_FIELDS = [
    "removed_id",
    "original_segment_id",
    "remove_reason",
    "llm_action",
    "reason",
    "zh-CN",
    "ko",
    "corrected_ko",
]
REWRITTEN_FIELDS = [
    "rewrite_id",
    "original_segment_id",
    "reason",
    "zh-CN",
    "original_ko",
    "corrected_ko",
    "glossary_terms",
]
REWRITE_FAILED_FIELDS = [
    "failed_id",
    "original_segment_id",
    "reason",
    "validation_errors",
    "zh-CN",
    "original_ko",
    "corrected_ko",
    "glossary_terms",
]
SUMMARY_FIELDS = ["metric", "value"]
WARNING_FIELDS = ["warning_type", "scope", "value", "count", "rate", "details"]
SAMPLE_REVIEW_FIELDS = [
    "sample_id",
    "original_segment_id",
    "final_action",
    "llm_action",
    "validation_status",
    "reason",
    "validation_errors",
    "zh-CN",
    "original_ko",
    "corrected_ko",
    "final_ko",
]

REASON_REPETITION_WARNING_RATE = 0.60
REASON_REPETITION_MIN_BATCH_ROWS = 5
SURFACE_FEATURE_WARNING_MIN_ROWS = 5

HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
PLACEHOLDER_RE = re.compile(
    r"\{[A-Za-z0-9_]+\}|%[sdif]|%\d+\$[sdif]|\$\{[^}]+\}|<key\d+>|<[^>\s]+>"
)
STRUCTURED_RE = re.compile(r"^\s*[\{\[]\s*['\"].*['\"]\s*[\}\]]\s*$")
EXPLANATION_RE = re.compile(r"(translation|corrected|번역|수정|설명|理由|原因|改写)")

SYSTEM_PROMPT = (
    "You are a Chinese-to-Korean game localization segment reviewer. Review each "
    "row independently by its own meaning, not by applying a bulk rule to the "
    "whole batch. You may keep, remove, mark uncertain, or rewrite only the "
    "Korean target. The reason for every row must cite that row's own semantic "
    "problem or why it is usable. Do not return code, pseudocode, rules, batch "
    "summaries, or explanations outside the required JSON. Never change Chinese "
    "source, add rows, split rows, merge rows, or edit glossary terms. Every "
    "row in the results array must include corrected_ko: an empty string for "
    "non-rewrite actions, never null."
)


def _segments_response_schema() -> dict[str, Any]:
    """JSON schema enforced via response_format=json_schema strict.

    Built lazily so VALID_ACTIONS (set ordering) is captured at call time.
    """
    return {
        "name": "segment_review_results",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["results"],
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "segment_id",
                            "action",
                            "reason",
                            "corrected_ko",
                        ],
                        "properties": {
                            "segment_id": {"type": "string"},
                            "action": {
                                "type": "string",
                                "enum": sorted(VALID_ACTIONS),
                            },
                            "reason": {"type": "string", "minLength": 1},
                            "corrected_ko": {"type": "string"},
                        },
                    },
                },
            },
        },
    }


@dataclass(frozen=True)
class SegmentRow:
    segment_id: str
    zh: str
    ko: str


@dataclass(frozen=True)
class GlossaryTerm:
    term_id: str
    zh: str
    ko: str


@dataclass(frozen=True)
class SegmentFeatures:
    placeholders: list[str]
    glossary_terms: list[GlossaryTerm]
    target_contamination: bool
    structured_hint: bool


@dataclass(frozen=True)
class Decision:
    segment_id: str
    action: str
    reason: str
    corrected_ko: str
    batch_no: int = 0


@dataclass(frozen=True)
class RowOutcome:
    row: SegmentRow
    decision: Decision
    features: SegmentFeatures
    final_action: str
    validation_status: str
    validation_errors: list[str]
    final_ko: str


@dataclass(frozen=True)
class CleanupResult:
    mode: str
    input_rows: int
    output_rows: int
    kept_rows: int
    removed_rows: int
    rewritten_rows: int
    rewrite_failed_rows: int
    review_rows: int
    review_dir: Path
    model: str
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    action_counts: dict[str, int]


Client = Callable[[dict[str, Any], ClientConfig, float, int], dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LLM-assisted full-corpus cleanup for data/segments.csv."
    )
    parser.add_argument("--segments", default="data/segments.csv")
    parser.add_argument("--glossary", default="data/glossary.csv")
    parser.add_argument(
        "--review-dir", default="data/review/llm_segments_cleanup"
    )
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument(
        "--sample-review-rows",
        type=int,
        default=50,
        help="Number of balanced sample-review rows to write under the review directory.",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--batch-mode",
        choices=["sync", "batch"],
        default="batch",
        help="sync: legacy synchronous /v1/chat/completions per micro-batch. "
        "batch: submit one /v1/batches job for the whole corpus (50%% discount, "
        "up to 24h SLA). Default: batch.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=None,
        help="Cap on completion tokens per micro-batch. Defaults to batch_size*45.",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=60,
        help="Seconds between batch status polls (batch mode only).",
    )
    parser.add_argument(
        "--max-wait-sec",
        type=int,
        default=24 * 3600,
        help="Maximum seconds to wait for a batch job to complete.",
    )
    parser.add_argument(
        "--completion-window",
        default="24h",
        help="Completion window passed to /v1/batches (batch mode only).",
    )
    parser.add_argument(
        "--batch-chunks",
        type=int,
        default=1,
        help=(
            "Split the corpus into N sequential batch jobs (batch mode only). "
            "Use when the org enqueued-token quota is smaller than the full corpus. "
            "Each chunk is submitted and completed before the next is uploaded. "
            "State is persisted in batch_state_chunked.json; resumable across restarts."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Write review only.")
    mode.add_argument("--apply", action="store_true", help="Rewrite segments.csv.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mode = "apply" if args.apply else "dry-run"
    try:
        result = run_cleanup(
            segments_path=Path(args.segments),
            glossary_path=Path(args.glossary),
            review_dir=Path(args.review_dir),
            apply_changes=args.apply,
            batch_size=args.batch_size,
            max_retries=args.max_retries,
            sample_review_rows=args.sample_review_rows,
            temperature=args.temperature,
            timeout=args.timeout,
            base_url=args.base_url,
            model=args.model,
            batch_mode=args.batch_mode,
            max_output_tokens=args.max_output_tokens,
            poll_interval_sec=args.poll_interval,
            max_wait_sec=args.max_wait_sec,
            completion_window=args.completion_window,
            n_chunks=args.batch_chunks,
        )
    except RuntimeError as exc:
        print(f"Segments LLM cleanup failed in {mode} mode: {exc}")
        return 1
    print_result(result)
    return 0


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


def _load_state(state_path: Path) -> dict[str, Any] | None:
    if not state_path.is_file():
        return None
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Corrupt batch_state.json at {state_path}: {exc}") from exc


def _save_state_atomic(state_path: Path, state: Mapping[str, Any]) -> None:
    """Write state.json atomically: temp file + rename, never partial."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    serialised = json.dumps(state, ensure_ascii=False, indent=2)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=state_path.parent,
        prefix=state_path.name + ".",
        suffix=".tmp",
    ) as tf:
        tf.write(serialised)
        tmp_path = Path(tf.name)
    os.replace(tmp_path, state_path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_positive_int(name: str, value: int) -> None:
    if value < 1:
        raise RuntimeError(f"{name} must be >= 1.")


def validate_nonnegative_int(name: str, value: int) -> None:
    if value < 0:
        raise RuntimeError(f"{name} must be >= 0.")


def read_segments(path: Path) -> list[SegmentRow]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        ensure_csv_columns(reader, SEGMENT_SCHEMA, path)
        rows = [
            SegmentRow(
                segment_id=(row.get("segment_id") or "").strip(),
                zh=(row.get("zh-CN") or "").strip(),
                ko=(row.get("ko") or "").strip(),
            )
            for row in reader
        ]
    if not rows:
        raise RuntimeError(f"No segment rows found: {path}")
    return rows


def read_glossary(path: Path) -> list[GlossaryTerm]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        ensure_csv_columns(reader, GLOSSARY_SCHEMA, path)
        rows = [
            GlossaryTerm(
                term_id=(row.get("term_id") or "").strip(),
                zh=(row.get("zh-CN") or "").strip(),
                ko=(row.get("ko") or "").strip(),
            )
            for row in reader
            if (row.get("zh-CN") or "").strip() and (row.get("ko") or "").strip()
        ]
    if not rows:
        raise RuntimeError(f"No glossary rows found: {path}")
    return rows


def make_batches(rows: list[SegmentRow], batch_size: int) -> list[list[SegmentRow]]:
    return [rows[index : index + batch_size] for index in range(0, len(rows), batch_size)]


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


def build_request_payload(
    model: str,
    batch: list[SegmentRow],
    glossary_sorted: list[GlossaryTerm],
    temperature: float,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in batch:
        features = build_features(row, glossary_sorted)
        rows.append(
            {
                "segment_id": row.segment_id,
                "zh-CN": row.zh,
                "ko": row.ko,
                "placeholder_tokens": features.placeholders,
                "glossary_terms": [
                    {"term_id": term.term_id, "zh-CN": term.zh, "ko": term.ko}
                    for term in features.glossary_terms
                ],
            }
        )

    user_payload = {
        "task": "Review every segment row independently and optionally rewrite only Korean.",
        "allowed_actions": sorted(VALID_ACTIONS),
        "policy": [
            "Judge each row by its own Chinese and Korean meaning; do not bulk-apply a surface rule across the batch.",
            "Use the glossary_terms only as required terminology constraints for this row.",
            "Use placeholder_tokens only to preserve machine placeholders; do not treat placeholders alone as a removal reason.",
            "Keep usable seq2seq sentence or phrase pairs, even if they are short UI text.",
            "Remove only when this row is not a trainable segment, is a bad semantic pair, or has unusable target-language content.",
            "Use REWRITE_KO only when a natural Korean target is clearly derivable from zh-CN and the glossary constraints.",
            "If uncertain, choose REVIEW_UNCERTAIN rather than guessing.",
            "The reason must mention this row's own semantic issue or why it is usable; do not return generic rule labels.",
            "Do not change zh-CN, add rows, split rows, merge rows, or output explanations outside JSON.",
            "corrected_ko must always be a string; use \"\" (empty string, never null) when the action is not REWRITE_KO.",
        ],
        "output_schema": {
            "results": [
                {
                    "segment_id": "same string as input",
                    "action": "one allowed action",
                    "reason": "short reason",
                    "corrected_ko": "required only for REWRITE_KO, otherwise empty",
                }
            ]
        },
        "rows": rows,
    }
    payload: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        # Strict json_schema rejects malformed shapes server-side and lets
        # the local parser drop its regex fallback. Every row must include
        # corrected_ko as a string (empty for non-REWRITE actions).
        "response_format": {
            "type": "json_schema",
            "json_schema": _segments_response_schema(),
        },
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    }
    if max_output_tokens is not None:
        payload["max_tokens"] = max_output_tokens
    return payload


def _recover_truncated_results(content: str) -> dict[str, Any]:
    """Extract whatever complete result objects exist in a truncated JSON response.

    The model output is cut mid-array; we walk the content with a JSON decoder
    to collect every fully-formed object before the truncation point.
    """
    decoder = json.JSONDecoder()
    results: list[Any] = []
    start = content.find("[")
    if start == -1:
        return {"results": results}
    pos = start + 1
    while pos < len(content):
        tail = content[pos:].lstrip()
        if not tail or tail[0] == "]":
            break
        skip = len(content[pos:]) - len(tail)
        try:
            obj, end = decoder.raw_decode(tail)
        except json.JSONDecodeError:
            break
        if isinstance(obj, dict):
            results.append(obj)
        pos += skip + end
        while pos < len(content) and content[pos] in ", \t\n\r":
            pos += 1
    return {"results": results}


def parse_and_validate_response(
    response: dict[str, Any], batch: list[SegmentRow]
) -> list[Decision]:
    choices = response.get("choices") or []
    finish_reason = choices[0].get("finish_reason") if choices else None
    truncated = finish_reason == "length"

    content = extract_message_content(response)
    try:
        payload = parse_json_content(content)
    except RuntimeError:
        if truncated:
            payload = _recover_truncated_results(content)
        else:
            raise

    results = payload.get("results")
    if not isinstance(results, list):
        if truncated:
            results = []
        else:
            raise RuntimeError("LLM response JSON must contain a 'results' list.")

    expected_ids = {row.segment_id for row in batch}
    decisions: dict[str, Decision] = {}
    for index, item in enumerate(results, 1):
        if not isinstance(item, dict):
            if not truncated:
                raise RuntimeError(f"Result #{index} must be a JSON object.")
            continue
        segment_id = str(item.get("segment_id", "")).strip()
        action = str(item.get("action", "")).strip()
        reason = str(item.get("reason", "")).strip()
        corrected_ko = str(item.get("corrected_ko", "")).strip()
        if segment_id not in expected_ids:
            if not truncated:
                print(
                    f"WARNING: Unexpected segment_id {segment_id!r} in LLM result "
                    f"(finish_reason={finish_reason!r}); ignoring."
                )
            continue
        if segment_id in decisions:
            if not truncated:
                print(
                    f"WARNING: Duplicate segment_id {segment_id!r} in LLM result "
                    f"(finish_reason={finish_reason!r}); keeping first occurrence."
                )
            continue
        if action not in VALID_ACTIONS:
            if not truncated:
                print(
                    f"WARNING: Invalid action {action!r} for segment_id {segment_id!r} "
                    f"(finish_reason={finish_reason!r}); marking as {REVIEW_ACTION}."
                )
                action = REVIEW_ACTION
                reason = reason or f"invalid action {action!r} from LLM"
            else:
                continue
        if not reason:
            if not truncated:
                print(
                    f"WARNING: Missing reason for segment_id {segment_id!r} "
                    f"(finish_reason={finish_reason!r}); using placeholder."
                )
                reason = "no reason provided by LLM"
            else:
                continue
        if action == REWRITE_ACTION and not corrected_ko:
            # Model returned REWRITE_KO with empty corrected_ko — demote to REVIEW.
            if not truncated:
                print(
                    f"WARNING: REWRITE_KO missing corrected_ko for segment_id {segment_id!r}; "
                    f"demoting to {REVIEW_ACTION}."
                )
            action = REVIEW_ACTION
            reason = f"REWRITE_KO missing corrected_ko (original reason: {reason})"
        decisions[segment_id] = Decision(segment_id, action, reason, corrected_ko)

    missing = expected_ids - set(decisions)
    if missing:
        reason = (
            "response truncated by token limit"
            if truncated
            else "segment omitted from LLM response"
        )
        if not truncated:
            print(
                f"WARNING: LLM response missing segment_id(s) {sorted(missing)} "
                f"(finish_reason={finish_reason!r}); marking as {REVIEW_ACTION}."
            )
        for seg_id in missing:
            decisions[seg_id] = Decision(
                segment_id=seg_id,
                action=REVIEW_ACTION,
                reason=reason,
                corrected_ko="",
            )
    return [decisions[row.segment_id] for row in batch]


def extract_message_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("LLM response has no choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise RuntimeError("LLM response choice must be an object.")
    message = first.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("LLM response choice has no message object.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM response message content is empty.")
    return content.strip()


def build_features(row: SegmentRow, glossary_sorted: list[GlossaryTerm]) -> SegmentFeatures:
    placeholders = sorted(set(PLACEHOLDER_RE.findall(f"{row.zh} {row.ko}")))
    glossary_terms = find_glossary_terms(row.zh, glossary_sorted)
    return SegmentFeatures(
        placeholders=placeholders,
        glossary_terms=glossary_terms,
        target_contamination=target_is_contaminated(row.ko),
        structured_hint=bool(STRUCTURED_RE.search(row.zh) or STRUCTURED_RE.search(row.ko)),
    )


def find_glossary_terms(text: str, glossary_sorted: list[GlossaryTerm]) -> list[GlossaryTerm]:
    matches: list[tuple[int, int, GlossaryTerm]] = []
    occupied: list[tuple[int, int]] = []
    for term in glossary_sorted:
        start = text.find(term.zh)
        while start != -1:
            end = start + len(term.zh)
            if not any(start < used_end and end > used_start for used_start, used_end in occupied):
                matches.append((start, end, term))
                occupied.append((start, end))
                break
            start = text.find(term.zh, start + 1)
    return [term for _, _, term in sorted(matches, key=lambda item: item[0])]


def target_is_contaminated(text: str) -> bool:
    return bool(CJK_RE.search(text) or (text.strip() and not HANGUL_RE.search(text)))


def build_outcome(
    row: SegmentRow, decision: Decision, features: SegmentFeatures
) -> RowOutcome:
    if decision.action in REMOVE_ACTIONS:
        return RowOutcome(
            row=row,
            decision=decision,
            features=features,
            final_action="REMOVE",
            validation_status="REMOVE_REQUESTED",
            validation_errors=[],
            final_ko="",
        )
    if decision.action == REWRITE_ACTION:
        errors = validate_rewrite(row, decision.corrected_ko, features)
        if not errors:
            return RowOutcome(
                row=row,
                decision=decision,
                features=features,
                final_action="REWRITE",
                validation_status="REWRITE_ACCEPTED",
                validation_errors=[],
                final_ko=decision.corrected_ko,
            )
        if features.target_contamination:
            return RowOutcome(
                row=row,
                decision=decision,
                features=features,
                final_action="REMOVE",
                validation_status="REWRITE_REJECTED_REMOVE_CONTAMINATED",
                validation_errors=errors,
                final_ko="",
            )
        return RowOutcome(
            row=row,
            decision=decision,
            features=features,
            final_action="KEEP",
            validation_status="REWRITE_REJECTED",
            validation_errors=errors,
            final_ko=row.ko,
        )
    if decision.action == REVIEW_ACTION:
        return RowOutcome(
            row=row,
            decision=decision,
            features=features,
            final_action="REVIEW",
            validation_status="REVIEW",
            validation_errors=[],
            final_ko=row.ko,
        )
    return RowOutcome(
        row=row,
        decision=decision,
        features=features,
        final_action="KEEP",
        validation_status="KEEP",
        validation_errors=[],
        final_ko=row.ko,
    )


def validate_rewrite(
    row: SegmentRow, corrected_ko: str, features: SegmentFeatures
) -> list[str]:
    errors: list[str] = []
    if not corrected_ko.strip():
        errors.append("empty_corrected_ko")
    if CJK_RE.search(corrected_ko):
        errors.append("corrected_ko_contains_cjk")
    if not HANGUL_RE.search(corrected_ko):
        errors.append("corrected_ko_has_no_hangul")
    expected_placeholders = set(features.placeholders)
    corrected_placeholders = set(PLACEHOLDER_RE.findall(corrected_ko))
    if expected_placeholders - corrected_placeholders:
        errors.append("placeholder_missing")
    if corrected_placeholders - expected_placeholders:
        errors.append("placeholder_extra")
    if any(not term_preserved(term.ko, corrected_ko) for term in features.glossary_terms):
        errors.append("glossary_term_missing")
    if looks_like_copy_or_explanation(row.zh, corrected_ko):
        errors.append("copy_or_explanation_like")
    if has_bad_length_ratio(row.ko, corrected_ko):
        errors.append("length_ratio_outlier")
    if has_excessive_repetition(corrected_ko):
        errors.append("excessive_repetition")
    return errors


def term_preserved(term_ko: str, text: str) -> bool:
    return term_ko in text or remove_spaces(term_ko) in remove_spaces(text)


def remove_spaces(text: str) -> str:
    return re.sub(r"\s+", "", text)


def looks_like_copy_or_explanation(source: str, corrected_ko: str) -> bool:
    if CJK_RE.search(corrected_ko):
        return True
    if source.strip() and corrected_ko.strip() == source.strip():
        return True
    return bool(EXPLANATION_RE.search(corrected_ko))


def has_bad_length_ratio(original_ko: str, corrected_ko: str) -> bool:
    original_len = max(len(original_ko.strip()), 1)
    corrected_len = len(corrected_ko.strip())
    return corrected_len > max(240, original_len * 4) or corrected_len < max(1, original_len // 8)


def has_excessive_repetition(text: str) -> bool:
    tokens = [token for token in re.split(r"\s+", text.strip()) if token]
    if len(tokens) >= 8:
        most_common = max(tokens.count(token) for token in set(tokens))
        return most_common / len(tokens) > 0.55
    return bool(re.search(r"(.{2,12})\1{4,}", text))


def write_review_files(
    review_dir: Path,
    outcomes: list[RowOutcome],
    total_usage: dict[str, int],
    client_config: ClientConfig,
    apply_changes: bool,
    sample_review_rows: int,
) -> None:
    audit_rows = [audit_row(outcome) for outcome in outcomes]
    removed = [outcome for outcome in outcomes if outcome.final_action == "REMOVE"]
    rewritten = [outcome for outcome in outcomes if outcome.final_action == "REWRITE"]
    rewrite_failed = [
        outcome for outcome in outcomes if outcome.validation_status.startswith("REWRITE_REJECTED")
    ]
    warnings = warning_rows(outcomes)
    write_csv(review_dir / "segments_llm_audit.csv", AUDIT_FIELDS, audit_rows)
    write_csv(review_dir / "removed_segments_llm.csv", REMOVED_FIELDS, removed_rows(removed))
    write_csv(review_dir / "rewritten_segments_llm.csv", REWRITTEN_FIELDS, rewritten_rows(rewritten))
    write_csv(
        review_dir / "rewrite_failed_segments_llm.csv",
        REWRITE_FAILED_FIELDS,
        rewrite_failed_rows(rewrite_failed),
    )
    write_csv(
        review_dir / "segments_llm_sample_review.csv",
        SAMPLE_REVIEW_FIELDS,
        sample_review(outcomes, sample_review_rows),
    )
    write_csv(review_dir / "segments_llm_warnings.csv", WARNING_FIELDS, warnings)
    write_csv(
        review_dir / "segments_llm_summary.csv",
        SUMMARY_FIELDS,
        summary_rows(outcomes, total_usage, client_config, apply_changes, warnings),
    )


def audit_row(outcome: RowOutcome) -> dict[str, str]:
    return {
        "original_segment_id": outcome.row.segment_id,
        "final_action": outcome.final_action,
        "llm_action": outcome.decision.action,
        "validation_status": outcome.validation_status,
        "reason": outcome.decision.reason,
        "validation_errors": ";".join(outcome.validation_errors),
        "placeholder_tokens": ";".join(outcome.features.placeholders),
        "glossary_terms": format_terms(outcome.features.glossary_terms),
        "target_contamination": "YES" if outcome.features.target_contamination else "NO",
        "structured_hint": "YES" if outcome.features.structured_hint else "NO",
        "zh-CN": outcome.row.zh,
        "original_ko": outcome.row.ko,
        "corrected_ko": outcome.decision.corrected_ko,
        "final_ko": outcome.final_ko,
    }


def removed_rows(outcomes: list[RowOutcome]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for removed_id, outcome in enumerate(outcomes, 1):
        rows.append(
            {
                "removed_id": str(removed_id),
                "original_segment_id": outcome.row.segment_id,
                "remove_reason": outcome.validation_status,
                "llm_action": outcome.decision.action,
                "reason": outcome.decision.reason,
                "zh-CN": outcome.row.zh,
                "ko": outcome.row.ko,
                "corrected_ko": outcome.decision.corrected_ko,
            }
        )
    return rows


def rewritten_rows(outcomes: list[RowOutcome]) -> list[dict[str, str]]:
    return [
        {
            "rewrite_id": str(index),
            "original_segment_id": outcome.row.segment_id,
            "reason": outcome.decision.reason,
            "zh-CN": outcome.row.zh,
            "original_ko": outcome.row.ko,
            "corrected_ko": outcome.final_ko,
            "glossary_terms": format_terms(outcome.features.glossary_terms),
        }
        for index, outcome in enumerate(outcomes, 1)
    ]


def rewrite_failed_rows(outcomes: list[RowOutcome]) -> list[dict[str, str]]:
    return [
        {
            "failed_id": str(index),
            "original_segment_id": outcome.row.segment_id,
            "reason": outcome.decision.reason,
            "validation_errors": ";".join(outcome.validation_errors),
            "zh-CN": outcome.row.zh,
            "original_ko": outcome.row.ko,
            "corrected_ko": outcome.decision.corrected_ko,
            "glossary_terms": format_terms(outcome.features.glossary_terms),
        }
        for index, outcome in enumerate(outcomes, 1)
    ]


def sample_review(outcomes: list[RowOutcome], limit: int) -> list[dict[str, str]]:
    if limit == 0:
        return []
    grouped: dict[str, list[RowOutcome]] = {
        "REMOVE": [],
        "REWRITE": [],
        "REVIEW": [],
        "KEEP": [],
    }
    for outcome in outcomes:
        grouped.setdefault(outcome.final_action, []).append(outcome)

    selected: list[RowOutcome] = []
    indexes = {action: 0 for action in grouped}
    order = ["REMOVE", "REWRITE", "REVIEW", "KEEP"]
    while len(selected) < limit:
        added = False
        for action in order:
            index = indexes[action]
            if index < len(grouped[action]):
                selected.append(grouped[action][index])
                indexes[action] += 1
                added = True
                if len(selected) >= limit:
                    break
        if not added:
            break

    rows: list[dict[str, str]] = []
    for sample_id, outcome in enumerate(selected, 1):
        rows.append(
            {
                "sample_id": str(sample_id),
                "original_segment_id": outcome.row.segment_id,
                "final_action": outcome.final_action,
                "llm_action": outcome.decision.action,
                "validation_status": outcome.validation_status,
                "reason": outcome.decision.reason,
                "validation_errors": ";".join(outcome.validation_errors),
                "zh-CN": outcome.row.zh,
                "original_ko": outcome.row.ko,
                "corrected_ko": outcome.decision.corrected_ko,
                "final_ko": outcome.final_ko,
            }
        )
    return rows


def warning_rows(outcomes: list[RowOutcome]) -> list[dict[str, str]]:
    return reason_repetition_warnings(outcomes) + surface_feature_action_warnings(outcomes)


def reason_repetition_warnings(outcomes: list[RowOutcome]) -> list[dict[str, str]]:
    by_batch: dict[int, list[RowOutcome]] = {}
    for outcome in outcomes:
        by_batch.setdefault(outcome.decision.batch_no, []).append(outcome)

    rows: list[dict[str, str]] = []
    for batch_no, batch_outcomes in sorted(by_batch.items()):
        if len(batch_outcomes) < REASON_REPETITION_MIN_BATCH_ROWS:
            continue
        counts: dict[str, int] = {}
        examples: dict[str, str] = {}
        for outcome in batch_outcomes:
            normalized = normalize_reason(outcome.decision.reason)
            counts[normalized] = counts.get(normalized, 0) + 1
            examples.setdefault(normalized, outcome.decision.reason)
        reason, count = max(counts.items(), key=lambda item: item[1])
        rate = count / len(batch_outcomes)
        if rate >= REASON_REPETITION_WARNING_RATE:
            rows.append(
                {
                    "warning_type": "batch_reason_repetition_warning",
                    "scope": f"batch-{batch_no}",
                    "value": examples[reason],
                    "count": str(count),
                    "rate": format_rate(rate),
                    "details": f"{count}/{len(batch_outcomes)} rows share the same normalized reason",
                }
            )
    return rows


def surface_feature_action_warnings(outcomes: list[RowOutcome]) -> list[dict[str, str]]:
    feature_groups: list[tuple[str, list[RowOutcome]]] = [
        (
            "target_contamination",
            [outcome for outcome in outcomes if outcome.features.target_contamination],
        ),
        ("structured_hint", [outcome for outcome in outcomes if outcome.features.structured_hint]),
        ("has_placeholders", [outcome for outcome in outcomes if outcome.features.placeholders]),
        ("has_glossary_terms", [outcome for outcome in outcomes if outcome.features.glossary_terms]),
    ]
    rows: list[dict[str, str]] = []
    for feature_name, group in feature_groups:
        if len(group) < SURFACE_FEATURE_WARNING_MIN_ROWS:
            continue
        final_actions = {outcome.final_action for outcome in group}
        if len(final_actions) == 1:
            action = next(iter(final_actions))
            rows.append(
                {
                    "warning_type": "surface_feature_single_final_action_warning",
                    "scope": feature_name,
                    "value": action,
                    "count": str(len(group)),
                    "rate": "1.000000",
                    "details": f"All rows with local feature {feature_name}=YES ended as {action}",
                }
            )
        llm_actions = {outcome.decision.action for outcome in group}
        if len(llm_actions) == 1:
            action = next(iter(llm_actions))
            rows.append(
                {
                    "warning_type": "surface_feature_single_llm_action_warning",
                    "scope": feature_name,
                    "value": action,
                    "count": str(len(group)),
                    "rate": "1.000000",
                    "details": f"All rows with local feature {feature_name}=YES received {action}",
                }
            )
    return rows


def normalize_reason(reason: str) -> str:
    return re.sub(r"\s+", " ", reason.strip().casefold())


def format_rate(value: float) -> str:
    return f"{value:.6f}"


def summary_rows(
    outcomes: list[RowOutcome],
    total_usage: dict[str, int],
    client_config: ClientConfig,
    apply_changes: bool,
    warnings: list[dict[str, str]],
) -> list[dict[str, str]]:
    counts: dict[str, int] = {}
    llm_counts: dict[str, int] = {}
    for outcome in outcomes:
        counts[outcome.final_action] = counts.get(outcome.final_action, 0) + 1
        llm_counts[outcome.decision.action] = llm_counts.get(outcome.decision.action, 0) + 1
    rewrite_requested = llm_counts.get(REWRITE_ACTION, 0)
    rewrite_accepted = counts.get("REWRITE", 0)
    rewrite_rejected = sum(
        1 for outcome in outcomes if outcome.validation_status.startswith("REWRITE_REJECTED")
    )
    max_reason_count, max_reason_rate = global_reason_repetition(outcomes)
    rows = [
        {"metric": "mode", "value": "apply" if apply_changes else "dry-run"},
        {"metric": "model", "value": client_config.model},
        {"metric": "input_rows", "value": str(len(outcomes))},
        {"metric": "output_rows", "value": str(counts.get("KEEP", 0) + counts.get("REWRITE", 0) + counts.get("REVIEW", 0))},
        {"metric": "kept_rows", "value": str(counts.get("KEEP", 0))},
        {"metric": "removed_rows", "value": str(counts.get("REMOVE", 0))},
        {"metric": "rewritten_rows", "value": str(counts.get("REWRITE", 0))},
        {"metric": "review_rows", "value": str(counts.get("REVIEW", 0))},
        {"metric": "rewrite_requested_rows", "value": str(rewrite_requested)},
        {"metric": "rewrite_accepted_rows", "value": str(rewrite_accepted)},
        {"metric": "rewrite_rejected_rows", "value": str(rewrite_rejected)},
        {"metric": "rewrite_accept_rate", "value": format_rate(rewrite_accepted / rewrite_requested) if rewrite_requested else "0.000000"},
        {"metric": "rewrite_reject_rate", "value": format_rate(rewrite_rejected / rewrite_requested) if rewrite_requested else "0.000000"},
        {"metric": "rewrite_failed_rows", "value": str(rewrite_rejected)},
        {"metric": "max_reason_repetition_count", "value": str(max_reason_count)},
        {"metric": "max_reason_repetition_rate", "value": format_rate(max_reason_rate)},
        {
            "metric": "reason_repetition_warning_batches",
            "value": str(
                sum(
                    1
                    for warning in warnings
                    if warning["warning_type"] == "batch_reason_repetition_warning"
                )
            ),
        },
        {
            "metric": "surface_feature_warning_rows",
            "value": str(
                sum(
                    1
                    for warning in warnings
                    if warning["warning_type"].startswith("surface_feature_")
                )
            ),
        },
        {"metric": "prompt_tokens", "value": str(total_usage.get("prompt_tokens", 0))},
        {"metric": "completion_tokens", "value": str(total_usage.get("completion_tokens", 0))},
        {"metric": "total_tokens", "value": str(total_usage.get("total_tokens", 0))},
    ]
    for action in sorted(counts):
        rows.append({"metric": f"final_action.{action}", "value": str(counts[action])})
    for action in sorted(llm_counts):
        rows.append({"metric": f"llm_action.{action}", "value": str(llm_counts[action])})
    return rows


def global_reason_repetition(outcomes: list[RowOutcome]) -> tuple[int, float]:
    if not outcomes:
        return 0, 0.0
    counts: dict[str, int] = {}
    for outcome in outcomes:
        normalized = normalize_reason(outcome.decision.reason)
        counts[normalized] = counts.get(normalized, 0) + 1
    max_count = max(counts.values(), default=0)
    return max_count, max_count / len(outcomes)


def format_terms(terms: list[GlossaryTerm]) -> str:
    return ";".join(f"{term.term_id}:{term.zh}->{term.ko}" for term in terms)


def write_segments(path: Path, outcomes: list[RowOutcome]) -> None:
    output: list[dict[str, str]] = []
    for new_id, outcome in enumerate(
        [outcome for outcome in outcomes if outcome.final_action != "REMOVE"], 1
    ):
        output.append(
            {
                "segment_id": str(new_id),
                "zh-CN": outcome.row.zh,
                "ko": outcome.final_ko,
            }
        )
    write_csv(path, SEGMENT_SCHEMA, output)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_raw_batch(
    raw_dir: Path,
    batch_no: int,
    attempt: int,
    request_payload: dict[str, Any],
    response: dict[str, Any] | None,
    error: str | None,
) -> None:
    path = raw_dir / f"batch-{batch_no:04d}-attempt-{attempt}.json"
    payload = {
        "batch_no": batch_no,
        "attempt": attempt,
        "request": request_payload,
        "response": response,
        "error": error,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def print_result(result: CleanupResult) -> None:
    print("Segments LLM cleanup completed.")
    print(f"mode={result.mode}")
    print(f"model={result.model}")
    print(f"input_rows={result.input_rows}")
    print(f"output_rows={result.output_rows}")
    print(f"kept_rows={result.kept_rows}")
    print(f"removed_rows={result.removed_rows}")
    print(f"rewritten_rows={result.rewritten_rows}")
    print(f"rewrite_failed_rows={result.rewrite_failed_rows}")
    print(f"review_rows={result.review_rows}")
    print(f"review_dir={result.review_dir}")
    print(f"prompt_tokens={result.total_prompt_tokens}")
    print(f"completion_tokens={result.total_completion_tokens}")
    print(f"total_tokens={result.total_tokens}")
    for action, count in sorted(result.action_counts.items()):
        print(f"final_action.{action}={count}")


if __name__ == "__main__":
    raise SystemExit(main())
