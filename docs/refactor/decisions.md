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
