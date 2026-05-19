# Refactor Backlog

This file is the single source of truth for systematic refactor work. README files should link here instead of carrying long-term TODO lists.

## RF-001: Git Hygiene

- **Status:** DONE
- **Scope:** `.gitignore`, Git index, local-only directories
- **Background / Why:** The repository currently tracks JetBrains `.idea/` files and has local environment directories such as `venv/` that should not be committed.
- **Concrete Scope:** Remove `.idea/` from the Git index without deleting local files, add ignores for IDE files, virtual environments, caches, checkpoints, generated outputs, and model artifacts.
- **Out of Scope:** Converting data files, moving notebooks, or restructuring source code.
- **Risks:** Accidentally removing user-local IDE files from disk, staging unrelated existing changes.
- **Acceptance Criteria:** `git ls-files` no longer lists `.idea/`; local `.idea/` remains on disk if present; `.gitignore` covers common generated/local artifacts.
- **Recommended Test Commands:** `git -c safe.directory=D:/longtu-translation-pipeline status --short`; `git -c safe.directory=D:/longtu-translation-pipeline ls-files | rg "^\\.idea/|venv/|__pycache__|\\.ipynb_checkpoints"`
- **Notes:** Completed on 2026-05-17. `.idea/` was removed from the Git index with `git rm --cached -r .idea` while local files remain ignored on disk. Validation: `git ls-files | rg "^\\.idea/"` returned no matches; `git check-ignore -v .idea/misc.xml venv/ .venv/ __pycache__/ .pytest_cache/ .ipynb_checkpoints/` matched `.gitignore`; `git diff --check` passed with a line-ending warning only; `git ls-files "*.xlsx"` still listed the 22 tracked Excel files, intentionally deferred to RF-002.

## RF-002: Data Governance

- **Status:** DONE
- **Scope:** `data/`, tracked `.xlsx`, generated CSV snapshots, notebook I/O references, historical `data/data-cleaning-and-merging.py`
- **Background / Why:** Raw Excel files are binary, large, and not review-friendly. The chosen policy is CSV in Git, raw xlsx outside normal Git tracking.
- **Concrete Scope:** Convert tracked Excel inputs and `glossary_all.xlsx` to stable CSV outputs, preserve workbook and sheet identity, remove xlsx files from Git index, document where raw xlsx should live, and mechanically move notebook/script I/O from Excel outputs to CSV outputs.
- **Out of Scope:** Rewriting model training, changing terminology logic, recalculating Excel formulas, or rewriting old Git history.
- **Risks:** Formula cells export the workbook's saved cached values; multi-sheet workbooks can lose sheet identity if flattened too aggressively; notebook behavior was changed mechanically and not re-trained.
- **Acceptance Criteria:** CSV files represent the current workbook/sheet data; `git ls-files` no longer lists `.xlsx`; notebooks no longer use Excel I/O in source cells; final repository state keeps only the final training corpus and explicitly retained supporting CSVs.
- **Recommended Test Commands:** `git -c safe.directory=D:/longtu-translation-pipeline -c core.quotePath=false ls-files "*.xlsx"`; `git -c safe.directory=D:/longtu-translation-pipeline check-ignore -v glossary_all.xlsx`; notebook source scan for `read_excel`, `to_excel`, `.xlsx`, and `Excel`; final corpus checks under RF-010.
- **Notes:** Completed on 2026-05-17. `scripts/export_xlsx_to_csv.py` originally exported 72 sheet CSV snapshots from 22 local workbooks and wrote `data/csv_manifest.csv` with workbook, sheet, CSV path, rows, columns, `has_formula`, and `formula_cells`. Five sheets contained 119,924 formula cells and were exported from saved workbook cached values. `.xlsx` files were removed from the Git index with `git rm --cached -- "*.xlsx"` while remaining ignored locally. Notebook I/O was mechanically migrated from Excel to CSV. On 2026-05-19, the temporary conversion script, CSV manifest, intermediate input snapshots, and old data cleaning script were intentionally removed as part of the final-training-corpus-only policy.

## RF-003: Data Pipeline Modularization

