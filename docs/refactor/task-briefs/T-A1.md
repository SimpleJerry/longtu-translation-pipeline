# T-A1 · RF-015 completion · Full-corpus LLM segments cleanup apply

> Status: BLOCKED (needs API key + user authorization to spend tokens) | Blocked-by: none in repo; gates Track A2/A3/A4 | Parallel-safe with: T-B*, T-C*, T-D*, T-E* (none of those touch data files)
> Touches: `data/segments.csv`, `docs/refactor/backlog.md` (RF-015 Notes)
> Audit: §P0-1, §P0-2 (resolved); RF-015 still BLOCKED for the *remaining* rows

## Why

`scripts/segments_llm_cleanup_pipeline.py` is implemented and unit-tested,
but the real OpenAI-compatible full run has not been executed end-to-end.
The 2026-05-26 commit `c107763` folded in a *partial* user-confirmed pass
(207 row removes + 17 ko rewrites) that is now recorded in the RF-015
follow-up note. The remaining 66,385 segments still need a full LLM
review pass, after which the corpus is frozen for the new training cycle.

This task spends real API tokens (estimated 5M-10M input + 1.5M-4M
output). At `gpt-4.1-mini` Batch API pricing (50% discount applied
server-side), the full run is expected to cost on the order of US$1.5-3.
Do not start unless the user has authorized the cost.

## Prerequisites

1. `OPENAI_API_KEY` set in the local PowerShell session.
2. `LLM_MODEL` set (e.g. `gpt-4o-mini` or whichever model the user chose).
3. Optionally `OPENAI_BASE_URL` if using a non-OpenAI compatible endpoint.
4. Recommended (not required): T-B1 (extract `llm_common.py`) committed
   first so the LLM client lives in a single audited place.
5. Working tree clean.

## Shared context (read these first)

- [docs/refactor/audit-2026-05-26.md](../audit-2026-05-26.md) §P0-1, §P0-2
- [docs/refactor/decisions.md](../decisions.md) §2026-05-26 "Cloud LLM
  Segment Cleanup May Rewrite Korean With Local Guards" — the policy
  the script enforces
- [docs/refactor/backlog.md](../backlog.md) RF-015 — current status
  and follow-up note
- [docs/data-cleaning.md](../../data-cleaning.md) — segment validation
  rules

## Files to read first

- `scripts/segments_llm_cleanup_pipeline.py` — full file, especially:
  - CLI surface (top of file)
  - LLM payload shape (must send only raw row, placeholders, matched
    glossary — no local pre-judgment fields)
  - Local validation pipeline that runs *after* each LLM response
  - Review CSV layout under `data/review/llm_segments_cleanup/`
- `tests/test_segments_llm_cleanup_pipeline.py` — confirm expected
  shapes of removed / rewritten / rewrite_failed / sample_review CSVs

## Don't touch

- Anything outside `data/segments.csv` and the RF-015 backlog Notes
- `data/glossary.csv` — this run is segments-only
- `configs/` — do not override prompts at run time
- `fine-tuned-models/` — old checkpoints are stale anyway

## Execution recipe (Batch API, default since 2026-05-27)

