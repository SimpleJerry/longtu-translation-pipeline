"""Resumable Batch API state persistence (ADR-0030).

Extracted verbatim from the former ``scripts/segments_llm_cleanup_pipeline.py``
under ADR-0033. The batch path persists its phase to ``batch_state.json`` so a
run can resume after interruption; writes are atomic (temp file + os.replace)
so the state file is never left partial.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


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
