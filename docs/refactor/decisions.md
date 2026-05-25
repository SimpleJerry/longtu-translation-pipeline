# Refactor Decisions

This file records confirmed architecture decisions and refactor principles. Do not repeatedly overturn these decisions without new context.

## 2026-05-17: README and AGENTS Do Not Carry Long-Term Task Pools

- **Decision:** README files stay focused on project introduction, setup, basic usage, and navigation. `AGENTS.md` stays focused on AI/Codex working rules.
- **Background:** Long-term refactor TODOs were starting to live in README-style documentation, which makes user-facing docs noisy and hard to maintain.
- **Impact Scope:** `README.md`, `README.en.md`, `README.zh-CN.md`, `AGENTS.md`.
- **Follow-up Notes:** Add only short links from README and AGENTS to the refactor backlog.

## 2026-05-17: Refactor Backlog Lives in `docs/refactor/backlog.md`

- **Decision:** Systematic refactor TODOs belong in `docs/refactor/backlog.md`.
- **Background:** The project needs a single place to record cross-module and long-running refactor tasks.
- **Impact Scope:** Future refactor planning, AI/Codex task selection, documentation updates.
- **Follow-up Notes:** New refactor items should include ID, status, scope, background, concrete scope, out-of-scope notes, risks, acceptance criteria, test commands, and notes.

## 2026-05-17: Architecture Decisions Live in `docs/refactor/decisions.md`

- **Decision:** Confirmed architecture decisions and refactor principles belong in this decision log.
- **Background:** Data governance and incremental refactor choices should be easy to find and should not be re-decided in each task.
- **Impact Scope:** Refactor planning, review, and future implementation work.
- **Follow-up Notes:** Add new decisions when a task establishes a durable project rule or tradeoff.

## 2026-05-17: CSV In Git, Raw XLSX Outside Normal Git Tracking

- **Decision:** Store normalized CSV snapshots in Git and move raw xlsx files out of normal Git tracking.
- **Background:** Raw Excel files are binary and difficult to review. The user confirmed the preferred data policy as "CSV 入库".
- **Impact Scope:** `data/`, `glossary_all.xlsx`, tracked `.xlsx` files, future data regeneration docs.
- **Follow-up Notes:** Multi-sheet workbooks must preserve workbook and sheet identity when converted. Formula cells should be treated carefully because CSV exports store values, not formulas.

## 2026-05-17: Use Gradual Engineering Refactor

- **Decision:** Refactor incrementally instead of rewriting the whole project at once.
- **Background:** The user confirmed "渐进工程化" as the preferred depth. The repository is currently an experiment workspace with notebooks and one data script.
- **Impact Scope:** Task sequencing, commit size, notebook migration, module extraction.
- **Follow-up Notes:** Keep notebooks as experiment records while extracting repeatable logic into modules and CLIs over time.

## 2026-05-17: Preserve Public Compatibility by Default

- **Decision:** Preserve documented commands, public APIs, file formats, token names, and notebook usability unless a selected task explicitly requires a breaking change.
- **Background:** The project contains research workflows that may still be used manually.
- **Impact Scope:** CLI design, module extraction, data conversion, notebook migration.
- **Follow-up Notes:** Breaking changes require explicit backlog scope, README updates, and migration notes.

## 2026-05-22: Segment Evidence Is Not a Sufficient Glossary Keep Signal

- **Decision:** `data/segments.csv` provides current product-corpus relevance evidence for glossary cleanup, but matching segment text is not by itself enough to keep a glossary term.
- **Background:** Common words can appear frequently in product text while still being unsuitable for a company game terminology table.
- **Impact Scope:** `scripts/glossary_semantic_pipeline.py`, `data/glossary.csv`, glossary review CSVs, README data workflow notes.
- **Follow-up Notes:** Segment evidence can remove terms that are absent from the current corpus and can be recorded for audit, but hard noise filters, termhood, game-domain signals, POS shape, and semantic checks still decide whether a matched term should remain.

## 2026-05-24: Glossary Pipeline Uses Final Glossary As Baseline

- **Decision:** The glossary semantic pipeline reads the current `data/glossary.csv` as its authoritative baseline and writes audit CSVs only as local ignored artifacts.
- **Background:** Historical audit baselines and raw source files are not committed because they are intermediate or sensitive data. The committed final glossary must be the reproducible starting point for later cleanup passes.
- **Impact Scope:** `scripts/glossary_semantic_pipeline.py`, `configs/glossary/`, `.gitignore`, README data workflow notes.
- **Follow-up Notes:** Long business rule lists and thresholds should live in `configs/glossary/`; `segments.csv` hashes may be recorded or optionally checked, but must not be hard-coded as a required source-code gate.

