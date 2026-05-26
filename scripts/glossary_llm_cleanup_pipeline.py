"""Aggressively prune glossary rows with an OpenAI-compatible LLM.

This pipeline is intentionally delete-only.  It sends the current
``data/glossary.csv`` term pairs to a cloud LLM and asks whether each pair
should remain in the company game glossary.  The model may keep or remove rows,
but it must not rewrite Korean, add terms, or merge entries.  Review artifacts
are written under ignored ``data/review/`` paths.
"""

from __future__ import annotations

import argparse
import csv
import json
import locale
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

try:
    from cleanup_common import ensure_csv_columns
    from llm_common import ClientConfig, call_chat_completion, parse_json_content, resolve_client_config
except ModuleNotFoundError:  # pragma: no cover - import fallback for tests
    from scripts.cleanup_common import ensure_csv_columns
    from scripts.llm_common import ClientConfig, call_chat_completion, parse_json_content, resolve_client_config


GLOSSARY_SCHEMA = ["term_id", "zh-CN", "ko"]
SUMMARY_FIELDS = ["metric", "value"]
AUDIT_FIELDS = [
    "original_term_id",
    "action",
    "keep",
    "reason",
    "zh-CN",
    "ko",
]
REMOVED_FIELDS = [
    "removed_id",
    "original_term_id",
    "action",
    "reason",
    "zh-CN",
    "ko",
]

KEEP_ACTION = "KEEP_GAME_TERM"
REMOVE_ACTIONS = {
    "REMOVE_COMMON_WORD",
    "REMOVE_PHRASE_OR_SENTENCE",
    "REMOVE_FRAGMENT",
    "REMOVE_BAD_PAIR",
    "REMOVE_NOT_COMPANY_GAME_TERM",
}
VALID_ACTIONS = {KEEP_ACTION, *REMOVE_ACTIONS}

SYSTEM_PROMPT = (
    "You are cleaning a Chinese-Korean glossary for one company's game "
    "localization project. Keep only entries that deserve to be enforced as "
    "game terminology: game systems, skills, equipment, attributes, currencies, "
    "proper names, monsters, maps, titles, item names, and established game "
    "acronyms. Remove ordinary dictionary words, UI phrases, sentence-like "
    "content, fragments, invalid pairs, or entries that should not be company "
    "game glossary terms. Do not rewrite Korean, do not add terms, and do not "
    "merge terms. Return strict JSON only."
)


@dataclass(frozen=True)
class GlossaryRow:
    term_id: str
    zh: str
    ko: str


@dataclass(frozen=True)
class Decision:
    term_id: str
    action: str
    reason: str


@dataclass(frozen=True)
class CleanupResult:
    mode: str
    input_rows: int
    kept_rows: int
    removed_rows: int
    review_dir: Path
    model: str
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    action_counts: dict[str, int]


Client = Callable[[dict[str, Any], ClientConfig, float, int], dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete-only cloud LLM cleanup for data/glossary.csv."
    )
    parser.add_argument("--glossary", default="data/glossary.csv")
    parser.add_argument(
        "--review-dir", default="data/review/llm_glossary_cleanup"
    )
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override OPENAI_BASE_URL. Defaults to https://api.openai.com/v1.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override LLM_MODEL. The repository intentionally has no default.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Write review only.")
    mode.add_argument("--apply", action="store_true", help="Rewrite glossary.csv.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mode = "apply" if args.apply else "dry-run"
    try:
        result = run_cleanup(
            glossary_path=Path(args.glossary),
            review_dir=Path(args.review_dir),
            apply_changes=args.apply,
            batch_size=args.batch_size,
            max_retries=args.max_retries,
            temperature=args.temperature,
            timeout=args.timeout,
            base_url=args.base_url,
            model=args.model,
        )
    except RuntimeError as exc:
        print(f"Glossary LLM cleanup failed in {mode} mode: {exc}")
        return 1
    print_result(result)
    return 0


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
) -> CleanupResult:
    rows = read_glossary(glossary_path)
    validate_positive_int("batch-size", batch_size)
    validate_positive_int("max-retries", max_retries)
    validate_positive_int("timeout", timeout)

    client_config = resolve_client_config(env or os.environ, base_url, model)
    review_dir.mkdir(parents=True, exist_ok=True)
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
        )
        for key, value in response.get("usage", {}).items():
            if key in total_usage and isinstance(value, int):
                total_usage[key] += value
        decisions.update({decision.term_id: decision for decision in batch_decisions})

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


