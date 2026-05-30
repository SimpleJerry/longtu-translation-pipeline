# T-F2 · RF-025 · Add COMET metric to evaluation

> Status: PENDING (optional, larger lift) | Blocked-by: T-A3 (need a real generation CSV) | Parallel-safe with: T-B*, T-C*, T-D*, T-E*, T-F1 not editing the same lines

> Touches: `src/longtu_translation_pipeline/evaluation.py` (new metric module recommended), `requirements-training.txt` (COMET dep), `configs/evaluation/*.json`, `tests/test_evaluation.py`, README

## Why

COMET (unbabel-comet) is a learned reference-based MT metric that
correlates better than BLEU/chrF with human judgment, especially for
mid-resource pairs like zh→ko. It is **optional** because:
- The COMET model is large (downloads on first use, ~1.5GB)
- It runs on GPU (or slow CPU)
- It adds a non-trivial dependency

Only do this if the user wants COMET as a regular metric.

## Prerequisites

1. T-A3 produces at least one generation CSV (validation or test).
2. GPU available, or willingness to run on CPU.

## Shared context (read these first)

- [ADR-0012](../../decisions/adr/ADR-0012-evaluation-uses-bleu-and-glossary-preservation-only.md) — Evaluation Uses BLEU and Glossary Preservation Only (adding COMET expands the contract; record this decision change as a new ADR in `docs/decisions/adr/` as part of the commit)
- COMET docs: https://unbabel.github.io/COMET/html/index.html
  (`unbabel-comet` Python package)
- T-F1 (chrF) — same pattern, easier; confirm T-F1 is committed
  first if you want a chrF row in the same report

## Files to read first

- `src/longtu_translation_pipeline/evaluation.py` — current
  `EvaluationResult` and `format_evaluation_summary`
- `tests/test_evaluation.py` — mock pattern for any external model
- `requirements-training.txt` — where COMET goes
- A generation CSV from T-A3 (or pilot) — schema:
  `segment_id,source,references,candidates`

## Don't touch

- BLEU / chrF / glossary preservation
- Training, inference
- Data files

## Modification surface

1. New module `src/longtu_translation_pipeline/comet_metric.py`:
   - `compute_comet(sources, references, candidates, model_name='Unbabel/wmt22-comet-da')`
   - Lazy import `comet` (so the rest of the package doesn't load it)
   - Cache the loaded model in a module-level variable
2. `evaluation.py`:
   - Add `comet_score` to `EvaluationResult`
   - In `evaluate_translation`, if config flag `comet_enabled=true`,
     call `compute_comet` (else skip)
   - `format_evaluation_summary` writes the COMET row when present
3. `requirements-training.txt`:
   - Add `unbabel-comet==<latest>` (pin exact version)
4. `configs/evaluation/generation_report.json`:
   - Add `"comet_enabled": false` (off by default — opt-in)
   - Add `"comet_model": "Unbabel/wmt22-comet-da"`
5. Tests:
   - With `comet_enabled=false`, current behavior unchanged
   - With `comet_enabled=true` and a mocked `compute_comet`,
     `comet_score` shows up in the summary
   - Mock pattern: `unittest.mock.patch(...,
     return_value=<deterministic>)`
6. Decision log: add a new ADR file in `docs/decisions/adr/`
   noting that evaluation now optionally includes COMET, with the
   default off (expands [ADR-0012](../../decisions/adr/ADR-0012-evaluation-uses-bleu-and-glossary-preservation-only.md)).
7. README: brief note that COMET is available, off by default,
   requires `requirements-training.txt` to be installed.

## Acceptance criteria

1. With `comet_enabled=false` (default), reports look identical to
   before T-F2.
2. With `comet_enabled=true` and the dependency installed, a
   `comet_score` row appears in `evaluation_summary.csv` and
   `comet_score` is in `report_manifest.json`.
3. Tests do not download COMET models (mock the call).
4. README explains the opt-in and the cost.
5. Backlog entry RF-025 set to `DONE`.
6. decisions.md gains the "evaluation may include COMET" entry.

## Verification

```powershell
venv\Scripts\python.exe -m unittest tests.test_evaluation -v
# With config flag off:
venv\Scripts\python.exe scripts\evaluate_translation.py `
    --config configs\evaluation\generation_report.json `
    --checkpoint <any checkpoint>
# Expect: no comet row.

# With flag on (requires a custom config file with comet_enabled=true):
# Manual smoke after the run; expect a comet row.

venv\Scripts\python.exe -m unittest discover -s tests
git -c safe.directory=D:/longtu-translation-pipeline diff --check
```

## Git workflow

- One commit, message: `Add optional COMET metric to evaluation (RF-025)`.
- Note in the commit body: COMET is opt-in and requires
  `requirements-training.txt` install.
- Do not push.
- Update RF-025 status to `DONE` in the same commit.