## 2026-05-24: Segment Cleanup Is Review-First

- **Decision:** The segment cleanup pipeline defaults to dry-run review outputs and rewrites `data/segments.csv` only when explicitly run with `--apply`.
- **Background:** Seq2seq segment cleaning has higher false-positive risk than glossary cleaning, especially for short UI labels and structured strings that may contain useful sentence fields.
- **Impact Scope:** `scripts/segments_cleaning_pipeline.py`, `configs/segments/`, `data/segments.csv`, local `data/review/segments/` outputs.
- **Follow-up Notes:** Term/entity-like deletion is based on local semantic signals rather than fixed text length thresholds. Presentation tags such as `<c=...>` are stripped while preserving wrapped text, symmetric outer wrappers are unwrapped, and valid machine placeholders are audited rather than deleted. Structured tuple-like strings should be split when safely aligned and removed only when parsing/alignment fails.

## 2026-05-24: Notebook Deletion Requires Inventory First

- **Decision:** Historical notebooks are classified and archived before any deletion. Main workflow notebooks live under `notebooks/main/`, auxiliary analysis notebooks under `notebooks/analysis/`, and old experiments under `notebooks/archive/2023-legacy/`.
- **Background:** The 2023 notebook sequence contains useful experiment history, but the original order and purpose are no longer obvious from filenames alone.
- **Impact Scope:** Notebook file layout, README navigation, RF-004, future RF-005/RF-006/RF-007 extraction work.
- **Follow-up Notes:** Do not delete archived notebooks until `docs/notebooks/inventory.md` has been reviewed and the replacement module, config, or evaluation path is clear.

## 2026-05-24: Text Protection Uses Single-Segment Term Markers

- **Decision:** Current terminology protection uses only `<start>...<end>` on both source and target sides. The historical `<start>source<middle>target<end>` T&N+R format and `<code_id=N>` code/tag protection are deprecated from the current engineering mainline.
- **Background:** The user decided to abandon the T&N+R method and simplify all terminology markers to a single-segment form.
- **Impact Scope:** `src/longtu_translation_pipeline/text_protection.py`, RF-005 tests, README workflow notes, notebook inventory, future RF-006/RF-007 migration.
- **Follow-up Notes:** Historical notebooks may still contain `<middle>` and `<code_id=N>` outputs as experiment records, but new reusable code should not generate them unless a future task explicitly reintroduces that behavior.

## 2026-05-24: Training and Inference Configs Use JSON Dry-Run Entrypoints

- **Decision:** Training and inference settings live in JSON config files, and RF-006 phase 1 entrypoints must not load models during import or dry-run execution.
- **Background:** Notebook cells previously mixed hard-coded paths such as `autodl-tmp/...`, NLLB language codes, split settings, batch sizes, and output directories. The project needs a reviewable configuration skeleton before adding heavyweight training dependencies.
- **Impact Scope:** `configs/training/default.json`, `configs/inference/default.json`, `src/longtu_translation_pipeline/config.py`, `src/longtu_translation_pipeline/training.py`, `src/longtu_translation_pipeline/inference.py`, `scripts/train_model.py`, `scripts/run_inference.py`, README workflow notes.
- **Follow-up Notes:** Actual model loading, `transformers` Trainer wiring, dataset tokenization, GPU training, and generation output writing should be added in later phases. Importable modules and dry-run commands should remain safe to execute without downloading NLLB models.

## 2026-05-25: Trainer Smoke Uses Real Tokenizer, Not Real NLLB Weights

- **Decision:** RF-006 trainer smoke tests use the real NLLB tokenizer but a tiny randomly initialized seq2seq model, not the real `facebook/nllb-200-distilled-600M` weights.
- **Background:** The project needs to validate language-code handling, marker tokens, tensor shapes, and Trainer wiring before paying the cost of large model downloads or long GPU runs.
- **Impact Scope:** `scripts/train_model.py`, `src/longtu_translation_pipeline/training.py`, `requirements-training.txt`, README workflow notes.
- **Follow-up Notes:** Treat `--nllb-smoke-test` as an engineering-chain check only. Full model loading, checkpoint policy, and quality evaluation require a later RF-006 training phase.

## 2026-05-25: Real Model Smoke Downloads Weights But Is Not Training