def read_glossary(path: Path) -> list[GlossaryRow]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        ensure_csv_columns(reader, GLOSSARY_SCHEMA, path)
        rows = [
            GlossaryRow(
                term_id=(row.get("term_id") or "").strip(),
                zh=(row.get("zh-CN") or "").strip(),
                ko=(row.get("ko") or "").strip(),
            )
            for row in reader
        ]
    if not rows:
        raise RuntimeError(f"No glossary rows found: {path}")
    for index, row in enumerate(rows, 1):
        if not row.term_id or not row.zh or not row.ko:
            raise RuntimeError(f"Invalid empty glossary field at input row {index}.")
    return rows


def validate_positive_int(name: str, value: int) -> None:
    if value < 1:
        raise RuntimeError(f"{name} must be >= 1.")


def make_batches(rows: list[GlossaryRow], batch_size: int) -> list[list[GlossaryRow]]:
    return [rows[index : index + batch_size] for index in range(0, len(rows), batch_size)]


def classify_batch(
    batch_no: int,
    batch: list[GlossaryRow],
    client_config: ClientConfig,
    client: Client,
    raw_dir: Path,
    max_retries: int,
    temperature: float,
    timeout: int,
) -> tuple[dict[str, Any], list[Decision]]:
    request_payload = build_request_payload(client_config.model, batch, temperature)
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


def build_request_payload(
    model: str, batch: list[GlossaryRow], temperature: float
) -> dict[str, Any]:
    rows = [
        {"term_id": row.term_id, "zh-CN": row.zh, "ko": row.ko}
        for row in batch
    ]
    user_payload = {
        "task": "Classify every row. Return one result for every input term_id.",
        "allowed_actions": sorted(VALID_ACTIONS),
        "aggressive_policy": "Only KEEP_GAME_TERM rows will remain in glossary.csv.",
        "output_schema": {
            "results": [
                {
                    "term_id": "same string as input",
                    "action": "one allowed action",
                    "reason": "short Chinese or English reason, no rewrite",
                }
            ]
        },
        "rows": rows,
    }
    return {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            },
        ],
    }