```powershell
$env:OPENAI_API_KEY = "<your-key>"
$env:LLM_MODEL     = "gpt-4.1-mini"
# Optional:
# $env:OPENAI_BASE_URL = "<base-url>"   # Batch API requires an endpoint that
                                        # supports /v1/batches; the OpenAI
                                        # official endpoint is the default.

# Behaviour: --batch-mode batch is the default; the pipeline uploads one
# JSONL containing all micro-batches (default --batch-size 50), creates a
# /v1/batches job, polls every --poll-interval seconds (default 60), and
# downloads the result. Resumable: re-running with the same --review-dir
# reads batch_state.json and skips already-completed phases.

# 1. Dry-run (writes review CSVs and a sample; still spends real tokens
#    because the batch job must run end-to-end to produce results).
venv\Scripts\python.exe scripts\segments_llm_cleanup_pipeline.py --dry-run

# 2. Manually inspect under data/review/llm_segments_cleanup/:
#      segments_llm_sample_review.csv
#      segments_llm_warnings.csv
#      segments_llm_summary.csv
#      rewrite_failed_segments_llm.csv
#      batch_state.json                  (phase should be 'downloaded')
#      batch_input/all.jsonl             (one request line per micro-batch)
#      batch_output/result.jsonl         (raw model output)
#    Confirm action distribution, rewrite accept rate, and that summary
#    prompt_tokens / completion_tokens / total_tokens look sane.

# 3. If sample is acceptable, apply. The apply pass re-issues a fresh
#    batch job (it does NOT reuse the dry-run state file because the dry-run
#    review-dir already advanced to phase=downloaded). If you want to reuse
#    a previous successful batch, point --review-dir at that directory.
venv\Scripts\python.exe scripts\segments_llm_cleanup_pipeline.py --apply

# 4. Strict gate must pass:
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check
# Expect: strict_current_mismatch_rows=0

# 5. Training dry-run records the new split counts:
venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k.json --dry-run

# 6. Diff segments.csv (rough sanity):
git -c safe.directory=D:/longtu-translation-pipeline diff --stat -- data/segments.csv
```

### Fallback to synchronous mode

If the upstream endpoint does not support `/v1/batches`, or you only need
a small smoke run (< 1k rows), pass `--batch-mode sync`. Per-batch retries
and raw_batches/ dumps work as before:

```powershell
venv\Scripts\python.exe scripts\segments_llm_cleanup_pipeline.py --batch-mode sync --dry-run
```

## What to record in RF-015 follow-up Notes

Append a new follow-up paragraph to RF-015 capturing:
- Date of this pass (local YYYY-MM-DD)
- New `data/segments.csv` row count
- New SHA256 (uppercase, matching `training.py::hash_file`)
- Action distribution from the summary CSV (KEEP / REWRITE / REMOVE
  / REVIEW totals; accept/reject rate for rewrites)
- Strict-check output (the same four lines that the 2026-05-26 note
  records)
- New training dry-run split counts (train/validation/test)
- "All previous run-* directories under fine-tuned-models/ are now
  stale — Track A2 must regenerate."

## Acceptance criteria

1. `data/segments.csv` has a new sha256, recorded in the RF-015
   follow-up Notes.
2. `segments_glossary_cross_cleaning_pipeline.py --strict-check`
   reports `strict_current_mismatch_rows=0` and exits 0.
3. `train_model.py --config full_10k.json --dry-run` succeeds and
   prints new split counts.
4. No new file is checked into Git beyond `data/segments.csv` and
   `docs/refactor/backlog.md`. Review CSVs and raw batches remain
   under ignored `data/review/llm_segments_cleanup/`.
5. RF-015 status remains visible (the work is recorded as a follow-up
   pass, not a brand-new RF; the BLOCKED label can stay or be lifted
   per the user's preference).
6. Commit message: `Apply full-corpus LLM segments cleanup (RF-015 final pass)`.

## Risks

- **Cost** — millions of tokens. Confirm with the user before
  --apply. Dry-run does not call the LLM (or only on a sample,
  depending on the script's current default — check before running).
- **Synthetic data injection** — every rewritten ko goes through local
  validation. If the validation logic has a bug, bad ko could enter
  the corpus. Sample the `rewritten_segments_llm.csv` manually before
  --apply.
- **Stale artifacts** — the moment segments.csv changes, every prior
  run-*/checkpoint-*/report becomes incompatible. They are gitignored
  so won't pollute the repo, but the user should be aware.

## Git workflow

- One commit on a clean working tree. No bundling with other RFs.
- Do not push without explicit user authorization (changing
  segments.csv is a heavyweight commit).
- After commit, ensure `git -c safe.directory=D:/longtu-translation-pipeline diff --check` is clean.
