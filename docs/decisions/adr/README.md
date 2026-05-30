# Architecture Decision Records

This directory is the project's authoritative Architecture Decision Record (ADR) log.
Each file represents one durable architectural or pipeline decision—something that was
chosen from real alternatives and that constrains future behavior.

`docs/refactor/decisions.md` (the original chronological decision log) has been
superseded by this directory and is now preserved as a historical archive only.

---

| ADR | Title | Status | Date | Summary |
|-----|-------|--------|------|---------|
| [ADR-0001](ADR-0001-readme-and-agents-do-not-carry-long-term-task-pools.md) | README and AGENTS Do Not Carry Long-Term Task Pools | Accepted | 2026-05-17 | README/AGENTS stay focused; all refactor TODOs go to backlog. |
| [ADR-0002](ADR-0002-refactor-backlog-lives-in-docs-refactor-backlog.md) | Refactor Backlog Lives in docs/refactor/backlog.md | Accepted | 2026-05-17 | `docs/refactor/backlog.md` is the single source of truth for refactor tasks. |
| [ADR-0003](ADR-0003-architecture-decisions-log-superseded.md) | Architecture Decisions Log (Superseded) | Superseded | 2026-05-17 | Chronological `decisions.md` replaced by this ADR system. |
| [ADR-0004](ADR-0004-csv-in-git-raw-xlsx-outside-git-tracking.md) | CSV In Git, Raw XLSX Outside Git Tracking | Accepted | 2026-05-17 | Normalized CSVs committed; raw Excel files in `.gitignore`. |
| [ADR-0005](ADR-0005-gradual-engineering-refactor-approach.md) | Gradual Engineering Refactor Approach | Accepted | 2026-05-17 | Incremental refactor; notebooks preserved as experiment records. |
| [ADR-0006](ADR-0006-preserve-public-compatibility-by-default.md) | Preserve Public Compatibility by Default | Accepted | 2026-05-17 | Breaking changes require explicit backlog scope and README updates. |
| [ADR-0007](ADR-0007-segment-evidence-not-sufficient-glossary-keep-signal.md) | Segment Evidence Not Sufficient Glossary Keep Signal | Accepted | 2026-05-22 | Segment presence is a removal gate, not a keep vote. |
| [ADR-0008](ADR-0008-glossary-pipeline-uses-final-glossary-as-baseline.md) | Glossary Pipeline Uses Final Glossary As Baseline | Accepted | 2026-05-24 | Pipeline reads `data/glossary.csv`; audit CSVs are local ignored artifacts. |
| [ADR-0009](ADR-0009-notebook-deletion-requires-inventory-first.md) | Notebook Deletion Requires Inventory First | Accepted | 2026-05-24 | Notebooks archived and inventoried before any deletion. |
| [ADR-0010](ADR-0010-text-protection-uses-single-segment-term-markers.md) | Text Protection Uses Single-Segment Term Markers | Accepted | 2026-05-24 | Only `<start>...<end>`; T&N+R and `<code_id=N>` deprecated. |
| [ADR-0011](ADR-0011-training-inference-configs-use-json-dry-run-entrypoints.md) | Training and Inference Configs Use JSON Dry-Run Entrypoints | Accepted | 2026-05-24 | JSON configs; `--dry-run` never loads models. |
| [ADR-0012](ADR-0012-evaluation-uses-bleu-and-glossary-preservation-only.md) | Evaluation Uses BLEU and Glossary Preservation Only | Accepted | 2026-05-24 | Core metrics are BLEU + glossary preservation; chrF/COMET are optional extensions. |
| [ADR-0013](ADR-0013-segment-cleanup-is-review-first.md) | Segment Cleanup Is Review-First | Accepted | 2026-05-24 | `--apply` is explicit; default is dry-run review output. |
| [ADR-0014](ADR-0014-engineering-smoke-tests-use-staged-model-loading.md) | Engineering Smoke Tests Use Staged Model Loading | Accepted | 2026-05-25 | Stage 1: tiny random model; Stage 2: real weights, one step each. |
| [ADR-0015](ADR-0015-pilot-training-may-save-ignored-local-checkpoints.md) | Pilot Training May Save Ignored Local Checkpoints | Accepted | 2026-05-25 | Pilot checkpoints are local engineering artifacts, not deliverables. |
| [ADR-0016](ADR-0016-inference-output-stays-rf007-compatible.md) | Inference Output Stays RF-007-Compatible | Accepted | 2026-05-25 | Output schema: `segment_id,source,references,candidates`. |
| [ADR-0017](ADR-0017-generation-evaluation-reports-are-local-artifacts.md) | Generation Evaluation Reports Are Local Engineering Artifacts | Accepted | 2026-05-25 | Reports live under ignored `data/review/evaluation/`; not committed. |
| [ADR-0018](ADR-0018-cross-cleaning-deletes-conflicts-not-translations.md) | Cross Cleaning Deletes Strong Conflicts, Not Translations | Accepted | 2026-05-25 | Cross-cleaning deletes but never auto-rewrites Korean. |
| [ADR-0019](ADR-0019-full-training-requires-strict-glossary-consistency-check.md) | Full Training Requires Strict Glossary Consistency Check | Accepted | 2026-05-25 | `--strict-check` must pass (`strict_current_mismatch_rows=0`) before training. |
| [ADR-0020](ADR-0020-formal-training-runs-require-split-artifacts-and-manifests.md) | Formal Training Runs Require Split Artifacts And Manifests | Accepted | 2026-05-25 | `--train` writes fixed splits + `run_manifest.json`; resume guards enforced. |
| [ADR-0021](ADR-0021-validation-generation-uses-fixed-training-splits.md) | Validation Generation Uses Fixed Training Splits | Accepted | 2026-05-25 | Reads `splits/validation.csv` from run manifest, not ad-hoc row slice. |
| [ADR-0022](ADR-0022-full-training-uses-explicit-profiles.md) | Full Training Uses Explicit Profiles | Accepted | 2026-05-25 | Named JSON profiles; old profiles preserved as historical baselines. |
| [ADR-0023](ADR-0023-formal-experiments-use-held-out-test-splits.md) | Formal Experiments Use Held-Out Test Splits (8:1:1, seed=42) | Accepted | 2026-05-25 | 8:1:1 / seed=42 locked; test used once per model. |
| [ADR-0024](ADR-0024-evaluation-reports-empty-model-outputs-instead-of-failing.md) | Evaluation Reports Empty Model Outputs Instead Of Failing | Accepted | 2026-05-25 | Empty candidates count as quality failures, not schema errors. |
| [ADR-0025](ADR-0025-cloud-llm-glossary-cleanup-is-delete-only.md) | Cloud LLM Glossary Cleanup Is Delete-Only | Accepted | 2026-05-26 | LLM may only delete glossary rows; no rewrites, adds, or merges. |
| [ADR-0026](ADR-0026-cloud-llm-segment-cleanup-may-rewrite-korean-with-local-guards.md) | Cloud LLM Segment Cleanup May Rewrite Korean With Local Guards | Accepted | 2026-05-26 | Korean rewrite allowed only after all local validation guards pass. |
| [ADR-0027](ADR-0027-segment-fragments-and-target-contamination-are-training-noise.md) | Segment Fragments And Target Contamination Are Training Noise | Accepted | 2026-05-26 | One-char CJK fragments and contaminated targets removed permanently. |
| [ADR-0028](ADR-0028-inference-uses-source-terminology-markers.md) | Inference Uses Source Terminology Markers | Accepted | 2026-05-26 | Inference applies `<start>...<end>` to source before tokenization. |
| [ADR-0029](ADR-0029-glossary-preservation-reports-exact-and-nospace-metrics.md) | Glossary Preservation Reports Exact And No-Space Metrics | Accepted | 2026-05-26 | Both exact and no-space preservation reported side by side. |
| [ADR-0030](ADR-0030-llm-cleanup-defaults-to-batch-api-with-strict-json-schema.md) | LLM Cleanup Defaults To Batch API With Strict JSON Schema | Accepted | 2026-05-27 | Default `--batch-mode batch`; strict `json_schema` in all completions. |
| [ADR-0031](ADR-0031-formal-training-uses-early-stopping-on-composite-metric.md) | Formal Training Uses Early Stopping On Composite Metric | Accepted | 2026-05-27 | `Seq2SeqTrainer` + `EarlyStoppingCallback`; composite = 0.5·BLEU + 0.5·preservation_nospace. |