def parse_and_validate_response(
    response: dict[str, Any], batch: list[GlossaryRow]
) -> list[Decision]:
    content = extract_message_content(response)
    payload = parse_json_content(content)
    results = payload.get("results")
    if not isinstance(results, list):
        raise RuntimeError("LLM response JSON must contain a 'results' list.")

    expected_ids = {row.term_id for row in batch}
    decisions: dict[str, Decision] = {}
    for index, item in enumerate(results, 1):
        if not isinstance(item, dict):
            raise RuntimeError(f"Result #{index} must be a JSON object.")
        term_id = str(item.get("term_id", "")).strip()
        action = str(item.get("action", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if term_id not in expected_ids:
            raise RuntimeError(f"Unexpected term_id in LLM result: {term_id}")
        if term_id in decisions:
            raise RuntimeError(f"Duplicate term_id in LLM result: {term_id}")
        if action not in VALID_ACTIONS:
            raise RuntimeError(f"Invalid action for term_id {term_id}: {action}")
        if not reason:
            raise RuntimeError(f"Missing reason for term_id {term_id}.")
        decisions[term_id] = Decision(term_id=term_id, action=action, reason=reason)

    missing = expected_ids - set(decisions)
    if missing:
        raise RuntimeError(f"LLM response is missing term_id values: {sorted(missing)}")
    return [decisions[row.term_id] for row in batch]


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


def build_audit_rows(
    rows: list[GlossaryRow], decisions: dict[str, Decision]
) -> list[dict[str, str]]:
    audit_rows: list[dict[str, str]] = []
    for row in rows:
        decision = decisions[row.term_id]
        audit_rows.append(
            {
                "original_term_id": row.term_id,
                "action": decision.action,
                "keep": "YES" if decision.action == KEEP_ACTION else "NO",
                "reason": decision.reason,
                "zh-CN": row.zh,
                "ko": row.ko,
            }
        )
    return audit_rows


def build_summary_rows(
    mode: str,
    rows: list[GlossaryRow],
    audit_rows: list[dict[str, str]],
    client_config: ClientConfig,
    total_usage: dict[str, int],
) -> list[dict[str, str]]:
    kept = sum(1 for row in audit_rows if row["keep"] == "YES")
    removed = len(audit_rows) - kept
    summary = [
        {"metric": "mode", "value": mode},
        {"metric": "model", "value": client_config.model},
        {"metric": "input_rows", "value": str(len(rows))},
        {"metric": "kept_rows", "value": str(kept)},
        {"metric": "removed_rows", "value": str(removed)},
        {
            "metric": "prompt_tokens",
            "value": str(total_usage.get("prompt_tokens", 0)),
        },
        {
            "metric": "completion_tokens",
            "value": str(total_usage.get("completion_tokens", 0)),
        },
        {"metric": "total_tokens", "value": str(total_usage.get("total_tokens", 0))},
    ]
    counts: dict[str, int] = {}
    for row in audit_rows:
        counts[row["action"]] = counts.get(row["action"], 0) + 1
    for action in sorted(counts):
        summary.append({"metric": f"action.{action}", "value": str(counts[action])})
    return summary


def write_removed_csv(path: Path, audit_rows: list[dict[str, str]]) -> None:
    rows: list[dict[str, str]] = []
    for removed_id, row in enumerate(audit_rows, 1):
        rows.append(
            {
                "removed_id": str(removed_id),
                "original_term_id": row["original_term_id"],
                "action": row["action"],
                "reason": row["reason"],
                "zh-CN": row["zh-CN"],
                "ko": row["ko"],
            }
        )
    write_csv(path, REMOVED_FIELDS, rows)


def write_clean_glossary(
    path: Path, rows: list[GlossaryRow], decisions: dict[str, Decision]
) -> None:
    kept_rows = [row for row in rows if decisions[row.term_id].action == KEEP_ACTION]
    sorted_rows = sort_by_chinese(kept_rows)
    output = [
        {"term_id": str(new_id), "zh-CN": row.zh, "ko": row.ko}
        for new_id, row in enumerate(sorted_rows, 1)
    ]
    write_csv(path, GLOSSARY_SCHEMA, output)


def sort_by_chinese(rows: list[GlossaryRow]) -> list[GlossaryRow]:
    try:
        locale.setlocale(locale.LC_COLLATE, "Chinese_China.936")
    except locale.Error:
        try:
            locale.setlocale(locale.LC_COLLATE, "zh_CN.UTF-8")
        except locale.Error:
            locale.setlocale(locale.LC_COLLATE, "")
    return sorted(rows, key=lambda row: locale.strxfrm(row.zh))


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
    payload = {
        "batch_no": batch_no,
        "attempt": attempt,
        "request": request_payload,
        "response": response,
        "error": error,
    }
    path = raw_dir / f"batch-{batch_no:04d}-attempt-{attempt}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def print_result(result: CleanupResult) -> None:
    print("LLM glossary cleanup completed.")
    print(f"mode={result.mode}")
    print(f"model={result.model}")
    print(f"input_rows={result.input_rows}")
    print(f"kept_rows={result.kept_rows}")
    print(f"removed_rows={result.removed_rows}")
    print(f"review_dir={result.review_dir}")
    print(f"prompt_tokens={result.total_prompt_tokens}")
    print(f"completion_tokens={result.total_completion_tokens}")
    print(f"total_tokens={result.total_tokens}")
    for action, count in sorted(result.action_counts.items()):
        print(f"action.{action}={count}")


if __name__ == "__main__":
    raise SystemExit(main())
