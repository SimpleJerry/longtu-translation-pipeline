# T-B1 · RF-017 · Extract `llm_common.py`

> Status: PENDING | Blocked-by: none | Parallel-safe with: T-A1 (recommended before), T-B2, T-B3, T-C*, T-D*, T-E*
> Touches: `scripts/llm_common.py` (new), `scripts/glossary_llm_cleanup_pipeline.py`, `scripts/segments_llm_cleanup_pipeline.py`, `tests/`
> Audit: P1-1 (2026-05-26)

## Why

`scripts/segments_llm_cleanup_pipeline.py` currently imports `ClientConfig`,
`resolve_client_config`, `call_chat_completion`, `parse_json_content`
from `scripts/glossary_llm_cleanup_pipeline.py`. That makes two CLI
scripts depend on each other, which violates `AGENTS.md` "Keep pure
transformation logic in importable modules and keep CLI scripts thin"
and means any change to the glossary script can silently break the
segments script.

This task lifts those four symbols into a single shared module and
points both scripts (and their tests) at it. Doing this *before* the
real full-corpus LLM segment run (T-A1) keeps the LLM client code in a
single audited place.

## Prerequisites

- None.

## Shared context (read these first)

- [docs/refactor/audit-2026-05-26.md](../audit-2026-05-26.md) §P1-1 —
  audit finding and recommended location options
- [AGENTS.md](../../../AGENTS.md) §Code Style — CLI scripts thin
- [docs/refactor/backlog.md](../backlog.md) RF-014 / RF-015 — existing
  LLM cleanup pipelines that consume the shared client

## Files to read first

- `scripts/glossary_llm_cleanup_pipeline.py` — find the four symbols
  (`ClientConfig`, `resolve_client_config`, `call_chat_completion`,
  `parse_json_content`) and their helpers (look near the top, after
  imports)
- `scripts/segments_llm_cleanup_pipeline.py:24` — the reverse import
  to remove
- `tests/test_glossary_llm_cleanup_pipeline.py` and
  `tests/test_segments_llm_cleanup_pipeline.py` — see how they mock
  `call_chat_completion`

## Don't touch

- `data/segments.csv`, `data/glossary.csv` — no data changes
- `configs/` — no config schema changes
- Any function whose behavior is glossary-specific or segments-specific
  (keep those in their respective scripts)

## Modification surface

1. **Create `scripts/llm_common.py`** containing exactly:
   - `ClientConfig` dataclass
   - `resolve_client_config()` (reads `OPENAI_API_KEY`, `OPENAI_BASE_URL`,
     `LLM_MODEL` env vars and fails clearly when missing)
   - `call_chat_completion(...)` (HTTP retry / timeout wrapper)
   - `parse_json_content(...)` (parse JSON-in-text robustness)
   - Optional: a small `__all__` listing them
2. Update `scripts/glossary_llm_cleanup_pipeline.py` to `from llm_common
   import ...` instead of defining them.
3. Update `scripts/segments_llm_cleanup_pipeline.py:24` to `from
   llm_common import ...`.
4. Update tests:
   - `tests/test_glossary_llm_cleanup_pipeline.py` — adjust import paths
     and mock targets if any patch `glossary_llm_cleanup_pipeline.call_chat_completion`
   - `tests/test_segments_llm_cleanup_pipeline.py` — same
5. **Create `tests/test_llm_common.py`** with at least:
   - `resolve_client_config` raises when `OPENAI_API_KEY` missing
   - `resolve_client_config` raises when `LLM_MODEL` missing
   - `parse_json_content` accepts plain JSON, JSON in ```json fences,
     and rejects malformed content with a clear error

## Alternative location (discuss in your commit message)

Two options for the new module:
- **A. `scripts/llm_common.py`** — keeps everything in `scripts/`,
  matches the existing `cleanup_common.py` placement.
- **B. `src/longtu_translation_pipeline/llm_client.py`** — more
  principled (importable package surface), but requires deciding
  whether to re-export from `__init__.py` (which T-D1 is also touching).

Recommend **A** to avoid colliding with T-D1.

## Acceptance criteria

1. `scripts/segments_llm_cleanup_pipeline.py` does not import from
   `glossary_llm_cleanup_pipeline`.
2. Both LLM scripts import the four symbols from `llm_common` only.
3. `tests/test_llm_common.py` exists and passes.
4. `python -m unittest discover -s tests` returns 0 with no regressions
   (current count: 92 passing).
5. Backlog entry RF-017 set to `DONE` with the run output recorded.
6. One clean commit (or two if you separate the move from the test
   addition).

## Verification

```powershell
venv\Scripts\python.exe -m py_compile scripts\llm_common.py scripts\glossary_llm_cleanup_pipeline.py scripts\segments_llm_cleanup_pipeline.py
venv\Scripts\python.exe -m unittest tests.test_llm_common
venv\Scripts\python.exe -m unittest tests.test_glossary_llm_cleanup_pipeline
venv\Scripts\python.exe -m unittest tests.test_segments_llm_cleanup_pipeline
venv\Scripts\python.exe -m unittest discover -s tests
rg -n "from glossary_llm_cleanup_pipeline" scripts tests
# Expect: no matches.
git -c safe.directory=D:/longtu-translation-pipeline diff --check
```

## Git workflow

- One commit, message: `Extract scripts/llm_common.py for shared LLM client (RF-017)`.
- Do not push.
- Update RF-017 status to `DONE` in the same commit (single backlog
  section, no other RF edits).
