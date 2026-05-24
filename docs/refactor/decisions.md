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

## 2026-05-24: Evaluation Uses BLEU and Glossary Preservation Only

- **Decision:** RF-007 evaluation automates corpus BLEU and glossary preservation for the simplified `<start>...<end>` marker policy. Code-token preservation is not part of the current evaluation mainline.
- **Background:** The old evaluation notebooks used historical `<middle>` and `<code_id>` assumptions that no longer match RF-005. The project still needs model-output checks before RF-006 moves into real training or generation.
- **Impact Scope:** `configs/evaluation/default.json`, `src/longtu_translation_pipeline/evaluation.py`, `scripts/evaluate_translation.py`, README workflow notes, RF-007 tests.
- **Follow-up Notes:** BLEU defaults to Korean whitespace tokenization, with character tokenization available as a config option. Glossary preservation checks Korean term presence after stripping glossary markers from candidate translations.