- **Decision:** RF-006 real model smoke may download and load `facebook/nllb-200-distilled-600M` weights, resize token embeddings for `<start>/<end>`, and run one Trainer step, but it is still an engineering smoke test rather than a training run.
- **Background:** After tokenizer and tiny-model smoke tests passed, the remaining infrastructure risk was real model weight loading, CUDA execution, and special-token resize compatibility.
- **Impact Scope:** `scripts/train_model.py`, `src/longtu_translation_pipeline/training.py`, local Hugging Face cache, README workflow notes.
- **Follow-up Notes:** Do not retain checkpoints from smoke tests. Keep outputs under ignored `data/review/`. Quality evaluation, checkpoint naming, and actual training duration belong to a later RF-006 phase.

## 2026-05-25: Pilot Training May Save Ignored Local Checkpoints

- **Decision:** RF-006 pilot training may save checkpoints under ignored `fine-tuned-models/.../pilot/run-*` and resume from them to validate the real training lifecycle.
- **Background:** One-step smoke tests did not verify checkpoint persistence, Trainer resume behavior, loss logging across runs, or final output directory shape.
- **Impact Scope:** `scripts/train_model.py`, `src/longtu_translation_pipeline/training.py`, ignored model output directories, README workflow notes.
- **Follow-up Notes:** Pilot checkpoints are local engineering artifacts, not final deliverables. Full training duration, final checkpoint selection, generation, and RF-007 quality evaluation still require a later training phase.

## 2026-05-25: Inference Output Stays RF-007-Compatible

- **Decision:** Checkpoint inference writes CSVs with `segment_id,source,references,candidates`; RF-007 continues to evaluate the `source`, `references`, and `candidates` columns while `segment_id` provides row traceability.
- **Background:** The project needs generation output that can flow directly into the existing BLEU and glossary-preservation evaluator without losing the link back to `data/segments.csv`.
- **Impact Scope:** `configs/inference/default.json`, `src/longtu_translation_pipeline/inference.py`, `scripts/run_inference.py`, local inference review artifacts, README workflow notes.
- **Follow-up Notes:** Generated inference CSVs are local artifacts under ignored `data/review/inference/`. Full validation generation and fixed split selection belong to later RF-006/RF-007 phases.

## 2026-05-25: Generation Evaluation Reports Are Local Engineering Artifacts

- **Decision:** Generation evaluation reports live under ignored `data/review/evaluation/` and record checkpoint/generation metadata, BLEU, glossary preservation, and sample review rows without implying model quality.
- **Background:** The project needs a fixed report shape for RF-006 generation outputs before running long training or full validation.
- **Impact Scope:** `configs/evaluation/generation_report.json`, `src/longtu_translation_pipeline/evaluation.py`, `scripts/evaluate_translation.py`, README workflow notes.
- **Follow-up Notes:** Use this report format for pilot and future validation outputs. Full-run quality conclusions require a real training run, fixed validation split, and a selected checkpoint.

## 2026-05-25: Formal Training Runs Require Split Artifacts And Manifests

- **Decision:** Formal training must run through `scripts/train_model.py --train`, write fixed train/validation split CSVs, and record `run_manifest.json` inside an ignored `fine-tuned-models/.../runs/run-*` directory.
- **Background:** Pilot training verified checkpoints and resume, but it did not provide enough metadata or split stability for a future full run to be reproducible.
- **Impact Scope:** `scripts/train_model.py`, `src/longtu_translation_pipeline/training.py`, local fine-tuned model directories, README workflow notes, future RF-006-P8 validation generation.
- **Follow-up Notes:** Resume commands inherit the existing manifest row limit, explicit resume row limits must match the manifest, and checkpoint steps must be smaller than the requested `max_steps`. Validation generation should consume the fixed run split in a later RF-006 phase.

## 2026-05-24: Evaluation Uses BLEU and Glossary Preservation Only

- **Decision:** RF-007 evaluation automates corpus BLEU and glossary preservation for the simplified `<start>...<end>` marker policy. Code-token preservation is not part of the current evaluation mainline.
- **Background:** The old evaluation notebooks used historical `<middle>` and `<code_id>` assumptions that no longer match RF-005. The project still needs model-output checks before RF-006 moves into real training or generation.
- **Impact Scope:** `configs/evaluation/default.json`, `src/longtu_translation_pipeline/evaluation.py`, `scripts/evaluate_translation.py`, README workflow notes, RF-007 tests.
- **Follow-up Notes:** BLEU defaults to Korean whitespace tokenization, with character tokenization available as a config option. Glossary preservation checks Korean term presence after stripping glossary markers from candidate translations.