- **Status:** TODO
- **Scope:** `data/data-cleaning-and-merging.py`, future `src/longtu_l10n_mt/data/`, CLI entry points
- **Background / Why:** Data cleaning currently lives in one script with hard-coded paths, header rows, and column mappings.
- **Concrete Scope:** Move reusable cleaning, merging, and language-pair generation logic into importable modules; keep a thin CLI wrapper; move mappings to config.
- **Out of Scope:** Training, inference, and evaluation rewrites.
- **Risks:** Changing output CSV shape or language column names unintentionally.
- **Acceptance Criteria:** Existing basic workflow still works; data transforms are covered by small fixture tests; config controls input/output paths and language mappings.
- **Recommended Test Commands:** `python -m pytest tests`; CLI dry run against a tiny fixture workbook or CSV fixture.
- **Notes:** Preserve current language normalization behavior unless a later task explicitly changes it. After the 2026-05-19 final-corpus cleanup, the old `data/data-cleaning-and-merging.py` script is no longer retained; re-triage this task if a reproducible source-to-final pipeline is needed again.

## RF-004: Notebook Governance

- **Status:** TODO
- **Scope:** Root `.ipynb` files, `tests/BLEU-score-calculating.ipynb`, future `notebooks/experiments/`
- **Background / Why:** Experiment notebooks are mixed into the repository root, making the project hard to scan.
- **Concrete Scope:** Move notebooks into `notebooks/experiments/`, clear heavy outputs where appropriate, and keep README links current.
- **Out of Scope:** Extracting all notebook logic into modules; that belongs to RF-003, RF-005, RF-006, and RF-007.
- **Risks:** Breaking relative paths inside notebooks.
- **Acceptance Criteria:** Root directory is easier to scan; notebooks remain findable and documented; moved notebooks either retain working path notes or include migration notes.
- **Recommended Test Commands:** `git -c safe.directory=D:/longtu-translation-pipeline status --short`; open or inspect at least one moved notebook for path references.
- **Notes:** Do mechanical moves separately from logic changes.

## RF-005: Terminology/Tag/Code Protection

- **Status:** TODO
- **Scope:** Terminology special tokens, game UI tag protection, `<code_id=*>` handling
- **Background / Why:** Critical text-protection logic is duplicated across notebooks and cannot be unit-tested directly.
- **Concrete Scope:** Extract pure functions for glossary tagging, tag/code placeholder replacement, and restoration; add fixture-based tests.
- **Out of Scope:** Model training parameter changes and full translation quality tuning.
- **Risks:** Incorrect placeholder ordering can corrupt game markup or terminology alignment.
- **Acceptance Criteria:** Glossary terms, bracket tags, angle tags, color tags, and code placeholders round-trip on representative samples.
- **Recommended Test Commands:** `python -m pytest tests/test_text_protection.py`
- **Notes:** Keep token names compatible with existing notebooks unless a selected task explicitly changes them.

## RF-006: Training/Inference Config

- **Status:** TODO
- **Scope:** Training notebooks, inference notebooks, future `configs/`
- **Background / Why:** Model paths, language pairs, batch sizes, and output paths are hard-coded in notebook cells.
- **Concrete Scope:** Introduce config files for model name, tokenizer, language pair, output directories, and training/inference parameters.
- **Out of Scope:** Downloading large models or running full GPU training as part of refactor verification.
- **Risks:** Config drift can make old experiment results hard to reproduce.
- **Acceptance Criteria:** Training/inference code reads paths and parameters from config; a small import/config validation test passes without downloading a model.
- **Recommended Test Commands:** Config parse check; targeted import test for training/inference modules.
- **Notes:** Prefer explicit config defaults over hidden local paths such as `autodl-tmp/...`.

## RF-007: Evaluation Automation

- **Status:** TODO
- **Scope:** BLEU, terminology preservation, code preservation evaluation
- **Background / Why:** Evaluation currently lives in notebooks and writes results manually.
- **Concrete Scope:** Provide importable evaluation functions and a CLI for BLEU, glossary preservation, and code preservation metrics.
- **Out of Scope:** Defining new model quality targets or changing metric formulas without a separate decision.
- **Risks:** Metric implementations may diverge from notebook behavior.
- **Acceptance Criteria:** Small fixture tests reproduce expected BLEU/preservation metrics; evaluation can run without notebook state.
- **Recommended Test Commands:** `python -m pytest tests/test_evaluation.py`
- **Notes:** Keep notebook-derived formulas documented if ported.

## RF-008: Dependency Split

- **Status:** TODO
- **Scope:** `requirements.txt`, future optional requirements files or project metadata
- **Background / Why:** The current requirements file pins a full experiment environment, including notebook and CUDA training dependencies.
- **Concrete Scope:** Split base data-processing dependencies from training/GPU and notebook dependencies.
- **Out of Scope:** Upgrading every package version or changing the runtime platform.
- **Risks:** Users may lose a one-command install path if docs are not updated.
- **Acceptance Criteria:** Dependency files clearly describe base, training, and notebook installs; README setup commands are accurate.
- **Recommended Test Commands:** Fresh environment install dry run where practical; `python -m pip check` if dependencies are installed.
- **Notes:** CUDA PyTorch wheels may require a separate PyTorch index URL.

## RF-009: Documentation Governance

- **Status:** DONE
- **Scope:** `README.md`, `README.en.md`, `README.zh-CN.md`, `AGENTS.md`, `docs/refactor/backlog.md`, `docs/refactor/decisions.md`
- **Background / Why:** README files contained long-term refactor direction and limitations, while there was no dedicated backlog or decision log.
- **Concrete Scope:** Move refactor TODOs into this backlog, create a decision log, create AI/Codex working rules, and leave README files with concise links.
- **Out of Scope:** Removing `.idea/`, converting xlsx to CSV, moving notebooks, or changing Python code.
- **Risks:** Losing useful README context if migration is too aggressive.
- **Acceptance Criteria:** README files contain no large refactor TODO section; AGENTS contains working rules only; this backlog and the decisions log contain the migrated governance content.
- **Recommended Test Commands:** `git -c safe.directory=D:/longtu-translation-pipeline status --short`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`; `rg -n -i "重构方向|Refactor Direction|리팩터링 방향|当前限制|Current Limitations" --glob "README*.md" .`; `rg -n -i "TODO|FIXME|NEEDS_TRIAGE|backlog|decisions" AGENTS.md docs/refactor`
- **Notes:** Completed on 2026-05-17. Validation: `git status --short` showed only the pre-existing `.idea/LongtuKoreaTranslationModel.iml` change plus this documentation work; `git diff --check` passed with Git line-ending warnings only; README refactor-heading scan returned no matches; AGENTS/backlog/decisions scan returned expected governance references.

## RF-010: CSV Normalization and Quarantine

- **Status:** DONE
- **Scope:** historical CSV schema registry and quarantine run, final `data/segments.csv` and `data/glossary.csv`
- **Background / Why:** Exported CSV snapshots contain blank rows, non-translation sheets, unstable layouts, and a few conflicting text-config sources. Cleaning after a global merge makes these issues hard to trace.
- **Concrete Scope:** Normalize each source CSV independently into a wide master CSV with language-code columns, quarantine invalid or unsupported rows during the working run, compare `文本配置表/Sheet1.csv` against single-language text config files, reduce accepted rows to final data files, and conservatively split high-confidence term duplicates from segment data.
- **Out of Scope:** Automatically classifying short text candidates as terms, changing translation text content beyond outer whitespace normalization, parsing unsupported row-oriented layouts such as `excelWord/Sheet3.csv`, or retaining a reusable source-to-final pipeline in this repository.
- **Risks:** The final repository no longer retains source CSV snapshots, quarantine reports, or RF-010 scripts/tests; regenerating the corpus from raw files will require a future explicit pipeline task. Conflicting `zh-CN + en` term groups are intentionally left in `segments.csv` for future triage.
- **Acceptance Criteria:** `data/segments.csv` contains segment rows with `segment_id` and language columns; `data/glossary.csv` contains term rows with `term_id` and language columns; intermediate `data/normalized/`, `data/input/`, process scripts, tests, manifest, old data docs, and superseded single-corpus/glossary-all files are absent.
- **Recommended Test Commands:** `Get-Content data/glossary.csv -TotalCount 1`; `Get-Content data/segments.csv -TotalCount 1`; `(Import-Csv data/glossary.csv).Count`; `(Import-Csv data/segments.csv).Count`; scan for superseded file names; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-19. The normalization dry run produced 170,097 accepted master rows from 71 scanned CSV files, 61 primary sources, 5,450 quarantined rows, and 605 text-config mismatch rows. Final cleanup intentionally removed intermediate cleaning artifacts. A later conservative split generated `data/glossary.csv` and `data/segments.csv`: 52,756 high-confidence duplicate rows were moved out of segment data, 4,613 candidate rows were kept because their `zh-CN + en` groups had language conflicts, `glossary.csv` contains 44,863 normalized term rows, and `segments.csv` contains 117,341 segment rows. Short-text candidates that do not already match glossary terms were not auto-classified.
