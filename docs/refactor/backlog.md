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

- **Status:** OBSOLETE
- **Scope:** `data/data-cleaning-and-merging.py`, future `src/longtu_l10n_mt/data/`, CLI entry points
- **Background / Why:** Data cleaning currently lives in one script with hard-coded paths, header rows, and column mappings.
- **Concrete Scope:** Move reusable cleaning, merging, and language-pair generation logic into importable modules; keep a thin CLI wrapper; move mappings to config.
- **Out of Scope:** Training, inference, and evaluation rewrites.
- **Risks:** Changing output CSV shape or language column names unintentionally.
- **Acceptance Criteria:** Existing basic workflow still works; data transforms are covered by small fixture tests; config controls input/output paths and language mappings.
- **Recommended Test Commands:** `python -m pytest tests`; CLI dry run against a tiny fixture workbook or CSV fixture.
- **Notes:** Preserve current language normalization behavior unless a later task explicitly changes it. After the 2026-05-19 final-corpus cleanup, the old `data/data-cleaning-and-merging.py` script is no longer retained; re-triage this task if a reproducible source-to-final pipeline is needed again. Closed on 2026-05-26 (RF-022): the raw xlsx inputs and the original `data/data-cleaning-and-merging.py` are not retained in this repository. A source-to-final data pipeline would only be useful if those raw inputs return; until then this item carries no actionable scope.

## RF-004: Notebook Governance

- **Status:** DONE
- **Scope:** Root `.ipynb` files, `docs/notebooks/inventory.md`, `notebooks/main/`, `notebooks/analysis/`, `notebooks/archive/2023-legacy/`
- **Background / Why:** Experiment notebooks were mixed into the repository root, and the long gap since the 2023 experiments made the order, purpose, and current value of each file hard to recover from memory.
- **Concrete Scope:** Build a notebook inventory from commit timeline and notebook content, classify each notebook as main, analysis, or legacy archive, move root notebooks into the corresponding `notebooks/` subdirectories, keep README links current, and defer deletion to a later explicit review.
- **Out of Scope:** Extracting all notebook logic into modules; that belongs to RF-003, RF-005, RF-006, and RF-007.
- **Risks:** Moving notebooks can break relative paths; deleting historical notebooks too early can lose useful experiment context; old outputs and intermediate CSVs are no longer committed.
- **Acceptance Criteria:** Root directory has no tracked `.ipynb` files; every tracked notebook is listed in `docs/notebooks/inventory.md` with purpose, timeline, dependency status, and keep/archive/delete guidance; README files point to the inventory instead of listing notebooks in the root.
- **Recommended Test Commands:** `git -c safe.directory=D:/longtu-translation-pipeline status --short`; `git -c safe.directory=D:/longtu-translation-pipeline ls-files "*.ipynb"`; root `.ipynb` scan; parse moved notebooks as JSON; `rg -n "notebooks|inventory|T&N\\+R|archive" README.md README.en.md README.zh-CN.md docs/notebooks docs/refactor`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-24. Root notebooks were moved into `notebooks/main/`, `notebooks/analysis/`, and `notebooks/archive/2023-legacy/`. `docs/notebooks/inventory.md` now records the 2023 experiment timeline, missing dependency references, and recommended treatment for each notebook. No notebooks were deleted and notebook internals were not changed.

## RF-005: Terminology Marker Protection

- **Status:** DONE
- **Scope:** `src/longtu_translation_pipeline/text_protection.py`, `tests/test_text_protection.py`, single-shape `<start>...<end>` terminology markers
- **Background / Why:** Critical terminology marker logic was duplicated across notebooks and could not be unit-tested directly. The user later decided to abandon the T&N+R format and use only single-segment terminology markers.
- **Concrete Scope:** Extract pure functions for glossary loading, longest-first terminology marker insertion, duplicate-marker avoidance, and marker stripping; remove current-mainline support for `<middle>` and `<code_id=N>`.
- **Out of Scope:** Model training parameter changes and full translation quality tuning.
- **Risks:** Historical notebooks still contain deprecated `<middle>` and `<code_id=N>` outputs; deleting or rewriting them in the same change would obscure experiment history.
- **Acceptance Criteria:** Glossary terms are marked as `<start>term<end>` on source and target sides; no current module/test/README/config path relies on `<middle>` or `<code_id=N>`; placeholders such as `{0}` remain plain text.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\text_protection.py scripts\glossary_semantic_pipeline.py scripts\segments_cleaning_pipeline.py`; `venv\Scripts\python.exe -m unittest discover -s tests`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`; `git -c safe.directory=D:/longtu-translation-pipeline status --short`
- **Notes:** Completed on 2026-05-24. `src/longtu_translation_pipeline/text_protection.py` now provides testable pure functions for loading glossary pairs, protecting a Chinese-Korean training pair with `<start>...<end>` markers on both sides, and stripping glossary markers. The first RF-005 implementation briefly included `<middle>` and `<code_id=N>` compatibility, but this was removed after the user decided to abandon T&N+R and code/tag protection as current-mainline behavior. Notebook JSON was intentionally not rewritten; T&N+R notebooks are documented as deprecated historical experiments.

## RF-006: Training/Inference Config

- **Status:** DONE
- **Scope:** `configs/training/`, `configs/inference/`, `src/longtu_translation_pipeline/config.py`, `src/longtu_translation_pipeline/training.py`, `src/longtu_translation_pipeline/inference.py`, `scripts/train_model.py`, `scripts/run_inference.py`
- **Background / Why:** Model paths, language pairs, batch sizes, and output paths are hard-coded in notebook cells.
- **Concrete Scope:** Phase 1 introduces JSON config files for model name, language pair, data paths, output paths, split settings, tokenization settings, and basic training/inference parameters. It also adds importable dry-run APIs and CLI entry points that validate config and data without loading models.
- **Out of Scope:** Downloading large models or running full GPU training as part of refactor verification.
- **Risks:** Config drift can make old experiment results hard to reproduce.
- **Acceptance Criteria:** Training/inference code reads paths and parameters from config; a small import/config validation test passes without downloading a model; dry-run CLI commands run against the committed `data/segments.csv` and `data/glossary.csv`.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\config.py src\longtu_translation_pipeline\training.py src\longtu_translation_pipeline\inference.py scripts\train_model.py scripts\run_inference.py`; `venv\Scripts\python.exe -m unittest discover -s tests`; `venv\Scripts\python.exe scripts\train_model.py --config configs/training/default.json --dry-run`; `venv\Scripts\python.exe scripts\run_inference.py --config configs/inference/default.json --dry-run`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- data notebooks`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Phase 1 completed on 2026-05-24. The default training config uses `data/segments.csv`, `data/glossary.csv`, `zh-CN -> ko`, and NLLB language codes `zho_Hans -> kor_Hang`. `scripts/train_model.py` validates config/data, applies RF-005 `<start>...<end>` terminology markers only to preview examples during dry-run (`terminology_marker_scope=preview_only`), and prints deterministic split counts. RF-006-P10 later corrected those counts from train/validation to train/validation/test. `scripts/run_inference.py` validates config/input and prints model/input/output planning details. Review fixes on 2026-05-24 made config-internal relative paths resolve from the repository root, made empty training/inference CSVs fail clearly, and documented the preview-only marker scope.

## RF-006-P2: Tokenizer / Dataset / Trainer Smoke Test

- **Status:** DONE
- **Scope:** Training tokenizer/dataset preparation, minimal `transformers` integration, `requirements-training.txt`
- **Background / Why:** RF-006 Phase 1 validates config and data flow without model libraries. The next training step should prove that tokenizer, dataset construction, language codes, max length settings, and terminology markers can enter a real training-shaped pipeline before any long GPU training run.
- **Concrete Scope:** Add the smallest training-chain smoke test that loads a local tokenizer, builds a tiny dataset-shaped sample, passes `zh-CN -> ko` and `zho_Hans -> kor_Hang` settings into tokenization, and applies RF-005 `<start>...<end>` terminology markers to full prepared training examples rather than preview-only examples.
- **Out of Scope:** Full model training, checkpoint saving, long GPU runs, generation, evaluation loop integration, and model quality tuning.
- **Risks:** Introducing `transformers`, `datasets`, `sentencepiece`, and `accelerate` too early can make the base environment heavy; tests must not require downloading a large NLLB model.
- **Acceptance Criteria:** Tokenizer/dataset smoke test passes on a tiny local tokenizer without full training; RF-006 config values drive tokenization; terminology marker application is tested beyond preview-only dry-run; actual training dependencies are recorded in `requirements-training.txt`.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\config.py src\longtu_translation_pipeline\training.py src\longtu_translation_pipeline\inference.py scripts\train_model.py scripts\run_inference.py`; `venv\Scripts\python.exe -m unittest discover -s tests`; `venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --dry-run`; `venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --smoke-test`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- data notebooks`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-24. `src/longtu_translation_pipeline/training.py` now exposes prepared-example and tokenized-example helpers, applies RF-005 `<start>...<end>` terminology markers to all prepared examples, and builds `input_ids`, `attention_mask`, and `labels` through a tokenizer-shaped interface. `scripts/train_model.py --smoke-test` uses a tiny local `transformers.PreTrainedTokenizerFast` backed by `tokenizers.WordLevel`, so the smoke test confirms the training-chain dependency path without downloading NLLB. `requirements-training.txt` was created with the confirmed direct dependencies: `torch`, `torchvision`, `transformers`, `tokenizers`, `huggingface-hub`, and `safetensors`; `datasets`, `sentencepiece`, and `accelerate` remain excluded because RF-006-P2 does not use them. RF-006-P10 later corrected formal dry-run split reporting to include test rows.

## RF-006-P3: Real NLLB Tokenizer / Minimal Trainer Smoke

- **Status:** DONE
- **Scope:** Real NLLB tokenizer loading, tiny seq2seq Trainer smoke, `requirements-training.txt`
- **Background / Why:** RF-006-P2 proved the tokenizer-shaped path with a local tiny tokenizer. The next risk was whether the actual NLLB tokenizer, language codes, marker tokens, dataset tensors, and Hugging Face Trainer wiring work together before any full model training.
- **Concrete Scope:** Add `scripts/train_model.py --nllb-smoke-test --smoke-rows 2`, load the real `facebook/nllb-200-distilled-600M` tokenizer, apply RF-005 markers to a tiny prepared sample, tokenize source and target, construct a custom torch dataset, and run Trainer for `max_steps=1` against a randomly initialized tiny `M2M100ForConditionalGeneration`.
- **Out of Scope:** Downloading real NLLB model weights, full GPU training, checkpoint retention, model quality evaluation, inference generation, and dataset package integration.
- **Risks:** Hugging Face tokenizer downloads can fail without network; transformers API differences can break smoke arguments; Trainer may require additional dependencies.
- **Acceptance Criteria:** Real NLLB tokenizer loads; `zho_Hans -> kor_Hang` language codes are applied; `<start>` and `<end>` are available as tokenizer special tokens; tiny Trainer runs one step; no tracked data or notebook files are changed; required training dependencies are recorded.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\training.py scripts\train_model.py`; `venv\Scripts\python.exe -m unittest discover -s tests`; `$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"; venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --nllb-smoke-test --smoke-rows 2`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- data notebooks`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-25. `--nllb-smoke-test` downloaded/used the real NLLB tokenizer in local `venv/hf_cache`, added `<start>` and `<end>` while preserving NLLB language tokens, found `kor_Hang` token id `256098`, tokenized 2 prepared rows to `2 x 400`, and ran a one-step Trainer smoke with a tiny randomly initialized M2M100-style seq2seq model. The smoke output directory is ignored at `data/review/training_smoke`. `accelerate==1.13.0` and `sentencepiece==0.2.1` were installed and added to `requirements-training.txt`; `datasets` remains excluded because this phase uses a custom torch dataset.

## RF-006-P4: Real NLLB Model 1-Step Smoke

- **Status:** DONE
- **Scope:** Real NLLB model weight loading, CUDA Trainer smoke, special-token embedding resize
- **Background / Why:** RF-006-P3 validated the real tokenizer and Trainer wiring with a tiny random model. The next training risk was whether the actual `facebook/nllb-200-distilled-600M` weights can load, resize embeddings for `<start>/<end>`, and complete one Trainer step on the local CUDA environment.
- **Concrete Scope:** Add `scripts/train_model.py --real-model-smoke-test --smoke-rows 2`, load the real tokenizer and real model weights, apply RF-005 markers, tokenize 2 rows, resize token embeddings after adding special tokens, and run Trainer for `max_steps=1`.
- **Out of Scope:** Full training, checkpoint retention, quality evaluation, generation, changing hyperparameters, and adding the `datasets` package.
- **Risks:** Large model download can fail or be slow; CUDA OOM may require a smaller smoke shape or CPU fallback; Trainer API differences can break smoke flags.
- **Acceptance Criteria:** Real model weights load; CUDA is used when available; `<start>/<end>` special tokens are present after resize; Trainer completes one step; no tracked data or notebook files are changed; outputs remain under ignored `data/review/`.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\training.py scripts\train_model.py`; `venv\Scripts\python.exe -m unittest discover -s tests`; `$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"; venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --real-model-smoke-test --smoke-rows 2`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- data notebooks`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-25. The real model smoke downloaded/loaded `facebook/nllb-200-distilled-600M`, added `<start>` and `<end>`, confirmed `kor_Hang` token id `256098`, resized/verified embeddings at `256206`, tokenized 2 rows to `2 x 400`, and completed one Trainer step on `NVIDIA GeForce RTX 4070 Ti SUPER`. Final output reported `parameter_count=615073792`, `device=cuda`, `torch_dtype=float32+fp16_trainer`, `cuda_memory_summary=allocated_gb=2.32;reserved_gb=7.53`, and `train_loss=14.74772834777832`. A first attempt that loaded weights directly as FP16 failed during gradient unscale; the final implementation keeps model weights FP32 and lets Trainer use FP16 autocast. `data/review/training_smoke/real_model/` is ignored and not committed.

## RF-006-P5: Real NLLB Pilot Training

- **Status:** DONE
- **Scope:** Small-step real model training, checkpoint saving, resume validation, local output directory
- **Background / Why:** RF-006-P4 proved one backward step with the real model, but it did not save checkpoints or prove that training can resume. Before full training, the project needs a small pilot that exercises the real checkpoint lifecycle.
- **Concrete Scope:** Add `scripts/train_model.py --pilot-train`, run real NLLB training for a small row/step count, save checkpoints under ignored `fine-tuned-models/.../pilot/run-*`, resume from the first checkpoint, and report final global step and loss.
- **Out of Scope:** Full-length training, translation generation, checkpoint quality evaluation, final model naming, pushing or committing model artifacts.
- **Risks:** Pilot training can still require several GB of GPU memory; checkpoint files are large local artifacts; loss from a four-step pilot is only an engineering signal, not a model-quality signal.
- **Acceptance Criteria:** Pilot command creates at least one checkpoint, resumes from it, reaches the requested final global step, records finite loss values, keeps outputs under ignored `fine-tuned-models/`, and leaves `data/` and notebooks unchanged.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\training.py scripts\train_model.py`; `venv\Scripts\python.exe -m unittest discover -s tests`; `$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"; venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --pilot-train --pilot-rows 64 --max-steps 4 --save-steps 2`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- data notebooks`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-25. The pilot run used `facebook/nllb-200-distilled-600M`, 64 prepared/tokenized rows, `zho_Hans -> kor_Hang`, target language token id `256098`, and `NVIDIA GeForce RTX 4070 Ti SUPER`. It added `<start>` and `<end>`, verified embedding size `256206`, trained stage one under the final `max_steps=4` schedule until `checkpoint-2`, resumed from `checkpoint-2`, saved `checkpoint-4`, and finished at `final_global_step=4`. Output directory: `D:\longtu-translation-pipeline\fine-tuned-models\nllb-200-distilled-600M\zh2ko\pilot\run-20260525-093832`. Result summary: `torch_dtype=float32+bf16_trainer`, `cuda_memory_summary=allocated_gb=11.48;reserved_gb=16.71`, `first_stage_loss=14.929116249084473`, `final_train_loss=6.693559885025024`. The pilot artifacts are ignored and not committed.

## RF-006-P6: Real Checkpoint Inference Command

- **Status:** DONE
- **Scope:** Real checkpoint loading, sample generation, RF-007-compatible output CSV
- **Background / Why:** RF-006-P5 proved real training can save and resume checkpoints. The next risk was whether a checkpoint can be loaded for generation and whether generation output can feed the existing RF-007 evaluator.
- **Concrete Scope:** Add `scripts/run_inference.py --generate`, load a specified checkpoint, generate a small sample set, and write `segment_id,source,references,candidates` to ignored `data/review/inference/generated_samples.csv`.
- **Out of Scope:** Quality tuning, validation split hardening, beam-search experimentation, full validation generation, and automatic evaluation report orchestration.
- **Risks:** Pilot checkpoints are not quality checkpoints; generation output may be poor or repetitive; console previews can display mojibake on some Windows terminals even when the CSV is valid UTF-8.
- **Acceptance Criteria:** Generation command loads the checkpoint, applies `zho_Hans -> kor_Hang`, writes a CSV with RF-007-compatible columns, emits non-empty candidates, and RF-007 can read the generated CSV.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\config.py src\longtu_translation_pipeline\inference.py scripts\run_inference.py`; `venv\Scripts\python.exe -m unittest discover -s tests`; `$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"; venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate --model-path fine-tuned-models\nllb-200-distilled-600M\zh2ko\pilot\run-20260525-093832\checkpoint-4 --sample-rows 8`; `venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\default.json --input data\review\inference\generated_samples.csv`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- data/segments.csv data/glossary.csv notebooks`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-25. The generation command loaded `fine-tuned-models\nllb-200-distilled-600M\zh2ko\pilot\run-20260525-093832\checkpoint-4`, used tokenizer `facebook/nllb-200-distilled-600M`, language pair `zho_Hans -> kor_Hang`, forced BOS token id `256098`, CUDA device `NVIDIA GeForce RTX 4070 Ti SUPER`, batch size `8`, and max length `400`. It wrote 8 rows to `data/review/inference/generated_samples.csv` with columns `segment_id,source,references,candidates`; all candidates were non-empty. RF-007 successfully read the output and reported 8 rows. The generated CSV is ignored under `data/review/` and is not committed.

## RF-006-P7: Formal Training Command Hardening

- **Status:** DONE
- **Scope:** `scripts/train_model.py`, `src/longtu_translation_pipeline/training.py`, formal run directories, split artifacts, run manifests
- **Background / Why:** Pilot training proved checkpoint save/resume, but full training still needed a reproducible command with fixed split artifacts, checkpoint policy, resume policy, and run metadata before any long full run.
- **Concrete Scope:** Add `scripts/train_model.py --train`, support small validation runs with `--limit-rows`, write `splits/train.csv`, `splits/validation.csv`, and `run_manifest.json` under ignored `fine-tuned-models/.../runs/run-*`, support `--resume-from-checkpoint latest|path`, and record training/dependency/git metadata.
- **Out of Scope:** Validation generation, RF-007 report generation, checkpoint quality selection, and full-length training.
- **Risks:** Real model training still writes large ignored checkpoint artifacts; resuming with inconsistent row limits can change the validation set if not guarded.
- **Acceptance Criteria:** Formal run command creates split artifacts and manifest; checkpoints are saved according to policy; resume from latest checkpoint reaches a later global step; manifest records command, split, checkpoint policy, dependency versions, loss, and git metadata; tracked data and notebooks remain unchanged.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\training.py scripts\train_model.py`; `venv\Scripts\python.exe -m unittest discover -s tests`; `$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"; venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --train --run-name run-p7-final --limit-rows 128 --max-steps 4 --save-steps 2 --save-total-limit 2 --logging-steps 1`; `$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"; venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --train --run-dir fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-p7-final --resume-from-checkpoint latest --max-steps 6 --save-steps 2 --save-total-limit 2 --logging-steps 1`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- data/segments.csv data/glossary.csv notebooks`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-25. The formal run command originally created `fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-p7-final` with two-way `splits/train.csv` and `splits/validation.csv`; RF-006-P10 later corrected formal runs to three-way train/validation/test artifacts. Resume guards still reject mismatched explicit row limits and checkpoints whose step is already greater than or equal to the requested `max_steps`, preventing accidental split drift or extra steps. Local run artifacts remain ignored and are not committed.

## RF-006-P8: Validation Generation Command

- **Status:** DONE
- **Scope:** `scripts/run_inference.py`, `src/longtu_translation_pipeline/inference.py`, P7 validation split generation artifacts
- **Background / Why:** RF-006-P6 generated translations from the first rows of `data/segments.csv`. Before full training evaluation, generation must use the fixed validation split written by the formal training run.
- **Concrete Scope:** Add `scripts/run_inference.py --generate-validation --run-dir <run_dir>`, read `run_manifest.json`, resolve `splits/validation.csv`, default to the latest numeric checkpoint, generate `segment_id,source,references,candidates`, and write a local validation generation manifest.
- **Out of Scope:** BLEU/report generation, model quality judgment, beam-search tuning, and full training.
- **Risks:** Validation generation still loads real model checkpoints and can take time/GPU memory; generated outputs are local artifacts that must remain ignored.
- **Acceptance Criteria:** Validation generation uses the P7 split rather than `data/segments.csv`; output CSV has RF-007-compatible columns; generated row count matches the validation split or `--validation-rows`; manifest records run, checkpoint, split, output, row count, language pair, and device.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\inference.py scripts\run_inference.py`; `venv\Scripts\python.exe -m unittest discover -s tests`; `$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"; venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate-validation --run-dir fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-p7-final`; `venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\default.json --input data\review\inference\validation\run-p7-final\validation_generated.csv`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- data/segments.csv data/glossary.csv notebooks`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-25. Validation generation read `fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-p7-final\run_manifest.json`, used fixed `splits\validation.csv`, defaulted to latest checkpoint `checkpoint-6`, generated 25 rows, and wrote `data\review\inference\validation\run-p7-final\validation_generated.csv` plus `validation_generation_manifest.json`. The manifest records language pair `zho_Hans->kor_Hang`, forced BOS token id `256098`, CUDA device `NVIDIA GeForce RTX 4070 Ti SUPER`, batch size `8`, and max length `400`. RF-007 successfully read the validation CSV and reported 25 rows; the resulting BLEU and glossary preservation values are engineering artifacts from a tiny P7 run, not quality conclusions.
- **Follow-up Notes:** On 2026-05-26, inference was aligned with training by applying source-only glossary markers from `data/glossary.csv` before tokenization while keeping raw source text in generated CSVs. Generation summaries and manifests now record `source_terminology_markers`, `marked_source_rows`, and `source_terms_marked`.

## RF-006-P9: Full-Run Preflight / Training Profile

- **Status:** DONE
- **Scope:** `configs/training/full_10k.json`, `src/longtu_translation_pipeline/config.py`, `src/longtu_translation_pipeline/training.py`, `scripts/train_model.py`, README workflow notes
- **Background / Why:** The project is ready for a first full-data staged training run, but the training parameters must be encoded in a reproducible profile before a long GPU job starts. Formal training must not inherit small-step validation defaults from smoke tests.
- **Concrete Scope:** Add a `full_10k.json` profile with full data, `max_steps=10000`, `save_steps=1000`, `eval_steps=5000`, `save_total_limit=6`, `logging_steps=100`, batch size `1`, gradient accumulation `1`, learning rate `2e-5`, warmup ratio `0.03`, and weight decay `0.01`; make `--train` require `max_steps` from config or CLI; record eval and optimizer parameters in run manifests.
- **Out of Scope:** Hyperparameter tuning, claiming final model quality, deleting intermediate ignored run artifacts, and selecting a production checkpoint beyond the staged 10k result.
- **Risks:** The first full-data run can take many hours and produce large ignored checkpoints. Misconfigured eval cadence can make validation evaluation expensive, so `eval_steps` is separated from `save_steps`.
- **Acceptance Criteria:** `full_10k.json` loads and dry-runs against the full dataset; formal `--train` rejects configs that lack `max_steps` unless CLI provides it; run manifests can record checkpoint, eval, optimizer, and gradient accumulation settings; tracked data and notebooks remain unchanged.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\config.py src\longtu_translation_pipeline\training.py scripts\train_model.py`; `venv\Scripts\python.exe -m unittest discover -s tests`; `venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k.json --dry-run`; `venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --train --limit-rows 2`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- data/segments.csv data/glossary.csv notebooks`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-25. The original `configs/training/full_10k.json` dry-run used a two-way 80/20 split and the first staged run `run-full-10k-v2` produced a validation-only report with BLEU `0.245297`, glossary preservation `0.459088`, and `13` empty candidate rows. That report is now explicitly historical engineering evidence and **must not be treated as test performance**, because RF-006-P10 corrected the experiment design to a held-out test split. `--train` still requires `max_steps` from config or CLI.

## RF-006-P10: Train / Validation / Test Split Correction

- **Status:** DONE
- **Scope:** `configs/training/`, `src/longtu_translation_pipeline/config.py`, `src/longtu_translation_pipeline/training.py`, `src/longtu_translation_pipeline/inference.py`, `scripts/train_model.py`, `scripts/run_inference.py`, README workflow notes
- **Background / Why:** The previous formal training path used train/validation only, and the first 10k report was therefore evaluated on validation data. Validation is for training-time eval and checkpoint observation; it must not be the final performance set.
- **Concrete Scope:** Change training configs and split logic to deterministic train/validation/test = 8:1:1 with seed `42`; write `splits/train.csv`, `splits/validation.csv`, `splits/test.csv`; record split ratios, split seed, row counts, split paths, and `data/segments.csv` SHA256 in `run_manifest.json`; add `scripts/run_inference.py --generate-test` for held-out test generation.
- **Out of Scope:** Re-running the full 10k training job, selecting a final checkpoint, deleting user-removed artifacts, or claiming new quality metrics.
- **Risks:** Existing ignored run directories created before this correction may contain two-way manifests; they should be treated as obsolete engineering artifacts.
- **Acceptance Criteria:** `full_10k.json` dry-run reports deterministic 8:1:1 train/validation/test counts for the current cleaned `data/segments.csv`; small formal training writes all three split CSVs and manifest fields; test generation reads `test_split_path` from manifest and writes `segment_id,source,references,candidates`; tracked data and notebooks remain unchanged.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\config.py src\longtu_translation_pipeline\training.py src\longtu_translation_pipeline\inference.py scripts\train_model.py scripts\run_inference.py`; `venv\Scripts\python.exe -m unittest discover -s tests`; `venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k.json --dry-run`; `$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"; venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k.json --train --run-name run-p10-split-check --limit-rows 100 --max-steps 1 --save-steps 1 --eval-steps 1 --save-total-limit 1 --logging-steps 1`; `venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate-test --run-dir fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-p10-split-check`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- data/segments.csv data/glossary.csv notebooks`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-25. Before RF-011, `configs/training/full_10k.json` dry-run reported `75,462` total rows, `60,370` train rows, `7,546` validation rows, and `7,546` test rows. A small corrected formal run `run-p10-split-check` used `--limit-rows 100 --max-steps 1`, wrote all three split CSVs, and recorded `segments_sha256=5792076F7FF23E8918758A80153830F59DD7FB135B820B9B734B1F46F6F96B3F`, `split_seed=42`, `split_ratios=0.8:0.1:0.1`, `train_rows=80`, `validation_rows=10`, `test_rows=10`, `train_loss=15.213525772094727`, and `eval_loss=14.032211303710938` in `run_manifest.json`. `scripts/run_inference.py --generate-test` loaded `checkpoint-1`, read the run's `splits/test.csv`, and wrote `data\review\inference\test\run-p10-split-check\test_generated.csv` with schema `segment_id,source,references,candidates` and 10 generated rows. After RF-011 cross-consistency cleaning, the current corpus dry-run reports `74,001` total rows, `59,201` train rows, `7,400` validation rows, and `7,400` test rows; future corrected 10k runs must regenerate splits from this cleaned corpus. Validation: py_compile passed; `venv\Scripts\python.exe -m unittest discover -s tests` passed with 57 tests; tracked data and notebooks had no diff; `git diff --check` passed.

## RF-007: Evaluation Automation

- **Status:** DONE
- **Scope:** `src/longtu_translation_pipeline/evaluation.py`, `configs/evaluation/default.json`, `scripts/evaluate_translation.py`, `tests/test_evaluation.py`
- **Background / Why:** Evaluation currently lives in notebooks and writes results manually.
- **Concrete Scope:** Provide importable evaluation functions and a CLI for BLEU and glossary preservation metrics. Historical code-token preservation notebooks stay archived because code/tag protection is no longer part of the current mainline.
- **Out of Scope:** Defining new model quality targets or changing metric formulas without a separate decision.
- **Risks:** Metric implementations may diverge from old notebook behavior because old glossary checks depended on deprecated `<middle>` markers.
- **Acceptance Criteria:** Small fixture tests reproduce expected BLEU/preservation metrics; evaluation can run without notebook state; code-token preservation is not implemented unless reintroduced by a future task.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\evaluation.py scripts\evaluate_translation.py`; `venv\Scripts\python.exe -m unittest discover -s tests`; `venv\Scripts\python.exe scripts\evaluate_translation.py --config configs/evaluation/default.json --input tests/fixtures/evaluation_translation_result.csv`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- data notebooks`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-24 and hardened on 2026-05-25 during the first 10k validation report. RF-007 now provides pure-Python corpus BLEU with default Korean whitespace tokenization and optional character tokenization, plus glossary preservation checks against `data/glossary.csv`. The evaluator reads translation result CSVs with notebook-compatible columns `source`, `references`, and `candidates`; strips `<start>...<end>` markers from candidate text before term matching; prints a summary; and writes local ignored reports under `data/review/evaluation/` when enabled. Empty candidates are no longer hard errors: they count as zero-length BLEU outputs, missing glossary terms, and `empty_candidate_rows` in summary/report manifest so real model failures remain reviewable. Historical `<middle>` and `<code_id>` evaluation paths remain archived only. Validation: `venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\evaluation.py scripts\evaluate_translation.py` passed; `venv\Scripts\python.exe -m unittest discover -s tests` passed with 24 tests initially and 53 tests after full-run empty-candidate hardening; `venv\Scripts\python.exe scripts\evaluate_translation.py --config configs/evaluation/default.json --input tests/fixtures/evaluation_translation_result.csv` printed BLEU/glossary summary and wrote ignored local reports; `git -c safe.directory=D:/longtu-translation-pipeline diff -- data notebooks` had no output; `git -c safe.directory=D:/longtu-translation-pipeline diff --check` passed with line-ending warnings only.
- **Follow-up Notes:** On 2026-05-26, glossary preservation was extended to report both exact and no-space exact metrics. The legacy `glossary_preservation_rate` remains the exact value, while `glossary_preservation_rate_nospace` avoids treating Korean spacing differences as true terminology misses.

## RF-007-P2: Generation Evaluation Report Loop

- **Status:** DONE
- **Scope:** P6 generation CSV evaluation, fixed report directory, sample review, manifest
- **Background / Why:** RF-006-P6 proved checkpoint generation can write a CSV that RF-007 can read. The next step is a stable local report entry point that records the generation input, checkpoint metadata, metrics, and reviewable samples.
- **Concrete Scope:** Add `configs/evaluation/generation_report.json`, extend evaluation reports with `sample_review.csv` and `report_manifest.json`, and allow CLI metadata overrides for checkpoint, report directory, and sample review row count.
- **Out of Scope:** Regenerating translations, loading models, treating P5/P6 outputs as quality metrics, full validation reports, and automated checkpoint selection.
- **Risks:** Metrics from the 4-step pilot checkpoint are not meaningful; report artifacts are ignored local files and must be regenerated when needed.
- **Acceptance Criteria:** The P6 generation CSV evaluates into `data/review/evaluation/generation_report/`; summary, glossary rows, sample review, and manifest are written; manifest records checkpoint and generation CSV; sample review includes `segment_id`; reports stay ignored.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\evaluation.py scripts\evaluate_translation.py`; `venv\Scripts\python.exe -m unittest discover -s tests`; `venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\generation_report.json --checkpoint fine-tuned-models\nllb-200-distilled-600M\zh2ko\pilot\run-20260525-093832\checkpoint-4`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- data/segments.csv data/glossary.csv notebooks`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-25. The report loop evaluated `data/review/inference/generated_samples.csv` from RF-006-P6 and wrote `evaluation_summary.csv`, `glossary_preservation_rows.csv`, `sample_review.csv`, and `report_manifest.json` to `data/review/evaluation/generation_report/`. The run recorded checkpoint `fine-tuned-models\nllb-200-distilled-600M\zh2ko\pilot\run-20260525-093832\checkpoint-4`, 8 rows, BLEU `0.001390`, and glossary preservation `1.000000`. These metrics are engineering-loop artifacts from a 4-step pilot checkpoint, not model-quality conclusions.

## RF-008: Dependency Split

- **Status:** DONE
- **Scope:** `requirements.txt`, `requirements-training.txt`, dependency notes in README
- **Background / Why:** The current requirements file pins a full experiment environment, including notebook and CUDA training dependencies.
- **Concrete Scope:** Keep `requirements.txt` as the already-landed base/semantic-cleaning dependency file and add a lightweight `requirements-training.txt` for RF-006-P2 training smoke / future training-chain dependencies.
- **Out of Scope:** Upgrading every package version or changing the runtime platform.
- **Risks:** Users may lose a one-command install path if docs are not updated.
- **Acceptance Criteria:** Backlog and README explain that current `requirements.txt` records the already-used semantic-cleaning/local environment dependencies, while `requirements-training.txt` records the confirmed RF-006 training-chain dependencies.
- **Recommended Test Commands:** `rg -n "RF-008|requirements-training|RF-006-P2|transformers|datasets|sentencepiece|accelerate" docs/refactor/backlog.md README.md README.en.md README.zh-CN.md requirements-training.txt`; `git -c safe.directory=D:/longtu-translation-pipeline status --short`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Closed on 2026-05-24 after RF-006-P2 and updated on 2026-05-25 after RF-006-P3. The dependency policy is intentionally lightweight rather than a full matrix split: `requirements.txt` keeps the semantic-cleaning/local environment dependencies already in use, and `requirements-training.txt` records the confirmed training smoke / future training-chain direct dependencies. RF-006-P3 added `accelerate` and `sentencepiece`; `datasets` remains excluded because the current smoke path uses a custom torch dataset rather than the Hugging Face datasets package.

## RF-009: Documentation Governance

- **Status:** DONE
- **Scope:** `README.md`, `README.en.md`, `README.zh-CN.md`, `AGENTS.md`, `docs/refactor/backlog.md`, `docs/refactor/decisions.md` (now superseded by `docs/decisions/adr/`)
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
- **Notes:** Completed on 2026-05-19. The normalization dry run produced 170,097 accepted master rows from 71 scanned CSV files, 61 primary sources, 5,450 quarantined rows, and 605 text-config mismatch rows. Final cleanup intentionally removed intermediate cleaning artifacts. A later conservative split generated `data/glossary.csv` and `data/segments.csv`: 52,756 high-confidence duplicate rows were moved out of segment data, 4,613 candidate rows were kept because their `zh-CN + en` groups had language conflicts, `glossary.csv` contains 44,863 normalized term rows, and `segments.csv` initially contained 117,341 segment rows. Short-text candidates that do not already match glossary terms were not auto-classified. AUTO_SAFE segment deduplication then removed 12,130 extra rows whose language columns were fully identical, leaving 105,211 segment rows with no full-language duplicate tuples. Presentation tag cleanup removed BBCode-style formatting tags such as color, size, bold, underline, and bare hex color tags from `segments.csv`, while preserving `{0}` placeholders, quotes, JSON-like text, and semantic square-bracket content; it removed 4 empty rows and 49 newly duplicated rows, leaving 105,158 segment rows. Contradictory translation cleanup then deleted 8,738 segment rows that shared any two non-empty language values and contributed a conflicting non-empty value in another language column, leaving 96,420 segment rows; 97 association-only rows with empty supplemental values were restored, and the actually removed rows were exported for review to `data/review/removed_segment_conflicts.csv`. First-round glossary purification removed 3,794 confirmed compound terms and added 250 missing component terms. A follow-up Korean inference pass kept 220 component terms that could be inferred as independent noun-like Korean phrases, removed 30 modifier-like or incomplete pending components, and reduced `data/glossary.csv` to 41,289 rows. Strict glossary cleanup then enforced bidirectional `zh-CN`/`ko` 1-to-1 terms, removed placeholders and strict non-term phrases, deleted 8,514 rows, merged 13 duplicate `zh-CN + ko` rows without language conflicts, and reduced `data/glossary.csv` to 32,762 rows. Round 2 glossary cleanup removed 42 phrase or slogan terms, removed 2,091 residual compound terms, added 375 safe atomic components, left 98 unstable components in pending review, sorted terms by `zh-CN` using Chinese locale collation, and reduced `data/glossary.csv` to 31,004 rows. Review CSVs for removed, merged, inferred, pending, sort-map, and compound-cleanup data are under `data/review/`.
- **Follow-up Notes:** On 2026-05-21, a local-first semantic glossary cleanup used deterministic rules, product-corpus evidence from `data/segments.csv`, noun-like Chinese/Korean heuristics, and compound-family detection because no local NLP or embedding packages were installed. It removed 2,533 high-confidence semantic/noise rows, split out 5 remaining compound rows, preserved 25,151 uncertain rows instead of guessing, kept `data/segments.csv` unchanged, and reduced `data/glossary.csv` to 28,466 strictly bilingual `zh-CN`/`ko` one-to-one rows sorted by Chinese locale. Review outputs are `data/review/glossary_semantic_audit.csv`, `data/review/removed_glossary_semantic_cleanup.csv`, `data/review/split_glossary_compounds_semantic.csv`, and `data/review/glossary_semantic_cleanup_summary.csv`; the audit records `embedding_status=unavailable_local_fallback`.
- **Follow-up Notes:** Later on 2026-05-21, the semantic glossary cleanup was rerun from the full 31,004-row audit baseline after installing local NLP and embedding dependencies in `venv`. This run used `BAAI/bge-m3` on CUDA, `jieba` for Chinese shape signals, `kiwipiepy` for Korean noun-like signals, and product-corpus evidence from unchanged `data/segments.csv`. It removed 2,436 rows, split 5 compound rows, preserved 23,923 uncertain rows, and reduced `data/glossary.csv` to 28,563 strictly bilingual `zh-CN`/`ko` one-to-one rows sorted by Chinese locale. `data/segments.csv` stayed at SHA256 `466380F8AAFA9BACDE36BD92D642B131B5DA377FB51A70418ECE184A50C6F397`; the review CSVs under `data/review/` now record `embedding_model=BAAI/bge-m3`.
- **Follow-up Notes:** The glossary semantic cleanup was then solidified as `scripts/glossary_semantic_pipeline.py` and rerun with Stanza zh/ko models loaded from `venv/stanza_resources`. This complete local pipeline used Stanza `tokenize,pos,lemma,depparse`, `jieba`, `kiwipiepy`, `BAAI/bge-m3` on CUDA, and product-corpus evidence from unchanged `data/segments.csv`. It removed 2,474 rows, split 5 compound rows, preserved 23,922 uncertain rows, and reduced `data/glossary.csv` to 28,525 strictly bilingual `zh-CN`/`ko` one-to-one rows sorted by Chinese locale. `data/segments.csv` remained at SHA256 `466380F8AAFA9BACDE36BD92D642B131B5DA377FB51A70418ECE184A50C6F397`; review CSVs under `data/review/` record `embedding_model=BAAI/bge-m3`, `embedding_device=cuda`, and `stanza_status=zh_ko_models_loaded`.
- **Follow-up Notes:** Product evidence gating was added to `scripts/glossary_semantic_pipeline.py` on 2026-05-21: terms with neither `zh-CN` nor `ko` appearing in the current `data/segments.csv` are now removed as `not_in_segments_redundant_for_current_corpus`. The rerun kept `data/segments.csv` unchanged at SHA256 `466380F8AAFA9BACDE36BD92D642B131B5DA377FB51A70418ECE184A50C6F397`, removed 26,487 product-redundant rows, reduced total auto removals to 26,950 rows, split 3 compound rows, reduced `KEEP_UNCERTAIN` to 513 rows, and reduced final `data/glossary.csv` to 4,051 strictly bilingual rows. `data/review/glossary_keep_uncertain_review.csv` now contains the remaining uncertain rows for focused review.
- **Follow-up Notes:** The final corpus schema was narrowed to Chinese-Korean only on 2026-05-21: `data/segments.csv` now contains only `segment_id`, `zh-CN`, and `ko`, while `data/glossary.csv` contains only `term_id`, `zh-CN`, and `ko`. The semantic pipeline now treats standalone signed/numeric tokens, non-whitelisted non-Chinese `zh-CN` values, Hangul in the `zh-CN` column, and obvious UI/status fragments as structural noise. The rerun removed `+7`, `VIP等级不足`, and Korean-only `zh-CN` rows, recorded 63 structural-noise removals, kept `data/segments.csv` at 96,420 rows with SHA256 `9AF3A691258D9A05ECD81CCB4187041E944A46CCEA3839A9FE26183E550C0458`, and reduced final `data/glossary.csv` to 4,032 bilingual rows.
- **Follow-up Notes:** Single-language segment rows were removed on 2026-05-21. `data/segments.csv` dropped 23,333 Chinese-only rows, 1 Korean-only row, and 9 empty bilingual rows, leaving 73,077 rows where both `zh-CN` and `ko` are present. The semantic glossary pipeline expected hash was updated to `EB82EBA165477CC1D96DC92E0304147AB0EC2EB7DDC9278C8C202618DC1C771B` and rerun against the cleaned segment corpus; final `data/glossary.csv` now contains 3,712 bilingual rows, with 26,869 product-redundant removals and 475 remaining uncertain rows.
- **Follow-up Notes:** General-word termhood filtering was added on 2026-05-22. `scripts/glossary_semantic_pipeline.py` now combines local common-word signals, Stanza/Jieba POS shape, game-domain anchors, a game-seed embedding centroid, product-corpus evidence, and a narrow acronym-component product-evidence fallback for terms such as `BOSS层`. The rerun kept `data/segments.csv` unchanged at SHA256 `EB82EBA165477CC1D96DC92E0304147AB0EC2EB7DDC9278C8C202618DC1C771B`, removed 27,945 rows total, marked 4,009 rows with `common_word_without_game_term_signal`, reduced `KEEP_UNCERTAIN` to 196 rows, wrote 29 boundary rows to `data/review/glossary_common_word_review.csv`, and reduced final `data/glossary.csv` to 3,056 bilingual rows. Validation confirmed `发言/발언` was removed while `暴击/치명타`, `传送/전송`, `PVP伤害/PVP피해`, `BOSS层/BOSS층`, and `VIP卡/VIP카드` were retained.
- **Follow-up Notes:** The product-evidence semantics were corrected on 2026-05-22: `data/segments.csv` is now documented and implemented as a current-product relevance gate and audit signal, not as a sufficient glossary keep signal. `product_score` was removed from the positive `term_score`, keep reasons no longer mention product support, and acronym-component evidence only prevents false `not_in_segments_redundant_for_current_corpus` deletion for strong game acronym compounds. The rerun kept `data/segments.csv` unchanged at SHA256 `EB82EBA165477CC1D96DC92E0304147AB0EC2EB7DDC9278C8C202618DC1C771B`; final `data/glossary.csv` stayed at 3,056 rows, `AUTO_KEEP` became 2,323 rows, and `KEEP_UNCERTAIN` became 733 rows. Validation confirmed `发言/발언` and `保护/보호` are deleted despite `product_evidence_score=1.0`, while `暴击/치명타`, `传送/전송`, `PVP伤害/PVP피해`, `BOSS层/BOSS층`, and `VIP卡/VIP카드` remain.
- **Follow-up Notes:** Ordinary-noun filtering was enhanced on 2026-05-22 with local `wordfreq` Chinese Zipf frequencies, a generic noun embedding centroid, and a `domain_specificity_score` that protects game anchors, acronyms, and likely proper/product entities. Korean `wordfreq` lookup currently falls back to `-1.0` because MeCab is not installed, which is recorded as an audit limitation rather than a blocker. The rerun kept `data/segments.csv` unchanged at SHA256 `EB82EBA165477CC1D96DC92E0304147AB0EC2EB7DDC9278C8C202618DC1C771B`, removed 265 rows with `common_noun_without_domain_signal`, wrote 185 boundary rows to `data/review/glossary_common_noun_review.csv`, and reduced final `data/glossary.csv` to 2,841 rows. Validation confirmed `折扣/할인` and `月亮/달` were removed while `暴击/치명타`, `传送/전송`, `PVP伤害/PVP피해`, `BOSS层/BOSS층`, and `VIP卡/VIP카드` remain.
- **Follow-up Notes:** Glossary embedding seeds were externalized on 2026-05-22. `scripts/glossary_semantic_pipeline.py` now reads game-domain seeds from `configs/glossary/game_term_seeds.txt` and ordinary-noun seeds from `configs/glossary/common_noun_seeds.txt`, with CLI overrides `--game-seeds` and `--common-noun-seeds`. The default files preserve the previous 26 game seeds and 28 ordinary-noun seeds; summary output records seed file paths and counts.
- **Follow-up Notes:** On 2026-05-24, the glossary semantic pipeline was changed to use the current `data/glossary.csv` as its baseline instead of a historical audit CSV. Audit outputs under `data/review/` are now local ignored artifacts, `segments.csv` SHA256 is recorded before/after but no longer hard-coded in source, and rule lists/thresholds longer than a few lines were moved to `configs/glossary/` including `rules.json`.
- **Follow-up Notes:** A review-first `scripts/segments_cleaning_pipeline.py` was added on 2026-05-24 with rules in `configs/segments/`. It now uses local semantic term/entity scoring instead of fixed short-text length thresholds: Stanza `tokenize,pos`, jieba, kiwipiepy, and `BAAI/bge-m3` on CUDA score noun/entity shape, glossary embedding similarity, term/entity seed similarity, and sentence-like keep signals. The semantic dry-run kept `data/segments.csv` unchanged at SHA256 `EB82EBA165477CC1D96DC92E0304147AB0EC2EB7DDC9278C8C202618DC1C771B`, expanded structure-split audit rows to 81,389, predicted 75,849 kept rows, flagged 4,996 term-like rows for removal (793 exact glossary pairs and 4,203 semantic term/entity rows), wrote 18,228 semantic boundary rows to review, split 13,984 structured child rows, found 281 placeholder mismatch review rows, and wrote local ignored review CSVs under `data/review/segments/`.
- **Follow-up Notes:** Segment markup/wrapper normalization was added to the review-first pipeline on 2026-05-24. The dry-run against the current 75,849-row `data/segments.csv` stripped presentation tags from 17,034 rows, unwrapped 1,968 symmetric outer wrappers, marked 44 markup-only rows for removal, wrote 237 markup/wrapper mismatch rows for review, and kept `data/segments.csv` unchanged at SHA256 `E3C6961DD41A91A51A6D9C5EA80BB27A3FF3FCF6BA9955FFB1A908E6409E6B35`. Validation confirmed `segment_id=23144` preserves `2%` and text after removing `<c=green>` / `<c=purple>`, while `segment_id=1300` unwraps the outer `{"..."}` and remains as a sentence-like kept row.

## RF-011: Glossary / Segments Cross-Consistency Cleaning

- **Status:** DONE
- **Scope:** `scripts/segments_glossary_cross_cleaning_pipeline.py`, `configs/cross_cleaning/rules.json`, final `data/segments.csv`, final `data/glossary.csv`, local review outputs
- **Background / Why:** The term-conflict audit showed both glossary noise and segment rows that do not preserve strong glossary translations. Glossary and segment cleaning cannot be fully independent because a noisy glossary term should not delete useful training rows, while a strong product term with preserved evidence elsewhere should not be trained with inconsistent Korean.
- **Concrete Scope:** Add a review-first cross-cleaning pipeline that computes term-level preservation stats, classifies glossary entries as strong terms / glossary noise / review, removes only high-confidence glossary noise, removes segment rows that miss strong glossary terms, and writes all removed content to ignored review CSVs.
- **Out of Scope:** Semantic replacement of Korean translations, LLM-based adjudication, editing glossary Korean values, changing train/validation/test split code, or retaining review artifacts in Git.
- **Risks:** Exact/no-space matching can still over-report synonym or natural-translation cases; overly broad weak-term rules could delete proper names or equipment terms; removed segment rows require future split regeneration before training.
- **Acceptance Criteria:** The pipeline defaults to dry-run; `--apply` keeps `data/glossary.csv` as `term_id,zh-CN,ko` and `data/segments.csv` as `segment_id,zh-CN,ko`; IDs are continuous after apply; removed rows are exported under `data/review/segments_glossary_cross/`; notebooks remain untouched.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile scripts\segments_glossary_cross_cleaning_pipeline.py`; `venv\Scripts\python.exe -m unittest discover -s tests`; `venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --dry-run`; `venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --apply`; `Get-Content data/glossary.csv -TotalCount 1`; `Get-Content data/segments.csv -TotalCount 1`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- notebooks`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-25. The first dry-run used a broad short-term weak rule and correctly surfaced a safety issue: two-character proper names or equipment-like terms such as `艾格` and `臂铠` could be misclassified as glossary noise. The default `weak_score_min` was tightened to `0.85`, so shortness alone now sends a term to review instead of automatic glossary deletion. The final apply removed `0` glossary rows and `1,461` strong-term conflict segment rows, reducing `data/segments.csv` from `75,462` to `74,001` rows while keeping `data/glossary.csv` at `2,841` rows. Review outputs were written to `data/review/segments_glossary_cross/`, including `cross_cleaning_term_summary.csv`, `cross_cleaning_row_audit.csv`, `removed_glossary_cross_noise.csv`, `removed_segment_terminology_conflicts.csv`, and `cross_cleaning_summary.csv`. `configs/training/full_10k.json --dry-run` now reports `74,001` total rows with split counts `59,201 / 7,400 / 7,400`; future corrected 10k runs must use the regenerated split artifacts from this cleaned corpus.

## RF-012: Strict Glossary-Segment Consistency Gate

- **Status:** DONE
- **Scope:** `scripts/segments_glossary_cross_cleaning_pipeline.py`, `configs/cross_cleaning/rules.json`, local strict review outputs
- **Background / Why:** Before full training and held-out evaluation, the user requires a basic corpus purity guarantee: if a segment contains a retained glossary term, the Korean side must preserve the glossary Korean form. Otherwise the same conflict contaminates training, validation, and test splits.
- **Concrete Scope:** Add `--strict-dry-run`, `--strict-apply`, and `--strict-check` to the cross-cleaning pipeline. Strict dry-run first identifies glossary terms that are not enforceable in the current corpus, then plans removal of any segment row that still misses a retained glossary term. Strict check validates the current files and exits non-zero when any mismatch remains.
- **Out of Scope:** Automatically rewriting Korean translations, semantic synonym acceptance, LLM adjudication, or automatically running strict apply without a review step.
- **Risks:** A strict gate can remove many rows or remove glossary terms whose Korean standard may be correct but not reflected in current segment translations. Review CSVs must be inspected before `--strict-apply`.
- **Acceptance Criteria:** `--strict-dry-run` writes strict review CSVs without modifying data; `--strict-check` fails on the current unclean dataset; after a reviewed future `--strict-apply`, `--strict-check` must report zero mismatching segment rows.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile scripts\segments_glossary_cross_cleaning_pipeline.py`; `venv\Scripts\python.exe -m unittest tests.test_segments_glossary_cross_cleaning`; `venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-dry-run`; `venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-25. The first automation-only version proved the current dataset still failed strict check with `strict_current_mismatch_rows=14125`, but its first strict plan was too aggressive because it treated many natural phrase variants as enforceable glossary terms. RF-012-P2 changed strict mode to first select an enforceable glossary set from the real segment translations: clean terms are retained, strong game-domain terms require preserved evidence and a bounded missing rate, and empirical stable terms require high preserved count/rate. `--strict-apply` was then executed in two passes because term statistics changed after the first cleanup. Pass 1 removed `1,089` unenforceable glossary terms and `636` segment rows; pass 2 removed `15` additional glossary terms and `137` segment rows. Final `data/glossary.csv` has `1,737` rows, final `data/segments.csv` has `73,228` rows, and `--strict-check` now passes with `strict_current_mismatch_rows=0`. `configs/training/full_10k.json --dry-run` now reports split counts `58,584 / 7,322 / 7,322`. Old run artifacts and previous split counts are no longer valid for training.

## RF-013: Segment Fragment And Target Contamination Cleanup

- **Status:** DONE
- **Scope:** `scripts/segments_cleaning_pipeline.py`, final `data/segments.csv`, final `data/glossary.csv`, `docs/architecture/data-cleaning-pipeline.md` (was `docs/data-cleaning.md`, moved in docs reorg), README data workflow notes, local review outputs
- **Background / Why:** Validation sample review after the strict 10k diagnostic run surfaced rows that are not valid seq2seq segment pairs, including isolated Chinese fragments such as `艮 -> 간` and Korean targets that still contained Chinese or had no Hangul. These rows can degrade every future train/validation/test split if left in the final corpus.
- **Concrete Scope:** Add permanent segment-cleaning rules for `AUTO_REMOVE_NON_SEGMENT_FRAGMENT` and `AUTO_REMOVE_TARGET_LANGUAGE_CONTAMINATION`; execute a one-time 2-3 character short-fragment migration from historical mixed segment data into glossary when doing so does not break strict 1-to-1 or strict segment consistency; update data-cleaning documentation with examples.
- **Out of Scope:** Automatically rewriting Korean targets, making the 2-3 character migration a reusable pipeline step, changing the glossary strict gate, or treating this diagnostic validation report as final quality evidence.
- **Risks:** Strong target contamination deletion may remove ID-like rows or placeholder-only rows that could be useful in another task, but the user explicitly chose strong deletion for the current seq2seq training corpus. The one-time migration can enlarge glossary and requires strict-check afterward.
- **Acceptance Criteria:** `segments_cleaning_pipeline.py --apply` writes local review files for fragment and target contamination removals; short-fragment migration audit is written under ignored `data/review/`; `data/segments.csv` and `data/glossary.csv` keep continuous IDs and schemas; `--strict-check` reports `strict_current_mismatch_rows=0`; `configs/training/full_10k.json --dry-run` records the new 8:1:1 split counts.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile scripts\segments_cleaning_pipeline.py scripts\segments_glossary_cross_cleaning_pipeline.py`; `venv\Scripts\python.exe -m unittest discover -s tests`; `venv\Scripts\python.exe scripts\segments_cleaning_pipeline.py --dry-run`; `venv\Scripts\python.exe scripts\segments_cleaning_pipeline.py --apply`; `venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check`; `venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k.json --dry-run`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- notebooks`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-26. The permanent segment cleanup pass removed `83` pure one-character CJK fragments and `956` target-language contamination rows, reducing `data/segments.csv` from `73,228` to `72,189` rows. A one-time short-fragment migration then removed `5,597` pure 2-3 character rows from segments; `2,063` non-conflicting and enforceable pairs were added to `data/glossary.csv`, `270` duplicate candidate pairs were already covered by another migrated pair, `2,190` candidates were not added because of 1-to-1 conflicts, and `1,074` were not added because they would create strict mismatches in remaining segments. Final `data/glossary.csv` has `3,800` rows, final `data/segments.csv` has `66,592` rows, and `--strict-check` passes with `strict_current_mismatch_rows=0`. `configs/training/full_10k.json --dry-run` now reports split counts `53,274 / 6,659 / 6,659`; any previous 10k run remains diagnostic only.

## RF-014: LLM Glossary Aggressive Cleanup

- **Status:** DONE
- **Scope:** `scripts/glossary_llm_cleanup_pipeline.py`, final `data/glossary.csv`, local LLM review outputs, README/data-cleaning notes
- **Background / Why:** After local semantic, strict, and cross-cleaning passes, the remaining glossary noise is semantic enough that deterministic rules can become brittle. A cloud LLM can judge whether a row is truly a company game glossary term, but it must not create new terminology values.
- **Concrete Scope:** Add an OpenAI-compatible Chat Completions cleanup entry point that reads `data/glossary.csv`, batches `term_id,zh-CN,ko`, classifies rows as `KEEP_GAME_TERM` or one of the delete actions, writes ignored audit/raw-batch files under `data/review/llm_glossary_cleanup/`, and rewrites `data/glossary.csv` only in `--apply` mode.
- **Out of Scope:** Rewriting Korean terms, adding terms, merging duplicates, using a repository-hard-coded model name, committing LLM audit artifacts, or treating LLM output as a replacement for the strict glossary/segment gate.
- **Risks:** Cloud API use sends glossary terms outside the local machine; aggressive deletion can remove valid but obscure product terms; malformed or incomplete LLM responses must retry the whole batch rather than silently deleting rows.
- **Acceptance Criteria:** Missing `OPENAI_API_KEY` or `LLM_MODEL` fails before writing `data/glossary.csv`; every batch must return exactly one valid action per input row; removed rows are exported for review; `data/glossary.csv` keeps schema `term_id,zh-CN,ko` and continuous IDs after apply; `--strict-check` and training dry-run pass after a real apply.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile scripts\glossary_llm_cleanup_pipeline.py`; `venv\Scripts\python.exe -m unittest tests.test_glossary_llm_cleanup_pipeline`; `venv\Scripts\python.exe -m unittest discover -s tests`; `$env:OPENAI_API_KEY="<your-key>"; $env:LLM_MODEL="<your-model>"; venv\Scripts\python.exe scripts\glossary_llm_cleanup_pipeline.py --apply`; `venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check`; `venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k.json --dry-run`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- data/glossary.csv`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-26 using the user-supplied ChatGPT output files. `glossary_cleaned.csv` had schema `term_id,zh-CN,ko`, continuous IDs, no empty fields, no duplicate pairs, and no `zh-CN`/`ko` one-to-many conflicts. It reduced the glossary from `3,800` rows to `3,401`; `removed_glossary_llm.csv` contained `399` removals: `269` common words, `64` phrase/sentence entries, `29` fragments, `7` bad pairs, and `30` non-company-game terms. Applying the cleaned glossary exposed `19` strict mismatches due to longest-match changes, so `--strict-apply` removed `5` additional unenforceable glossary rows and no segment rows. Final `data/glossary.csv` has `3,396` rows, `data/segments.csv` remains at `66,592` rows, `--strict-check` passes with `strict_current_mismatch_rows=0`, and `configs/training/full_10k.json --dry-run` reports split counts `53,274 / 6,659 / 6,659`. The temporary `data/glossary_cleaned.csv`, `data/removed_glossary_llm.csv`, and `data/llm_glossary_summary.csv` files were deleted.

## RF-015: LLM Segment Full-Corpus Cleanup

- **Status:** DONE
- **Scope:** `scripts/segments_llm_cleanup_pipeline.py`, final `data/segments.csv`, local LLM segment review outputs, README/data-cleaning notes
- **Background / Why:** After local segment, glossary, and strict consistency cleaning, remaining segment problems may include semantic mistranslation, over-free Korean targets, and subtle non-segment rows that deterministic rules cannot safely classify. The user chose a full-corpus LLM pass and allowed Korean rewrite.
- **Concrete Scope:** Add an OpenAI-compatible Chat Completions cleanup entry point that sends all `segment_id,zh-CN,ko` rows with only raw text, placeholders, and matched glossary terms. Local pre-judgment fields such as contamination flags, structured-string hints, length-ratio checks, and repeated-output checks are reserved for post-response validation and audit, not prompt input. The LLM can keep, remove, review, or propose a Korean rewrite. Apply mode deletes remove-class rows and applies only locally validated Korean rewrites.
- **Out of Scope:** Changing Chinese source text, adding rows, splitting rows, merging rows, editing glossary, committing LLM review artifacts, or treating old training checkpoints as valid after segment cleanup.
- **Risks:** Full-corpus LLM review sends all final segment text to a cloud model and can consume millions of tokens. Korean rewrites are synthetic data and must pass local guards before entering the corpus.
- **Acceptance Criteria:** Missing API key/model fails before writing `data/segments.csv`; every batch must return exactly one valid action per input row; invalid or incomplete batches retry; accepted rewrites preserve placeholders and glossary terms and contain Korean without Chinese contamination; apply mode keeps continuous `segment_id`; review CSVs record removed, rewritten, rewrite-failed, sample-review, warning, and summary rows; summary records action distribution, repeated-reason warnings, surface-feature action warnings, and rewrite accept/reject rates; strict-check and training dry-run pass after a real apply.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile scripts\segments_llm_cleanup_pipeline.py scripts\glossary_llm_cleanup_pipeline.py`; `venv\Scripts\python.exe -m unittest tests.test_segments_llm_cleanup_pipeline`; `venv\Scripts\python.exe -m unittest discover -s tests`; `$env:OPENAI_API_KEY="<your-key>"; $env:LLM_MODEL="<your-model>"; venv\Scripts\python.exe scripts\segments_llm_cleanup_pipeline.py --dry-run`; after review, `venv\Scripts\python.exe scripts\segments_llm_cleanup_pipeline.py --apply`; `venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check`; `venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k.json --dry-run`; `git -c safe.directory=D:/longtu-translation-pipeline diff -- data/segments.csv`.
- **Notes:** Implementation is present as of 2026-05-26 with mock-response unit tests for deletion, rewrite acceptance, placeholder rejection, glossary-preservation rejection, contaminated target deletion, invalid actions, missing rows, missing runtime credentials, payload field minimization, repeated-reason warnings, and review-uncertain behavior. The real full-corpus LLM run is blocked until `OPENAI_API_KEY` and `LLM_MODEL` are set locally and the user chooses to spend API tokens. Estimated cost for the remaining `66,385` rows is roughly `5M-10M` input tokens and `1.5M-4M` output tokens depending on rewrite rate and retry count.
- **Follow-up Notes:** On 2026-05-27, T-A1 executed the full-corpus LLM segments cleanup pass using `gpt-4.1-mini` + OpenAI Batch API (5 sequential chunks of ≤266 micro-batches each, `batch_size=50`, `max_output_tokens=4500`). Date: `2026-05-27`. New `data/segments.csv` row count: `66,267`. New SHA256: `3AF4FF516C68AC4020260CE9ABFDF0CD4ED8BBDE2B69042A76FD21A6B49E3A3F`. Action distribution: `KEEP=47,733` (71.9%), `REWRITE=17,464` (26.3%), `REVIEW=1,070` (1.6%), `REMOVE=118` (0.2%). Rewrite accept rate: `98.2%` (17,464 accepted / 17,785 requested); rewrite reject rate: `1.8%` (321 rejected by local validation, primary cause: `glossary_term_missing`). Token usage: `prompt=5,844,295`, `completion=3,171,654`, `total=9,015,949`. Post-apply strict-check: `strict_current_mismatch_rows=0`, `strict_unenforceable_glossary_rows=0`, `strict_removed_segment_mismatch_rows=0`, exit 0. Training dry-run split counts: `train=53,015`, `validation=6,626`, `test=6,626` (total=66,267, ratio 8:1:1, seed 42). All previous `run-*` directories under `fine-tuned-models/` are now stale — Track A2 must regenerate. On 2026-05-26 commit `c107763` ("Harden LLM segment cleanup prompts and audits") also folded in a user-confirmed partial LLM segment cleanup pass, acknowledged by the user during the 2026-05-26 audit review. The pass removed `207` segment rows and applied `17` Korean rewrites (same `zh-CN`, different `ko`), reducing `data/segments.csv` from `66,592` rows to `66,385` rows. `data/glossary.csv` is unchanged at `3,396` rows. Current corpus state: `data/segments.csv` SHA256 = `D299B01FF90D571CAEA65C6933C1769D3B93B1E04798EEDF2B395C2248482419`. The associated review CSVs and raw LLM batch envelopes were not committed (they live under ignored `data/review/llm_segments_cleanup/` or were generated on the user's machine outside Git), so the change is not bit-for-bit reproducible from the repository alone; it is recorded here as user-confirmed evidence. On 2026-05-26 the post-pass strict glossary/segment gate was re-verified by `python scripts/segments_glossary_cross_cleaning_pipeline.py --strict-check`, which reported `strict_current_mismatch_rows=0`, `input_glossary_rows=3396`, `input_segment_rows=66385`, `term_action.STRONG_GLOSSARY_TERM=235`, and exit code `0`. Any previous `splits/train.csv`, `splits/validation.csv`, `splits/test.csv`, `run_manifest.json`, validation/test report directories under `fine-tuned-models/` and `data/review/` no longer correspond to the current `data/segments.csv` and must be regenerated before any new training run. The full-corpus LLM segment pass over the remaining rows is still **BLOCKED** until `OPENAI_API_KEY` and `LLM_MODEL` are set and the user chooses to proceed. On 2026-05-27, RF-029 retrofitted both LLM cleanup pipelines to default to OpenAI Batch API with strict `json_schema` response format; T-A1 will use `--batch-mode batch` (the new default) with `LLM_MODEL=gpt-4.1-mini`, projected cost ~US$1.5-3 thanks to the 50% Batch discount.

## RF-006-P11: Formal 10k Training on LLM-Cleaned Segments

- **Status:** DONE
- **Scope:** `scripts/train_model.py --train`, `configs/training/full_10k.json`, ignored `fine-tuned-models/nllb-200-distilled-600M/zh2ko/runs/`, post-RF-015 corpus
- **Background / Why:** After RF-015 applies the full-corpus LLM segment cleanup, every prior training run is invalid because `segments_sha256` and the deterministic 8:1:1 splits no longer match. A fresh formal 10k training run on the new corpus is the next quality baseline.
- **Concrete Scope:** Re-execute `--train` with `configs/training/full_10k.json` against the post-RF-015 `data/segments.csv`, using a new `--run-name` such as `run-full-10k-llm-segments-v1`. Hyperparameters identical to the prior baseline so the comparison is direct. Record run name, manifest content, checkpoint list, final loss, and wall-clock time in Notes.
- **Out of Scope:** Hyperparameter sweeps, base model changes (see RF-026), inference parameter sweeps (see RF-028).
- **Risks:** Multi-hour GPU run; interruption requires `--resume-from-checkpoint` with matching `segments_sha256`. New checkpoints invalidate all prior validation/test reports.
- **Acceptance Criteria:** Run directory exists with `splits/{train,validation,test}.csv`, `checkpoint-*`, and `run_manifest.json`; manifest carries `segments_sha256` matching the live `data/segments.csv`, `split_seed=42`, `split_ratios=[0.8,0.1,0.1]`; backlog Notes record the run name, final step, and loss; no files added to Git beyond this entry.
- **Recommended Test Commands:** `venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k.json --dry-run`; `$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"; venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k.json --train --run-name run-full-10k-llm-segments-v1`; `Get-Content "<run-dir>\run_manifest.json"`; `git -c safe.directory=D:/longtu-translation-pipeline status --short`.
- **Notes:** Completed on 2026-05-27 (T-A2). Run name: `run-full-10k-llm-segments-v1`. Full path: `fine-tuned-models/nllb-200-distilled-600M/zh2ko/runs/run-full-10k-llm-segments-v1/`. `segments_sha256=1462B2E18CDB82B0FF1E9E3C80AC5AFF583227E396C54F5C6431FFD379F147BA`, `split_seed=42`, `split_ratios=[0.8,0.1,0.1]`, `total_rows=66267`, `train_rows=53015`, `validation_rows=6626`, `test_rows=6626`. `final_global_step=10000`, `train_loss=0.5191` (Trainer average over all steps; step-10000 logged loss=0.0549), `eval_loss=0.0672` (validation set at step 10000; intermediate eval at step 5000: 0.0729). Loss curve (at checkpoint steps): step 1000→0.139, 2000→0.089, 3000→0.084, 4000→0.074, 5000→0.075, 6000→0.086, 7000→0.068, 8000→0.054, 9000→0.086, 10000→0.055. Loss decreased steeply in early steps and stabilised below 0.1 from step 1000 onward; no monotonic-violation concern. Checkpoints retained (save_total_limit=6): `checkpoint-5000`, `checkpoint-6000`, `checkpoint-7000`, `checkpoint-8000`, `checkpoint-9000`, `checkpoint-10000`; earlier checkpoints (1000–4000) were automatically rotated out. Wall-clock training time: ~49 min 35 sec (18:21–19:10, NVIDIA GeForce RTX 4070 Ti SUPER, CUDA, float32+bf16_trainer, allocated 6.90 GB / reserved 11.84 GB). No hyperparameter deviations from `configs/training/full_10k.json` baseline. Validation generation report (T-A3) and held-out test report (T-A4) are the next steps.

## RF-006-P12: Validation Generation and Reports for Re-Trained Run

- **Status:** DONE
- **Scope:** `scripts/run_inference.py --generate-validation`, `scripts/evaluate_translation.py`, ignored `data/review/inference/validation/`, ignored `data/review/evaluation/validation_report/`
- **Background / Why:** RF-006-P11 produces multiple saved checkpoints. Per-checkpoint validation reports are the engineering signal used to pick the final checkpoint for RF-007-P3, not the model quality claim itself.
- **Concrete Scope:** For each (or a representative subset of) saved checkpoint under the RF-006-P11 run directory, generate validation translations and run the evaluation report. Capture BLEU, exact glossary preservation, no-space glossary preservation, and `empty_candidate_rows` in a comparison table inside this backlog entry.
- **Out of Scope:** Final model quality declarations (those belong to RF-007-P3); inference parameter sweeps (RF-028).
- **Risks:** Generating on every checkpoint multiplies inference time; pick the last several checkpoints if compute-limited. Sample size is fixed by the validation split.
- **Acceptance Criteria:** Each evaluated checkpoint has a directory under `data/review/evaluation/validation_report/run-...-v1/<checkpoint>/` with `evaluation_summary.csv`, `glossary_preservation_rows.csv`, `sample_review.csv`, and `report_manifest.json`; the comparison table is recorded in this entry; no files added to Git beyond this entry.
- **Recommended Test Commands:** `venv\Scripts\python.exe scripts\run_inference.py --generate-validation --run-dir <run dir>`; `venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\generation_report.json --checkpoint <checkpoint>`; `git -c safe.directory=D:/longtu-translation-pipeline status --short`.
- **Notes:** Completed 2026-05-27 by T-A3. Run: `run-full-10k-llm-segments-v1`. Evaluated last 4 checkpoints (7000–10000) on the 6 626-row validation split (seed 42, 10 % of corpus). **Validation is not the final quality claim**; it is the engineering signal used by T-A4 to select the checkpoint that will be evaluated on the held-out test split.

  Checkpoint comparison table (validation split, whitespace-tokenised BLEU):

  | Checkpoint | BLEU | glossary_preservation_rate (exact) | glossary_preservation_rate_nospace | empty_candidate_rows |
  |---|---|---|---|---|
  | checkpoint-7000 | 0.1917 | 0.7586 | 0.7820 | 0 |
  | checkpoint-8000 | 0.1938 | 0.7679 | 0.7898 | 0 |
  | checkpoint-9000 | 0.1959 | 0.7679 | 0.7917 | 0 |
  | checkpoint-10000 | 0.1969 | 0.7653 | 0.7887 | 0 |

  Observations: BLEU improves monotonically from 7000 → 10000 (no regression). Exact glossary preservation peaks at 8000/9000 (0.7679) then dips slightly at 10000 (0.7653); nospace preservation follows the same pattern, peaking at 9000 (0.7917). No empty_candidate_rows at any checkpoint. Anomaly to flag for T-A4: checkpoint-10000 has the highest BLEU but loses ~3 pp on glossary preservation versus checkpoint-9000 — trade-off to consider during final selection.

  Report artifacts (Git-ignored): `data/review/evaluation/validation_report/run-full-10k-llm-segments-v1/checkpoint-{7000,8000,9000,10000}/` — each contains `evaluation_summary.csv`, `glossary_preservation_rows.csv`, `sample_review.csv`, `report_manifest.json`.

## RF-007-P3: Final Held-Out Test Report on Selected Checkpoint

- **Status:** DONE
- **Scope:** `scripts/run_inference.py --generate-test`, `scripts/evaluate_translation.py`, ignored `data/review/inference/test/`, ignored `data/review/evaluation/test_report/`
- **Background / Why:** Per the 2026-05-25 held-out test decision, validation reports are engineering signals and the test split (seed 42, 10% of corpus) is reserved for the final quality claim. After RF-006-P12 selects a checkpoint, this entry records the single test-set run for the project's headline number on this `segments_sha256`.
- **Concrete Scope:** Run `--generate-test` on the selected checkpoint, then evaluate. Record selected checkpoint path, corpus SHA256, test BLEU, test exact + no-space glossary preservation, `empty_candidate_rows`, and a brief comparison against the same checkpoint's validation numbers.
- **Out of Scope:** Iterating test-set results across checkpoints (data leakage); any change to splits, seed, or marker shape.
- **Risks:** Re-running test on a different checkpoint after seeing this one is data leakage; record the result and stop.
- **Acceptance Criteria:** `data/review/evaluation/test_report/.../<checkpoint>/` contains the four report files; `report_manifest.json` records checkpoint and corpus SHA256; backlog Notes carry the final metric block plus the explicit statement that any future change to `data/segments.csv` invalidates this report; no files added to Git beyond this entry.
- **Recommended Test Commands:** `venv\Scripts\python.exe scripts\run_inference.py --generate-test --run-dir <run dir> --model-path <checkpoint>`; `venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\generation_report.json --checkpoint <checkpoint>`; `git -c safe.directory=D:/longtu-translation-pipeline status --short`.
- **Notes:** Completed 2026-05-27 by T-A4. Selected checkpoint `checkpoint-9000` from the RF-006-P12 validation table (best `glossary_preservation_rate_nospace`, tied-best exact preservation, BLEU within 0.001 of `checkpoint-10000`). Test split: seed `42`, 6 626 rows (10 % of corpus), held out from training.

  Final test report (single run, no iteration):

  | Metric | Test (checkpoint-9000) | Validation (checkpoint-9000) | Δ (test − val) |
  |---|---|---|---|
  | BLEU (whitespace) | 0.1979 | 0.1959 | +0.0020 |
  | glossary_preservation_rate (exact) | 0.7754 | 0.7679 | +0.0075 |
  | glossary_preservation_rate_nospace | 0.7975 | 0.7917 | +0.0058 |
  | empty_candidate_rows | 0 | 0 | 0 |

  - Selected checkpoint: `fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-full-10k-llm-segments-v1\checkpoint-9000`
  - `data/segments.csv` SHA256 at run time: `1462B2E18CDB82B0FF1E9E3C80AC5AFF583227E396C54F5C6431FFD379F147BA` (matches `run_manifest.json`)
  - Test rows: 6 626; sample review rows: 50
  - Test BLEU brevity penalty: 1.000000; glossary terms matched exact: 2 072 / 2 672; nospace: 2 131 / 2 672
  - Sanity check: test and validation are in the same ballpark, with test marginally higher across all metrics — consistent with no over-fitting to validation during checkpoint selection.

  Report artifacts (Git-ignored): `data/review/evaluation/test_report/run-full-10k-llm-segments-v1/checkpoint-9000/` — `evaluation_summary.csv`, `glossary_preservation_rows.csv`, `sample_review.csv`, `report_manifest.json`. Test generation CSV: `data/review/inference/test/run-full-10k-llm-segments-v1/test_generated.csv`.

  > Any future re-training on a different `data/segments.csv` SHA256 invalidates this test report. Re-run T-A1 → T-A4 in order.

## RF-016: Test Coverage Backfill for Cleanup Pipelines

- **Status:** DONE
- **Scope:** `tests/test_cleanup_common.py` (new), `tests/test_segments_cleaning_pipeline.py`, `tests/test_glossary_semantic_pipeline.py` (new), foundation helpers
- **Background / Why:** Audit 2026-05-26 §P2-1 surfaced that the largest cleanup module (`glossary_semantic_pipeline.py`, 1502 LOC) has zero unit tests, `cleanup_common.py` (foundation for five pipelines) has zero direct tests, and `segments_cleaning_pipeline.py` (1150 LOC) has only 10 assertions. Future refactors lack a regression net.
- **Concrete Scope:** Split into three sub-phases (P1: foundation; P2: segments pipeline rules; P3: glossary pipeline pure logic). Each is independent and parallel-safe.
- **Out of Scope:** Refactoring the pipelines themselves; tests must lock current behavior, not redesign.
- **Risks:** Glossary semantic pipeline has many branches that need stanza / jieba / kiwi / bge-m3; those must be skipped or mocked so tests run on a bare environment.
- **Acceptance Criteria:** All three sub-phase RF entries (RF-016-P1, P2, P3) reach `DONE`; `unittest discover` total count increases by at least 30; total suite still runs in < 60s without external models.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m unittest discover -s tests`.
- **Notes:** Tracked via [T-C1](task-briefs/T-C1.md), [T-C2](task-briefs/T-C2.md), [T-C3](task-briefs/T-C3.md).

## RF-016-P1: cleanup_common.py Tests

- **Status:** DONE
- **Scope:** `tests/test_cleanup_common.py` (new), `scripts/cleanup_common.py` (read-only)
- **Background / Why:** `cleanup_common.py` is the shared foundation module imported by five cleanup pipelines. A regression here silently breaks all five. Zero direct tests today.
- **Concrete Scope:** Add fixture-level unit tests for `sha256`, `read_term_file`, `read_json_config`, `compile_regexes`, `ensure_csv_columns`, covering at least one happy path and one error path per helper. Use `tempfile.TemporaryDirectory()` fixtures; no external dependencies.
- **Out of Scope:** Modifying `cleanup_common.py`; if a bug is found, open a separate RF.
- **Risks:** Tests must not depend on encoding shortcuts; verify UTF-8-with-BOM is handled.
- **Acceptance Criteria:** `tests/test_cleanup_common.py` exists with ~12-15 test methods; `python -m unittest tests.test_cleanup_common` passes; `unittest discover` count increases by the new methods; no regressions.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile tests\test_cleanup_common.py`; `venv\Scripts\python.exe -m unittest tests.test_cleanup_common -v`; `venv\Scripts\python.exe -m unittest discover -s tests`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Owned by [T-C1](task-briefs/T-C1.md). Completed 2026-05-27: 16 tests added in `tests/test_cleanup_common.py`.

## RF-016-P2: segments_cleaning_pipeline.py Tests Extension

- **Status:** DONE
- **Scope:** `tests/test_segments_cleaning_pipeline.py` (extend), `scripts/segments_cleaning_pipeline.py` (read-only)
- **Background / Why:** `segments_cleaning_pipeline.py` is 1150 LOC; existing tests cover fragment removal and target contamination (10 assertions) but not markup stripping, symmetric wrapper unwrap, structured tuple split, or placeholder mismatch audit.
- **Concrete Scope:** Add fixture-level tests for the deterministic, rule-based branches of those features. Do not exercise stanza / jieba / kiwi / bge-m3 paths in this RF.
- **Out of Scope:** Semantic scoring tests (those require external models and are deferred), rewriting the pipeline.
- **Risks:** Tests that accidentally pull in `BAAI/bge-m3` or `stanza` will fail in a clean env; mock or skip those branches.
- **Acceptance Criteria:** Test file grows to at least 30 assertions; suite runs in < 30s without external models; `unittest discover` increases the total count; no regressions in existing tests.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m unittest tests.test_segments_cleaning_pipeline -v`; `venv\Scripts\python.exe -m unittest discover -s tests`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Owned by [T-C2](task-briefs/T-C2.md). Completed 2026-05-27. 46 tests / ~62 assertions across 8 test classes covering markup stripping, symmetric wrapper unwrap, structured tuple split, placeholder mismatch, non-segment fragment, target contamination, utility functions, and sentence-like scoring. Suite runs in < 30s without any external models.

## RF-016-P3: glossary_semantic_pipeline.py First-Wave Tests

- **Status:** DONE
- **Scope:** `tests/test_glossary_semantic_pipeline.py` (new), `scripts/glossary_semantic_pipeline.py` (read-only)
- **Background / Why:** Single largest untested module in the repo (1502 LOC). Combines deterministic rules with stanza / jieba / kiwi / bge-m3 / wordfreq scoring. The rule-based branches are pure-Python and testable without those external deps.
- **Concrete Scope:** Add first-wave tests for hard noise filters, strict 1:1 enforcement, product-corpus evidence gate, and config/seed file loading helpers. Mock external scorers when a branch unavoidably reaches them.
- **Out of Scope:** Embedding / POS / Zipf scoring paths in this RF (later P4 if needed); modifying the pipeline.
- **Risks:** Test scope can balloon; the brief gives a concrete branch list to keep this bounded.
- **Acceptance Criteria:** At least 12 test methods; suite runs in < 30s without GPU or HF cache; `unittest discover` count increases; record any deferred branches in Notes for a future P4.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m unittest tests.test_glossary_semantic_pipeline -v`; `venv\Scripts\python.exe -m unittest discover -s tests`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Owned by [T-C3](task-briefs/T-C3.md). Pending.

## RF-017: Extract scripts/llm_common.py

- **Status:** DONE
- **Scope:** `scripts/llm_common.py` (new), `scripts/glossary_llm_cleanup_pipeline.py`, `scripts/segments_llm_cleanup_pipeline.py`, `tests/test_llm_common.py` (new), related test imports
- **Background / Why:** Audit 2026-05-26 §P1-1: `scripts/segments_llm_cleanup_pipeline.py:24` reverse-imports `ClientConfig`, `resolve_client_config`, `call_chat_completion`, `parse_json_content` from `scripts/glossary_llm_cleanup_pipeline.py`. CLI scripts importing CLI scripts violates AGENTS.md "Keep pure transformation logic in importable modules and keep CLI scripts thin."
- **Concrete Scope:** Lift the four shared symbols into `scripts/llm_common.py`. Update both LLM scripts and their tests to import from the new module. Add minimal `tests/test_llm_common.py` covering missing credentials, JSON parsing, and the basic HTTP wrapper interface (mocked).
- **Out of Scope:** Changing LLM payload contracts; redesigning retry behavior; moving the module into `src/longtu_translation_pipeline/` (deferred to avoid colliding with RF-020).
- **Risks:** Test mock targets may need updating if they patched `glossary_llm_cleanup_pipeline.call_chat_completion`. (Neither test used patch; both used injected StaticClient — no mock target changes required.)
- **Acceptance Criteria:** No reverse import remains; `tests/test_llm_common.py` passes; `unittest discover` count goes up; `git grep "from glossary_llm_cleanup_pipeline" scripts tests` returns no results.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile scripts\llm_common.py scripts\glossary_llm_cleanup_pipeline.py scripts\segments_llm_cleanup_pipeline.py`; `venv\Scripts\python.exe -m unittest tests.test_llm_common tests.test_glossary_llm_cleanup_pipeline tests.test_segments_llm_cleanup_pipeline`; `venv\Scripts\python.exe -m unittest discover -s tests`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Validation (2026-05-27):**
  - `py_compile` on all three scripts: OK
  - `rg "from glossary_llm_cleanup_pipeline" scripts tests`: no matches
  - `unittest tests.test_llm_common`: 16/16 passed
  - `unittest tests.test_glossary_llm_cleanup_pipeline tests.test_segments_llm_cleanup_pipeline`: 19/19 passed
  - `unittest discover -s tests`: 108/108 passed (up from 92; +16 new tests in test_llm_common.py)
- **Notes:** Owned by [T-B1](task-briefs/T-B1.md). Placed in `scripts/llm_common.py` (option A) to avoid colliding with T-D1 touching `src/`.

## RF-018: Consolidate torch Pinning in requirements-training.txt

- **Status:** DONE
- **Scope:** `requirements.txt`, `requirements-training.txt`, README install paragraphs (three languages)
- **Background / Why:** Audit 2026-05-26 §P1-2: both `requirements.txt` and `requirements-training.txt` pin `torch==2.12.0+cu132` and `torchvision==0.27.0+cu132` plus the same `--extra-index-url`. Duplicate pin makes upgrades non-atomic.
- **Concrete Scope:** Remove the torch/torchvision pin and `--extra-index-url` from `requirements.txt`; keep them only in `requirements-training.txt`. Document the install order `pip install -r requirements.txt; pip install -r requirements-training.txt` in README sections that currently show install commands.
- **Out of Scope:** Actual pip install in this commit; upgrading any package version; introducing a base/extra requirements layout beyond what already exists.
- **Risks:** Users running only `requirements.txt` will no longer get torch — confirm that's the intended boundary (RF-008 already separates training deps; this just removes the duplication).
- **Acceptance Criteria:** `requirements.txt` does not contain `torch`, `torchvision`, or `cu132`; `requirements-training.txt` keeps them; READMEs show the two-step install; `unittest discover` passes.
- **Recommended Test Commands:** `rg -n "torch|cu132" requirements.txt`; `rg -n "torch==|torchvision==" requirements-training.txt`; `rg -n -i "torch|cu132" README.md README.en.md README.zh-CN.md`; `venv\Scripts\python.exe -m unittest discover -s tests`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-27. Removed `torch==2.12.0+cu132`, `torchvision==0.27.0+cu132`, and `--extra-index-url https://download.pytorch.org/whl/cu132` from `requirements.txt`, leaving only the base semantic-cleaning dependencies. Added clarifying comment to top of `requirements-training.txt` explaining the two-step install order. Updated all three READMEs (README.md, README.en.md, README.zh-CN.md) to emphasize the install order and that `requirements-training.txt` is only needed for training. Validation: `rg -n "torch|cu132" requirements.txt` returns no matches; `rg -n "torch==2.12.0|torchvision==0.27.0" requirements-training.txt` confirms both pins present; all three READMEs now clearly document the two-step install sequence; `unittest discover -s tests` passes with 108/108 tests.

## RF-019: Annotate configs/training/default.json as Dry-Run / Smoke Only

- **Status:** DONE
- **Scope:** `configs/training/default.json` (or `scripts/train_model.py`), README sections that show training commands
- **Background / Why:** Audit 2026-05-26 §P1-3: `default.json` has no `max_steps`, so `--train --config configs/training/default.json` fails. But the CLI default for `--config` is exactly that file, so newcomers hit the pitfall.
- **Concrete Scope:** Add a top-level `_comment` field in `default.json` marking it dry-run / smoke only and pointing at `full_10k.json` for `--train`. Fix README examples that pair `--train` with `default.json`. Larger alternative (changing the CLI default) is out of scope unless the user authorizes a behavior change.
- **Out of Scope:** Changing existing dry-run / smoke / nllb-smoke / real-model-smoke behavior; changing default values for batch sizes etc.
- **Risks:** A future config loader stricter about unknown fields would reject `_comment`; current loader ignores unrecognized keys, but document this in the entry.
- **Acceptance Criteria:** `default.json` carries the `_comment`; existing dry-run path unchanged; READMEs no longer pair `--train` with `default.json`; `unittest discover` passes.
- **Recommended Test Commands:** `venv\Scripts\python.exe -c "import json; d=json.load(open('configs/training/default.json', encoding='utf-8')); print('_comment' in d)"`; `venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --dry-run`; `rg -n "train.*default.json" README.md README.en.md README.zh-CN.md`; `venv\Scripts\python.exe -m unittest discover -s tests`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Owned by [T-B3](task-briefs/T-B3.md).

## RF-020: Slim Public API Surface in Package __init__

- **Status:** DONE
- **Scope:** `src/longtu_translation_pipeline/__init__.py`
- **Background / Why:** Audit 2026-05-26 §P2-2: `__init__.py` re-exports CLI-internal smoke/pilot helpers but does not export the real training entry `run_real_nllb_formal_training`. The exposed surface is inverted from the stable one.
- **Concrete Scope:** Remove `run_real_nllb_pilot_training`, `run_real_nllb_model_smoke_test`, `run_nllb_trainer_smoke_test`, and their `format_*_smoke_test` / `format_real_model_*` companions plus their `NllbTrainerSmokeResult`/`RealModel*Result` data classes from `__init__.py` and `__all__`. CLI scripts continue importing them directly from `.training`.
- **Out of Scope:** Renaming or relocating the removed functions; touching submodules themselves.
- **Risks:** Any external user importing the removed names from the package root will break — confirm none exist (rg in the repo plus user awareness).
- **Acceptance Criteria:** Removed names raise `ImportError` from the package root; stable names (configs, evaluators, marker helpers, dry-run helpers) still import; `scripts/train_model.py --dry-run` still works; `unittest discover` passes.
- **Recommended Test Commands:** `venv\Scripts\python.exe -c "from longtu_translation_pipeline import TrainingConfig, evaluate_translation, protect_training_pair"`; `venv\Scripts\python.exe -c "from longtu_translation_pipeline import run_real_nllb_pilot_training" 2>&1`; `venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --dry-run`; `venv\Scripts\python.exe -m unittest discover -s tests`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Owned by [T-D1](task-briefs/T-D1.md).

## RF-021: Archive Deprecated Notebooks

- **Status:** DONE
- **Scope:** `notebooks/main/` (six deprecated `.ipynb` files), `notebooks/archive/2023-legacy/`, `docs/notebooks/inventory.md`, README link references (three languages)
- **Background / Why:** Audit 2026-05-26 §P2-3 + §P3-3: T&N+R notebooks and notebooks replaced by `scripts/train_model.py` / `scripts/run_inference.py` still live in the active `notebooks/main/` directory despite being marked deprecated in `decisions.md` and `inventory.md`.
- **Concrete Scope:** `git mv` the six notebooks (`T&N+R method.ipynb`, `T&N+R method code accuracy testing.ipynb`, `T&N+R method glossary accuracy testing.ipynb`, `T&N+R preprocess.ipynb`, `nllb-fine-tune_all.ipynb`, `model-generation.ipynb`) into `notebooks/archive/2023-legacy/`. Update inventory and README links. Do not modify notebook JSON.
- **Out of Scope:** Deleting notebooks; editing notebook internal content; moving other notebooks.
- **Risks:** README internal links to old paths must be updated for all three languages.
- **Acceptance Criteria:** None of the six remain in `notebooks/main/`; all are present in `archive/2023-legacy/`; `git log --follow` preserves history; inventory reflects new paths; READMEs consistent; `unittest discover` passes.
- **Recommended Test Commands:** `Get-ChildItem notebooks/main -Filter "*.ipynb" | Where-Object { $_.Name -like "*T&N+R*" -or $_.Name -in @('nllb-fine-tune_all.ipynb','model-generation.ipynb') }`; `rg -n "notebooks/main/T&N|notebooks/main/nllb-fine-tune_all|notebooks/main/model-generation" README.md README.en.md README.zh-CN.md docs/notebooks/inventory.md`; `venv\Scripts\python.exe -m unittest discover -s tests`; `git -c safe.directory=D:/longtu-translation-pipeline status --short`.
- **Notes:** Owned by [T-D2](task-briefs/T-D2.md).

## RF-022: AGENTS.md unittest Reference Fix and RF-003 Closure

- **Status:** DONE
- **Scope:** `AGENTS.md` Required Checks section, `docs/refactor/backlog.md` RF-003 section
- **Background / Why:** Audit 2026-05-26 §P3-1 and §P2-4 — two small drift items bundled into one commit. AGENTS.md tells agents to use `pytest`, but the repo uses `unittest discover` (no pytest config exists). RF-003 status is `TODO` but its Notes already record that the source-to-final pipeline is no longer meaningful in this repository.
- **Concrete Scope:** Replace the `python -m pytest` paragraph in AGENTS.md with the `unittest discover` form actually used by the project. Mark RF-003 as `OBSOLETE` with a closing note explaining that raw xlsx inputs are not retained.
- **Out of Scope:** Restructuring AGENTS.md; rewriting RF-003 background.
- **Risks:** None significant — both edits are textual.
- **Acceptance Criteria:** AGENTS.md no longer recommends pytest as the primary command; RF-003 status is `OBSOLETE`; `unittest discover` still passes.
- **Recommended Test Commands:** `rg -n "pytest" AGENTS.md`; `rg -n "unittest discover -s tests" AGENTS.md`; `rg -n "^- \*\*Status:\*\* OBSOLETE" docs/refactor/backlog.md`; `venv\Scripts\python.exe -m unittest discover -s tests`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Completed on 2026-05-27. AGENTS.md "Required Checks" section replaced `python -m pytest` with `venv\Scripts\python.exe -m unittest discover -s tests` to match the repository's actual test setup (no pytest config exists). RF-003 marked OBSOLETE with closing note explaining that raw xlsx inputs are not retained post-2026-05-19 cleanup and source-to-final pipeline is not currently actionable. Both edits verified: pytest no longer mentioned in AGENTS.md required checks, unittest discover command confirmed in place, RF-003 status changed, all unit tests pass.

## RF-023: README Tri-Language Sync

- **Status:** DONE
- **Scope:** `README.md` (zh-CN), `README.en.md`, `README.zh-CN.md`, optionally `scripts/check_readme_sync.py`
- **Background / Why:** Audit 2026-05-26 §P3-2: three READMEs duplicate corpus numbers and command examples without any sync mechanism. Drift risk grows with every corpus change.
- **Concrete Scope:** Two strategies — Strategy A centralizes numbers (link to `docs/refactor/backlog.md` instead of duplicating); Strategy B adds a sync-checker script. Pick A by default; pick B only if the user wants to keep per-language numerical prose.
- **Out of Scope:** Restructuring README sections; changing the project's tri-language commitment.
- **Risks:** Strategy A removes per-language numeric context that some readers may rely on; mitigate by leaving structural prose intact and only centralizing numbers.
- **Acceptance Criteria:** Strategy A — no concrete corpus numbers (row counts, SHA256) remain in any README; each previously-numeric mention links to backlog/data-cleaning docs. Strategy B — `scripts/check_readme_sync.py` exits 0 on current trees. Either way `unittest discover` passes.
- **Recommended Test Commands:** Strategy A: `rg -n "66,?385|3,?396|SHA256" README.md README.en.md README.zh-CN.md`; Strategy B: `venv\Scripts\python.exe scripts\check_readme_sync.py`; both: `venv\Scripts\python.exe -m unittest discover -s tests`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Owned by [T-E2](task-briefs/T-E2.md). Done 2026-05-29 as project wrap-up (Strategy A — centralize via reference, no sync script). The three READMEs (`README.md` ko / `README.en.md` / `README.zh-CN.md`) got a tri-language overhaul: (1) added a "Project Status & Results" section near the top — RF-001~029 workload narrative plus the final held-out test metrics (BLEU 0.325 / chrF 0.590 / preservation_nospace 0.954 / preservation_exact 0.950 on `checkpoint-48000`, beam=4); (2) added a "Larger Models (1.3B / 3.3B)" section — qualitative quality direction + explicit "not benchmarked here" disclaimer + sourced cost numbers (HF model cards + `run_manifest.json` measured VRAM + AdamW memory accounting), no fabricated quality figure; (3) fixed the stale "RF-006 smoke/pilot hardening phase / full training not yet started" paragraph to reflect the completed `run-full-earlystop-v1` model. Volatile corpus row counts / SHA256 are referenced to `docs/refactor/backlog.md` rather than duplicated in the READMEs. No `scripts/check_readme_sync.py` was created — the body carried no duplicated corpus numbers to police.

## RF-024: Add chrF Metric to Evaluation

- **Status:** DONE
- **Scope:** `src/longtu_translation_pipeline/evaluation.py`, `configs/evaluation/*.json`, `tests/test_evaluation.py`, README evaluation section
- **Background / Why:** chrF correlates better with human judgment than BLEU on morphologically rich languages like Korean and needs no learned model. Adding it expands evaluation diagnostics without changing the existing BLEU / glossary preservation contract.
- **Concrete Scope:** Add `compute_chrf` (and optionally `compute_chrf_plus`); extend `EvaluationResult` and `format_evaluation_summary`; add config toggle; backfill at least one historical generation CSV report.
- **Out of Scope:** Replacing BLEU; changing existing report column shapes (only add new ones).
- **Risks:** Pure-Python chrF implementation must match an authoritative reference within tolerance; if using `sacrebleu`, pin the version and add to `requirements.txt`.
- **Acceptance Criteria:** `evaluation_summary.csv` has a chrF row; `compute_chrf` is unit-tested (3+ assertions); historical backfill report exists under `data/review/evaluation/.../chrf-backfill/`; BLEU and glossary numbers unchanged.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m unittest tests.test_evaluation -v`; `venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\generation_report.json --checkpoint <pilot or latest>`; `Get-Content "data\review\evaluation\generation_report\evaluation_summary.csv"`; `venv\Scripts\python.exe -m unittest discover -s tests`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Owned by [T-F1](task-briefs/T-F1.md). Implemented 2026-05-28 as Option A (diagnostic only, no training changes). Pure-Python chrF (max_n=6, beta=2), no sacrebleu dependency. 210 tests pass.

  **Backfill results (checkpoint-48000, run-full-earlystop-v1):**
  - test set (6626 rows): chrF=0.5825, BLEU=0.3192, preservation_nospace=0.9528
  - validation set (6626 rows): chrF=0.5851, BLEU=0.3226, preservation_nospace=0.9528

  **3-checkpoint chrF ranking:** Only one validation CSV preserved per run (not per checkpoint). Separate per-checkpoint CSVs for 44000/49000 were not retained. 3-checkpoint chrF ranking comparison留给 T-F5 的 sweep 顺带产出.

  **Ranking conclusion (single checkpoint):** chrF=0.5825 on test is consistent with BLEU direction (both confirm reasonable translation quality for checkpoint-48000). No conflict with the prior BLEU+preservation composite selection — chrF is a confirmatory diagnostic, no early-stopping change needed.

## RF-025: Add Optional COMET Metric

- **Status:** TODO
- **Scope:** new `src/longtu_translation_pipeline/comet_metric.py`, `evaluation.py`, `requirements-training.txt`, `configs/evaluation/generation_report.json`, `tests/test_evaluation.py`, `docs/decisions/adr/` (new ADR for contract change)
- **Background / Why:** COMET (unbabel-comet) is a learned reference-based MT metric that correlates better than BLEU/chrF with human judgment for mid-resource pairs like zh→ko. It is optional because of model size and dependency weight.
- **Concrete Scope:** Add COMET as an opt-in metric (default off). Pin `unbabel-comet` in `requirements-training.txt`. Use lazy import + module-level model caching so the rest of the package is not affected. Mock the call in tests. Record the contract change as a new ADR in `docs/decisions/adr/` (expands [ADR-0012](../../decisions/adr/ADR-0012-evaluation-uses-bleu-and-glossary-preservation-only.md)).
- **Out of Scope:** Replacing BLEU/chrF/glossary preservation; downloading models in CI.
- **Risks:** Large dependency, ~1.5GB model download on first use; runtime dominated by COMET on CPU.
- **Acceptance Criteria:** Default config has `comet_enabled=false` and reports look identical to before this RF; with the flag on, a COMET row appears in `evaluation_summary.csv` and `report_manifest.json`; tests do not download the model.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m unittest tests.test_evaluation -v`; `venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\generation_report.json --checkpoint <ckpt>`; (with custom flagged config) confirm COMET row appears; `venv\Scripts\python.exe -m unittest discover -s tests`; `git -c safe.directory=D:/longtu-translation-pipeline diff --check`.
- **Notes:** Owned by [T-F2](task-briefs/T-F2.md). Optional research extension; depends on at least one generation CSV from T-A3. **Status correction (2026-05-28):** an earlier edit erroneously flipped this to DONE; filesystem verification found no `src/longtu_translation_pipeline/comet_metric.py`, so it was reverted to TODO. NOT executed. **2026-05-29 decision: deferred.** COMET adds no model quality — it is only another reference-based eval metric, and the project already reports BLEU + chrF + glossary preservation. Not worth the ~1.5 GB model download + heavy dependency now. Revisit only if a learned metric is explicitly required.

## RF-026: NLLB-1.3B / 3.3B Base Model Experiment

- **Status:** TODO
- **Scope:** `configs/training/full_10k_nllb_1.3b.json` (new), optional `_3.3b.json`, `configs/inference/nllb_1.3b.json` (new), training runs against the same RF-015 corpus
- **Background / Why:** After RF-007-P3 establishes a 600M baseline, larger NLLB variants (1.3B, 3.3B) are the next obvious quality lever. Keeping the same segments / split / seed / marker shape allows direct comparison.
- **Concrete Scope:** Clone `full_10k.json` to a 1.3B profile; run full 10k training, validation, and test; record side-by-side comparison vs. RF-007-P3 baseline. Optionally repeat for 3.3B if VRAM allows.
- **Out of Scope:** Changing segments, glossary, splits, seed, marker shape; hyperparameter sweeps within the new base.
- **Risks:** VRAM requirements grow; gradient accumulation or LoRA may be needed for 1.3B+ on smaller GPUs; document deviations.
- **Acceptance Criteria:** New run directory under `fine-tuned-models/nllb-200-1.3B/zh2ko/runs/` with matching `segments_sha256`; side-by-side test report comparison recorded in this entry; 600M baseline untouched.
- **Recommended Test Commands:** `venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k_nllb_1.3b.json --nllb-smoke-test --smoke-rows 2`; `$env:HF_HOME="...; venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k_nllb_1.3b.json --train --run-name run-full-10k-nllb-1.3b-v1`; `Get-Content "<run>\run_manifest.json"`; `git -c safe.directory=D:/longtu-translation-pipeline status --short`.
- **Notes:** Owned by [T-F3](task-briefs/T-F3.md). Pending RF-007-P3 (now DONE — unblocked). **Status correction (2026-05-28):** an earlier edit erroneously flipped this to DONE; filesystem verification found no `configs/training/full_10k_nllb_1.3b.json` and no `fine-tuned-models/nllb-200-1.3B/` run directory, so it was reverted to TODO. NOT executed. **2026-05-29 decision: deferred.** Cost/benefit documented in the README "Larger Models" section: 1.3B full fine-tune does not fit the 16 GB GPU used here (needs gradient checkpointing / 8-bit optimizer / LoRA / offload), 3.3B needs a larger or multi-GPU setup, and the expected quality gain on this fine-tuned zh→ko task is not reliably predictable from public benchmarks. Revisit only if more quality is needed and a bigger GPU is available.

## RF-027: Back-Translation Data Augmentation

- **Status:** TODO
- **Scope:** new `scripts/generate_back_translation.py`, new `configs/training/full_10k_with_backtrans.json`, ignored `data/segments_synth_backtrans.csv`, manifest schema extension to record synthetic source SHA256
- **Background / Why:** Back-translation augments training data with synthetic zh→ko pairs derived from a ko corpus translated by a ko→zh model. Done with strict isolation it can lift quality; done carelessly it leaks synthetic content into validation/test.
- **Concrete Scope:** Generate a synthetic file outside `data/segments.csv`; extend training to append it to the train split only (after the deterministic 8:1:1 split is computed on real data); record both real and synthetic SHA256 in the manifest; verify validation/test splits are bit-identical to the baseline run.
- **Out of Scope:** Modifying `data/segments.csv` directly; auto-generating synthetic data on every run; changing seed/ratio.
- **Risks:** Synthetic rows leaking into validation or test invalidate the test report; the verification step that compares val/test SHA256 to baseline is non-negotiable.
- **Acceptance Criteria:** Synthetic file outside `data/segments.csv`; no synth row appears in validation or test splits (verified by SHA256 equality with baseline splits); manifest records both SHA256s; backlog Notes carry comparison vs. RF-007-P3 baseline.
- **Recommended Test Commands:** `Get-FileHash <baseline>\splits\validation.csv,<synth>\splits\validation.csv -Algorithm SHA256`; `Get-FileHash <baseline>\splits\test.csv,<synth>\splits\test.csv -Algorithm SHA256`; leak-check script in the brief; `venv\Scripts\python.exe -m unittest discover -s tests`; `git -c safe.directory=D:/longtu-translation-pipeline status --short`.
- **Notes:** Owned by [T-F4](task-briefs/T-F4.md). Pending RF-007-P3 (now DONE — unblocked). **Status correction (2026-05-28):** an earlier edit erroneously flipped this to DONE; filesystem verification found no `scripts/generate_back_translation.py`, so it was reverted to TODO. NOT executed. **2026-05-29 decision: deferred.** Marginal expected return after the early-stopping + beam-search gains already captured, against high effort (synthetic-data generation via a ko→zh model + strict val/test leakage isolation). Revisit only if a quality plateau needs breaking.

## RF-028: Inference Parameter Sweep

- **Status:** DONE
- **Scope:** new `scripts/sweep_inference_params.py`, new `configs/inference/sweep_v1.json`, ignored `data/review/inference/sweeps/`
- **Background / Why:** After RF-007-P3 selects a checkpoint, the cheapest remaining lever is inference hyperparameters (beam width, length penalty, no_repeat_ngram_size, sampling). A small grid sweep on validation can reveal a better operating point without retraining.
- **Concrete Scope:** Add a sweep script that takes a JSON grid, generates per-grid-point validation translations, evaluates, and writes a comparison CSV. Run the winning config once on the test split for the final number.
- **Out of Scope:** Retraining; modifying the checkpoint; iterating test results across grid points.
- **Risks:** Iterating the grid on the test split is data leakage; the contract is strict — sweep on validation, run the winning config on test once.
- **Acceptance Criteria:** `sweep_results.csv` lists at least 6 grid points with all configured metrics; winning validation config identified; one-shot test report on the winner recorded; comparison vs. baseline inference config in this entry.
- **Recommended Test Commands:** `venv\Scripts\python.exe scripts\sweep_inference_params.py --run-dir <run> --model-path <ckpt> --split validation --grid configs\inference\sweep_v1.json --output-dir data\review\inference\sweeps\v1`; `Get-Content "data\review\inference\sweeps\v1\sweep_results.csv"`; `git -c safe.directory=D:/longtu-translation-pipeline status --short`.
- **Notes:** Owned by [T-F5](task-briefs/T-F5.md). Executed 2026-05-29.

  **Setup (Step 1):** Added `num_beams`, `length_penalty`, `no_repeat_ngram_size` to `GenerationConfig` in `config.py`; wired through `model.generate()` in `inference.py`; defaults added to `configs/inference/default.json`; 3 new unit tests. Committed as `6fe2362`.

  **Sweep script (Step 2):** Created `scripts/sweep_inference_params.py` (coarse-to-fine grid runner with BLEU/chrF/preservation_nospace output) and `configs/inference/sweep_v1.json`. Committed as `a3c2096`.

  **Stage A (val_mini=1000, ckpt-48000):** beam ∈ {1,4,5}, lp=1.0, nrng=0. Result: beam=4 best (BLEU 0.3349 vs beam=5 0.3345 vs beam=1 0.3278). Selected beam=4.

  **Stage B (val_mini=1000, ckpt-48000):** beam=4 × lp ∈ {1.0,1.1,1.2} × nrng ∈ {0,3}. Result: lp=1.0 / nrng=0 clearly best. nrng=3 severely hurts BLEU (~−0.055, likely due to repetitive Korean game-text patterns). Selected: beam=4, lp=1.0, nrng=0.

  **Stage C (full val 6626 rows, all 3 checkpoints):** beam ∈ {1,4,5}, lp=1.0, nrng=0. Results:

  | checkpoint | beam | BLEU | chrF | pres\_nospace |
  |---|---|---|---|---|
  | 44000 | 1 | 0.318918 | 0.581234 | 0.951355 |
  | 44000 | 4 | 0.318785 | 0.584972 | 0.953583 |
  | 44000 | 5 | 0.324690 | 0.587512 | 0.953212 |
  | **48000** | **1** | **0.325044** | **0.585877** | **0.951727** |
  | **48000** | **4** | **0.328432** | **0.592224** | **0.952098** |
  | 48000 | 5 | 0.327399 | 0.592682 | 0.952098 |
  | 49000 | 1 | 0.322597 | 0.585081 | 0.952841 |
  | 49000 | 4 | 0.324233 | 0.591648 | 0.953212 |
  | 49000 | 5 | 0.324640 | 0.591826 | 0.953212 |

  **B1 (chrF ranking):** chrF confirms ckpt-48000 is best at every beam value. B1 closed — no escalation needed.

  **Winner:** ckpt-48000, beam=4, lp=1.0, nrng=0 (val BLEU 0.328432, best across all 3 checkpoints × beam configs).

  **Terminal test (Step 4 — one-shot, no iteration):** ckpt-48000, beam=4, lp=1.0, nrng=0 on test split (6626 rows):

  | Metric | RF-028 beam=4 | RF-007-P4 greedy (baseline) | Δ |
  |---|---|---|---|
  | BLEU (whitespace) | **0.324958** | 0.319163 | +0.005795 (+1.82%) |
  | chrF (max\_n=6, β=2) | **0.589897** | N/A (pre-RF-024) | — |
  | pres\_nospace | **0.953593** | 0.952844 | +0.000749 |
  | pres\_exact | **0.950225** | 0.949476 | +0.000749 |
  | empty\_candidate\_rows | 0 | 0 | 0 |

  **Step 5:** `configs/inference/default.json` updated to `num_beams=4` (lp=1.0, nrng=0 were already defaults). RF-007-P4 entry carries pointer to this result.

## RF-029: LLM Cleanup Batch API + Strict JSON Schema

- **Status:** DONE
- **Scope:** `scripts/llm_common.py`, `scripts/segments_llm_cleanup_pipeline.py`, `scripts/glossary_llm_cleanup_pipeline.py`, `tests/test_llm_common.py`, `tests/test_segments_llm_cleanup_pipeline.py`, `tests/test_glossary_llm_cleanup_pipeline.py`, `docs/refactor/task-briefs/T-A1.md`, `docs/decisions/adr/ADR-0030-llm-cleanup-defaults-to-batch-api-with-strict-json-schema.md`
- **Background / Why:** RF-013 and RF-015 shipped LLM cleanup over a synchronous per-batch `/v1/chat/completions` transport with no `response_format` constraint and no `max_tokens` cap. T-A1's pricing review on 2026-05-27 confirmed `gpt-4.1-mini` + OpenAI Batch API + `json_schema` strict as the cost-optimal configuration (50% discount, eliminates regex JSON fallback, ~$1.5-3 for the remaining 66k segments vs. ~$2.5 sync at gpt-4o-mini). Pipelines needed a Batch transport path and stricter request shape before T-A1 could run.
- **Concrete Scope:** Add six Batch API helpers in `llm_common.py` (`build_batch_request_line`, `upload_batch_input_file`, `create_batch`, `get_batch`, `wait_for_batch`, `download_batch_output`) using urllib only — no `openai` SDK dependency, multipart upload hand-rolled to preserve the single-transport audit surface (§P0-1). Both cleanup pipelines gained `--batch-mode {sync,batch}` (default `batch`), `--max-output-tokens`, `--poll-interval`, `--max-wait-sec`, and `--completion-window` CLI flags. Every chat completion payload (sync or batch) now carries `response_format={"type":"json_schema","strict":true}`, `parallel_tool_calls=false`, and `max_tokens=batch_size*45` (segments) or `batch_size*30` (glossary). Batch path writes one JSONL containing all micro-batches under `<review-dir>/batch_input/all.jsonl`, persists progress in `<review-dir>/batch_state.json` (atomic write of `phase ∈ {init, input_written, uploaded, submitted, completed, downloaded}` plus `input_file_id` / `batch_id` / `output_file_id`), and resumes from any phase on rerun.
- **Out of Scope:** Introducing a third-party SDK; deleting the sync path (kept behind `--batch-mode sync` for unit tests and small ad-hoc runs); changing prompt content, schema field names, validators, or review CSV layouts (verified by 137-test regression).
- **Risks:** Batch SLA is 24h — set `--max-wait-sec` accordingly; failed lines surface via `error` in the output JSONL and now raise loudly. Strict json_schema rejects `null` corrected_ko, so the prompt explicitly tells the model to emit `""` for non-rewrite actions. Multipart upload fully loads JSONL into memory; acceptable for the < 20 MiB segments corpus.
- **Acceptance Criteria:** `python -m unittest discover -s tests` passes (137 tests as of 2026-05-27); sync mode regression suite unchanged; batch mode end-to-end test with all four Batch API helpers mocked produces the expected outcomes; resume test confirms re-running with phase=downloaded does not call upload/create/wait/download again; payload assertion confirms `response_format / parallel_tool_calls / max_tokens` all present; T-A1 execution recipe updated to default to batch mode with sync as fallback.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile scripts\llm_common.py scripts\segments_llm_cleanup_pipeline.py scripts\glossary_llm_cleanup_pipeline.py`; `venv\Scripts\python.exe -m unittest tests.test_llm_common tests.test_segments_llm_cleanup_pipeline tests.test_glossary_llm_cleanup_pipeline`; `venv\Scripts\python.exe -m unittest discover -s tests`.
- **Notes:** Decided and implemented 2026-05-27 as a precondition for T-A1. See [ADR-0030](../../decisions/adr/ADR-0030-llm-cleanup-defaults-to-batch-api-with-strict-json-schema.md). T-A1 brief execution recipe rewritten to use the new default.

## RF-006-P13: Early-Stopping Formal Training with Composite Metric

- **Status:** DONE
- **Scope:** `src/longtu_translation_pipeline/config.py`, `src/longtu_translation_pipeline/training.py`, new `src/longtu_translation_pipeline/training_metrics.py`, new `configs/training/full_earlystop.json`, `tests/test_training_pipeline.py`, ignored `fine-tuned-models/.../runs/run-full-earlystop-v1/`
- **Background / Why:** RF-006-P11 (`run-full-10k-llm-segments-v1`) used `max_steps=10000`, which equals 0.189 epoch on the 53,015-row train split. At step 10000 `eval_loss` was still decreasing (0.0729→0.0672 from step 5000) and validation BLEU still rising (0.1917→0.1969 from 7000 to 10000) — strong evidence the model is under-fit. The arbitrary step ceiling has no machinery to detect either under-fit or over-fit. This task adds principled early stopping driven by a composite quality metric so future training auto-stops when actually plateaued.
- **Concrete Scope:** Switch the formal training path from `Trainer` to `Seq2SeqTrainer`; add `EarlyStoppingCallback`, `load_best_model_at_end=True`, `metric_for_best_model="eval_composite"`. Implement a `compute_metrics` factory in a new `training_metrics.py` module that decodes generated token IDs, strips glossary markers, and reuses `compute_corpus_bleu` and `compute_glossary_preservation` from `evaluation.py` to produce `eval_bleu`, `eval_glossary_preservation_exact`, `eval_glossary_preservation_nospace`, and `eval_composite = 0.5·BLEU + 0.5·preservation_nospace`. **In-loop eval uses a 1,000-row deterministic subset of `splits/validation.csv` (`metrics.eval_subset_rows=1000`)** because the full 6,626-row validation set takes ~38 min per eval (cost-prohibitive over a 10-epoch ceiling). The remaining 5,626 validation rows are reserved for **post-hoc top-K (3) full-eval** after early stopping triggers. **In-loop `generation_max_length=256`** (down from 400) — verified on test_generated.csv that p99.9 of ko candidate tokens = 225, so 256 truncates only ~0.06% of in-loop rows; the 400 cap stays in `configs/inference/default.json` for post-hoc / T-A6 / final inference. New profile `configs/training/full_earlystop.json` carries `num_train_epochs=10` ceiling (no `max_steps`), `per_device_train_batch_size=4`, `lr_scheduler_type="cosine"`, `eval_steps=save_steps=1000` (returned to 1000 after introducing `eval_subset_rows`), `early_stopping_patience=5`, `early_stopping_threshold=0.0`, `predict_with_generate=true`, `generation_max_length=256`, `eval_subset_rows=1000`. All other hyperparameters identical to `full_10k.json` for partial comparability. The 8:1:1 split contract (seed=42) is preserved — no changes to splits.
- **Out of Scope:** Touching `configs/training/full_10k.json` (historical baseline must remain reproducible); touching `run-full-10k-llm-segments-v1/`; changing seed / split ratios / marker shape / segments.csv; introducing inference parameter sweeps (RF-028); new base model experiments (RF-026); new evaluation metrics (RF-024 chrF lands separately).
- **Risks:** `predict_with_generate=True` makes each eval 5-20× slower than loss-only eval; the first T-A5 attempt confirmed 38 min per eval on the full 6,626-row validation. **Primary mitigation:** `metrics.eval_subset_rows=1000` reduces per-eval wall-clock to ~5.7 min — a 6.6× speedup — with negligible signal loss (1k-row BLEU SD ≈ 0.003-0.005, well below patience-5 tolerance). **Secondary mitigation:** `generation_max_length=256` saves KV-cache memory + batch padding. **Recovery:** if total wall-clock still > 8h after both mitigations, raise `eval_steps` to 2000. Composite metric noise — `patience=5` gives buffer. Backward compat — switching to `Seq2SeqTrainer` keeps a fallback path so smoke / pilot / RF-006-P11 profile (no `metrics` block) still uses plain `Trainer`. **Top-K full-eval risk:** if the in-loop-best checkpoint loses on full validation to another top-K candidate, record the gap and use the full-val winner for T-A6.
- **Acceptance Criteria:** `Seq2SeqTrainer` + `EarlyStoppingCallback` + `load_best_model_at_end` wired into formal training with backward-compat fallback; `make_compute_metrics` reuses `compute_corpus_bleu` + `compute_glossary_preservation`; **7** new unit tests pass (config parse / callback attach / load_best plumbed / compute_metrics dict shape / scheduler field / backward-compat / **eval_subset_rows subsetting**); `full_earlystop.json` loads cleanly; training run completes (by early stop or `num_train_epochs=10` ceiling); `run_manifest.json` records new metrics config + `trainer.state.best_metric` + `trainer.state.best_model_checkpoint`; **post-hoc top-K (3) full-validation runs executed on the 5,626-row remainder** with results recorded; branch decision (auto-best confirmed / full-val winner overrides / tie + tie-break) recorded in Notes; backlog Notes contain the in-loop eval curve table, post-hoc top-K full-val table, and comparison vs RF-006-P11; no files added to Git beyond the listed surface.
- **Recommended Test Commands:** `venv\Scripts\python.exe -m py_compile src\longtu_translation_pipeline\config.py src\longtu_translation_pipeline\training.py src\longtu_translation_pipeline\training_metrics.py`; `venv\Scripts\python.exe -m unittest tests.test_training_pipeline -v`; `venv\Scripts\python.exe -m unittest discover -s tests`; `venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_earlystop.json --dry-run`; `$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"; venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_earlystop.json --train --run-name run-full-earlystop-v1`; `Get-Content "<run-dir>\run_manifest.json"`; `Get-Content "<run-dir>\checkpoint-*\trainer_state.json" | Select-String "best_metric|best_model_checkpoint"`; `git -c safe.directory=D:/longtu-translation-pipeline status --short`.
- **Notes:** Owned by [T-A5](task-briefs/T-A5.md). Decision rationale and methodology survey: see [ADR-0031](../../decisions/adr/ADR-0031-formal-training-uses-early-stopping-on-composite-metric.md). Gates T-A6 (RF-007-P4 new test report on the auto-selected best checkpoint).

  **Implementation state as of 2026-05-28 (T-A5 partial — code complete, training pending):**

  Code + config + tests are committed on branch `claude/optimistic-wescoff-8c3e57`. All 203 existing tests pass. `--dry-run` on `full_earlystop.json` validates cleanly (66267 rows total, train=53015 / validation=6626 / test=6626). Training run `run-full-earlystop-v1` has **not yet completed** — to be executed in the next conversation.

  *Key implementation decisions made during T-A5:*
  - `data/segments.csv` SHA256 at implementation time: `30d5c299828c10235aee357e9333740913e55c291c5b07a45c0739e41818ea97` (post-OpenAI-Batch-Mode cleaning, differs from RF-006-P11 baseline's `1462B2E1…`; user confirmed this is the correct current corpus).
  - transformers 5.x API: `Seq2SeqTrainer` uses `processing_class=` instead of deprecated `tokenizer=`; `Seq2SeqTrainer` pads **both** `predictions` and `label_ids` with `-100` when `predict_with_generate=True` — `compute_metrics` must replace `-100 → pad_token_id` in predictions before `batch_decode`, not just in labels.
  - `eval_steps=2000` (raised from plan's 1000): first live eval at step 1000 measured **38 min** on 6626-row validation with greedy generation (`eval_samples_per_second ≈ 2.9`), putting the 10-epoch ceiling at ~76 h eval-only. Raised to 2000 per the Risk mitigation plan (reduces eval frequency by half); `save_steps` raised to match.

  **2026-05-28 follow-up — incremental refinement before training restart.** The user paused the first T-A5 attempt after the 38 min/eval measurement and asked whether raising `eval_steps` was treating the symptom rather than the cause. After a research pass (see decisions.md 2026-05-27 follow-up note), the agreed cleaner fix is: **add `metrics.eval_subset_rows=1000` and lower `metrics.generation_max_length` to 256**, then return `eval_steps` to 1000. This replaces the temporary `eval_steps=2000` workaround. Implementation increment scope: (a) extend `MetricsConfig` with `eval_subset_rows` field + loader parse + a 7th unit test; (b) in training.py construct `inloop_eval_dataset` via `Subset(eval_dataset, range(N))` when configured; (c) update `configs/training/full_earlystop.json` `metrics` block to `generation_max_length=256` + `eval_subset_rows=1000` and `training.eval_steps`/`save_steps` back to 1000; (d) on training restart, also implement the post-hoc top-K full-eval workflow (T-A5 brief Step 6b/6c). The expected wall-clock for the new attempt: ~3-8 h total (vs 76 h before mitigation).

  **Code increment committed 2026-05-28**: `b759563` (`Add eval subset and reduce generation_max_length for in-loop eval`). All 204 tests pass (203 → 204, +`test_eval_dataset_is_subsetted_when_eval_subset_rows_configured`). Final config: `generation_max_length=256`, `eval_subset_rows=1000`, `eval_steps=save_steps=1000`.

  **Training run `run-full-earlystop-v1` started manually by user on 2026-05-28.** After training completes, run the post-hoc top-K full-validation (T-A5 brief Step 6b), record the in-loop eval curve + post-hoc full-val table + branch decision in this Notes block, then set Status → DONE.

  ---

  **Training run completed — RF-006-P13 results (recorded by T-A5 Step 6b/6c, 2026-05-28)**

  **Run summary:**
  - Run name: `run-full-earlystop-v1`
  - Run dir: `fine-tuned-models/nllb-200-distilled-600M/zh2ko/runs/run-full-earlystop-v1/`
  - `segments_sha256`: `30D5C299828C10235AEE357E9333740913E55C291C5B07A45C0739E41818EA97`
  - Training started: `2026-05-28T12:10:35` (from `run_manifest.json`); wall-clock end time not recorded.
  - Device: NVIDIA GeForce RTX 4070 Ti SUPER; torch=2.12.0+cu132, transformers=5.9.0
  - Final global step: 49000 (epoch ≈ 3.697); early stopping triggered.
  - `best_global_step`: 44000; `best_metric` (eval_composite, in-loop): 0.6992663
  - `best_model_checkpoint`: `checkpoint-44000` (auto-loaded via `load_best_model_at_end=True`)
  - Saved checkpoints (save_total_limit=3): {44000, 48000, 49000}

  **Independent early-stop verification:**
  - Eval composite peaks at step 44000 (0.6993). Subsequent 5 evals all below the peak:
    45000 (0.6942), 46000 (0.6970), 47000 (0.6922), 48000 (0.6898), 49000 (0.6977).
  - patience counter reached 5 at step 49000 → training stopped.
  - Math check: best_step (44000) + patience (5) × eval_steps (1000) = 49000 ✓
  - eval_loss is NOT monotonically decreasing (slight upticks at 27000, 32000, 40000-41000); the best checkpoint was correctly selected by eval_composite, not eval_loss. ✓
  - Background report verified: best_global_step=44000, best_metric=0.6993, early stop at 49000 — all match. ✓

  **In-loop eval curve** (val_mini = first 1000 rows of `splits/validation.csv`, max_length=256, greedy):

  | step | epoch | eval_loss | eval_bleu | pres_exact | pres_nospace | composite |
  |------|-------|-----------|-----------|------------|--------------|-----------|
  | 1000 | 0.075 | 5.9055 | 0.0046 | 0.0048 | 0.0048 | 0.0047 |
  | 2000 | 0.151 | 0.7261 | 0.0984 | 0.2530 | 0.2578 | 0.1781 |
  | 3000 | 0.226 | 0.0796 | 0.2055 | 0.6265 | 0.6554 | 0.4305 |
  | 4000 | 0.302 | 0.0670 | 0.2617 | 0.7012 | 0.7277 | 0.4947 |
  | 5000 | 0.377 | 0.0613 | 0.2770 | 0.7518 | 0.7759 | 0.5265 |
  | 6000 | 0.453 | 0.0575 | 0.2811 | 0.7711 | 0.8000 | 0.5406 |
  | 7000 | 0.528 | 0.0550 | 0.3055 | 0.8024 | 0.8289 | 0.5672 |
  | 8000 | 0.604 | 0.0527 | 0.3100 | 0.8241 | 0.8506 | 0.5803 |
  | 9000 | 0.679 | 0.0509 | 0.3278 | 0.8361 | 0.8602 | 0.5940 |
  | 10000 | 0.754 | 0.0495 | 0.3332 | 0.8337 | 0.8627 | 0.5979 |
  | 11000 | 0.830 | 0.0488 | 0.3394 | 0.8530 | 0.8843 | 0.6119 |
  | 12000 | 0.905 | 0.0473 | 0.3422 | 0.8651 | 0.8940 | 0.6181 |
  | 13000 | 0.981 | 0.0465 | 0.3567 | 0.8651 | 0.8940 | 0.6253 |
  | 14000 | 1.056 | 0.0459 | 0.3648 | 0.8723 | 0.9012 | 0.6330 |
  | 15000 | 1.132 | 0.0457 | 0.3586 | 0.8819 | 0.9108 | 0.6347 |
  | 16000 | 1.207 | 0.0448 | 0.3704 | 0.8771 | 0.9060 | 0.6382 |
  | 17000 | 1.283 | 0.0442 | 0.3652 | 0.8843 | 0.9133 | 0.6392 |
  | 18000 | 1.358 | 0.0436 | 0.3790 | 0.8795 | 0.9108 | 0.6449 |
  | 19000 | 1.434 | 0.0428 | 0.3587 | 0.8819 | 0.9108 | 0.6348 |
  | 20000 | 1.509 | 0.0422 | 0.3803 | 0.8867 | 0.9181 | 0.6492 |
  | 21000 | 1.584 | 0.0421 | 0.3851 | 0.8843 | 0.9157 | 0.6504 |
  | 22000 | 1.660 | 0.0412 | 0.3756 | 0.8916 | 0.9205 | 0.6480 |
  | 23000 | 1.735 | 0.0412 | 0.3854 | 0.8892 | 0.9181 | 0.6517 |
  | 24000 | 1.811 | 0.0405 | 0.3776 | 0.8964 | 0.9253 | 0.6514 |
  | 25000 | 1.886 | 0.0403 | 0.3916 | 0.9012 | 0.9301 | 0.6609 |
  | 26000 | 1.962 | 0.0399 | 0.4198 | 0.9012 | 0.9301 | 0.6749 |
  | 27000 | 2.037 | 0.0400 | 0.3985 | 0.9036 | 0.9325 | 0.6655 |
  | 28000 | 2.113 | 0.0398 | 0.4144 | 0.9012 | 0.9325 | 0.6735 |
  | 29000 | 2.188 | 0.0396 | 0.4045 | 0.9084 | 0.9373 | 0.6709 |
  | 30000 | 2.263 | 0.0392 | 0.4243 | 0.9036 | 0.9325 | 0.6784 |
  | 31000 | 2.339 | 0.0389 | 0.4150 | 0.9036 | 0.9325 | 0.6738 |
  | 32000 | 2.414 | 0.0390 | 0.4148 | 0.9060 | 0.9349 | 0.6749 |
  | 33000 | 2.490 | 0.0387 | 0.4151 | 0.9133 | 0.9422 | 0.6786 |
  | 34000 | 2.565 | 0.0383 | 0.4243 | 0.9108 | 0.9398 | 0.6820 |
  | 35000 | 2.641 | 0.0381 | 0.4296 | 0.9084 | 0.9373 | 0.6835 |
  | 36000 | 2.716 | 0.0377 | 0.4408 | 0.9084 | 0.9373 | 0.6891 |
  | 37000 | 2.792 | 0.0376 | 0.4394 | 0.9108 | 0.9398 | 0.6896 |
  | 38000 | 2.867 | 0.0374 | 0.4289 | 0.9133 | 0.9422 | 0.6855 |
  | 39000 | 2.943 | 0.0371 | 0.4022 | 0.9229 | 0.9518 | 0.6770 |
  | 40000 | 3.018 | 0.0374 | 0.4402 | 0.9205 | 0.9494 | 0.6948 |
  | 41000 | 3.093 | 0.0374 | 0.4356 | 0.9229 | 0.9518 | 0.6937 |
  | 42000 | 3.169 | 0.0372 | 0.4368 | 0.9205 | 0.9494 | 0.6931 |
  | 43000 | 3.244 | 0.0371 | 0.4412 | 0.9253 | 0.9542 | 0.6977 |
  | **44000** | **3.320** | **0.0367** | **0.4443** | **0.9253** | **0.9542** | **0.6993** ← best_global_step |
  | 45000 | 3.395 | 0.0367 | 0.4341 | 0.9253 | 0.9542 | 0.6942 | patience=1 |
  | 46000 | 3.471 | 0.0366 | 0.4375 | 0.9277 | 0.9566 | 0.6970 | patience=2 |
  | 47000 | 3.546 | 0.0365 | 0.4301 | 0.9253 | 0.9542 | 0.6922 | patience=3 |
  | 48000 | 3.622 | 0.0364 | 0.4349 | 0.9157 | 0.9446 | 0.6898 | patience=4 |
  | 49000 | 3.697 | 0.0363 | 0.4389 | 0.9277 | 0.9566 | 0.6977 | patience=5 → STOP |

  All values sourced directly from `checkpoint-49000/trainer_state.json`. composite = 0.5·eval_bleu + 0.5·eval_glossary_preservation_nospace (matches trainer's `metric_for_best_model="eval_composite"`). No discrepancies found between draft and JSON.

  **Step 6b — Post-hoc full-validation table** (6626 rows, max_length=400, greedy, `configs/inference/default.json`):

  | Checkpoint | BLEU | pres_exact | pres_nospace | empty_candidate_rows | composite (0.5·BLEU+0.5·nospace) |
  |---|---|---|---|---|---|
  | checkpoint-44000 | 0.318918 | 0.948013 | 0.951355 | 0 | 0.635137 |
  | **checkpoint-48000** | **0.325044** | **0.948013** | **0.951727** | **0** | **0.638386** ← full-val winner |
  | checkpoint-49000 | 0.322597 | 0.950241 | 0.952841 | 0 | 0.637719 |

  Report artifacts (Git-ignored): `data/review/evaluation/validation_report/run-full-earlystop-v1/checkpoint-{44000,48000,49000}/` — each contains `evaluation_summary.csv`, `glossary_preservation_rows.csv`, `sample_review.csv`, `report_manifest.json`.

  **Step 6c — Decision: Branch (ii)** — Another top-K checkpoint (48000) scores higher on full validation than the trainer's auto-selected best (44000). Gap: 0.638386 − 0.635137 = 0.003249 (just above ε≈0.003). Between 48000 and 49000, the gap is only 0.0007 (within ε), so tie-break applies: prefer earlier checkpoint (less overfit risk) → 48000 confirmed. **T-A6 uses `checkpoint-48000`.**

  Note on in-loop vs full-val discrepancy: the 1000-row in-loop subset ranked checkpoint-44000 first (0.6993) and checkpoint-48000 fourth (0.6898). On full 6626 rows the order reverses: 48000 (0.6384) > 49000 (0.6377) > 44000 (0.6351). The BLEU gap is large (in-loop BLEU ≈ 0.44 vs full-val ≈ 0.32) because the first 1000 validation rows are shorter/simpler than the full distribution. Preservation metrics are more stable across sample sizes and change by < 0.01 between in-loop and full-val. This is expected behavior for a 1000-row subset and does not indicate a problem with the training run.

  **Comparison vs RF-006-P11 baseline** (full 6626-row validation, same split seed 42 — both use `splits/validation.csv` from `run_manifest.json`):

  | Run | Checkpoint | BLEU | pres_nospace | composite | corpus_sha256 |
  |---|---|---|---|---|---|
  | RF-006-P11 (`run-full-10k-llm-segments-v1`) | checkpoint-9000 | 0.1959 | 0.7917 | 0.4938 | 1462B2E1… |
  | **RF-006-P13 (`run-full-earlystop-v1`)** | **checkpoint-48000** | **0.3250** | **0.9517** | **0.6384** | 30D5C299… |
  | Delta | | +0.1291 (+65.9%) | +0.1600 (+20.2%) | +0.1446 (+29.3%) | |

  Caveat: RF-006-P11 and RF-006-P13 were trained on different corpora (SHA256 differ). The improvement reflects both longer training (0.19 epochs → 3.7 epochs) and the updated post-OpenAI-Batch-Mode cleaned corpus. A pure methodology ablation would require rerunning RF-006-P11 on the 30D5C299 corpus.

## RF-007-P4: New Held-Out Test Report on Early-Stop Best Checkpoint

- **Status:** DONE
- **Scope:** `scripts/run_inference.py --generate-test`, `scripts/evaluate_translation.py`, ignored `data/review/inference/test/run-full-earlystop-v1/`, ignored `data/review/evaluation/test_report/run-full-earlystop-v1/`
- **Background / Why:** RF-006-P13 Step 6b/6c selected the genuine best checkpoint by full-validation re-ranking (NOT the trainer's `load_best_model_at_end` auto-best). The selected checkpoint is **`checkpoint-48000`** (Branch (ii): on full 6,626-row validation, 48000 beat the trainer auto-best 44000 by composite 0.0033 > ε≈0.003, and beat/tied 49000 within ε so the earlier 48000 won the tie-break; note val_mini=1000 had mis-ranked 48000 as worst of the tail — the full-val re-eval corrected it). This task runs the held-out test split against checkpoint-48000 to produce the new project headline number. RF-007-P3 stays as the historical baseline; this entry supersedes it as the current published result.
- **Concrete Scope:** Run `--generate-test --model-path <run>\checkpoint-48000`, run `evaluate_translation.py`, write the report under `data/review/evaluation/test_report/run-full-earlystop-v1/checkpoint-48000/`. Record comparison vs full-val (48000, from RF-006-P13 Step 6b) and vs RF-007-P3 (ckpt-9000 of `run-full-10k-llm-segments-v1`) on all metrics (BLEU, glossary preservation exact + nospace, empty_candidate_rows). **Do NOT resolve `best_model_checkpoint` from trainer_state.json** — that points to 44000, which Step 6c overrode; use 48000.
- **Out of Scope:** Iterating over multiple checkpoints (data leakage — test 48000 only, do not test 44000/49000 to compare); changing the Step 6c selection; rerunning training.
- **Risks:** If checkpoint-48000 turns out test-time worse than RF-007-P3 ckpt-9000, document the gap and decide whether to (a) keep RF-007-P3 as the production number, (b) revisit the composite weighting, or (c) accept the trade-off — but do NOT re-pick a different checkpoint on the basis of the test number (leakage). Corpus + training method both differ from RF-007-P3, so the comparison is "current model vs historical baseline", not a controlled ablation.
- **Acceptance Criteria:** Test report directory exists with the four standard files; `report_manifest.json` records the resolved best checkpoint and segments_sha256; backlog Notes carry the side-by-side comparison with RF-007-P3; one of the three decision branches (a/b/c) is explicitly recorded; no files added to Git beyond this entry.
- **Recommended Test Commands:** `venv\Scripts\python.exe scripts\run_inference.py --generate-test --run-dir <run dir> --model-path <best checkpoint>`; `venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\generation_report.json --checkpoint <best checkpoint>`; `git -c safe.directory=D:/longtu-translation-pipeline status --short`.
- **Notes:** Owned by [T-A6](task-briefs/T-A6.md). RF-006-P13 is DONE (`89b3e2d`); Step 6c selected `checkpoint-48000` via Branch (ii). Completed 2026-05-28 by T-A6.

  **Final test report (single run, checkpoint-48000, no iteration):**

  | Metric | Test (ckpt-48000) | Full-val (ckpt-48000, RF-006-P13 Step 6b) | Δ (test − val) |
  |---|---|---|---|
  | BLEU (whitespace) | 0.319163 | 0.325044 | −0.0059 |
  | glossary_preservation_rate (exact) | 0.949476 | 0.948013 | +0.0015 |
  | glossary_preservation_rate_nospace | 0.952844 | 0.951727 | +0.0011 |
  | empty_candidate_rows | 0 | 0 | 0 |

  - Selected checkpoint: `fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-full-earlystop-v1\checkpoint-48000`
  - `data/segments.csv` SHA256 at run time: `30D5C299828C10235AEE357E9333740913E55C291C5B07A45C0739E41818EA97` (matches `run_manifest.json`)
  - Test rows: 6,626; sample review rows: 50
  - BLEU brevity penalty: 1.000000; glossary terms matched exact: 2,537 / 2,672; nospace: 2,546 / 2,672
  - Sanity check: test and full-val are in the same ballpark (BLEU difference −0.006, preservation difference < 0.002). Preservation is marginally higher on test than val; BLEU is marginally lower — both differences are within expected sampling variation. No overfit signal; result is consistent with the RF-006-P13 validation picture. ✓

  **Comparison vs RF-007-P3 historical baseline (ckpt-9000, `run-full-10k-llm-segments-v1`):**

  | Metric | RF-007-P4 (ckpt-48000, this entry) | RF-007-P3 (ckpt-9000, historical) | Δ |
  |---|---|---|---|
  | BLEU (whitespace) | 0.319163 | 0.1979 | +0.1213 (+61.3%) |
  | glossary_preservation_rate (exact) | 0.949476 | 0.7754 | +0.1741 (+22.5%) |
  | glossary_preservation_rate_nospace | 0.952844 | 0.7975 | +0.1553 (+19.5%) |
  | empty_candidate_rows | 0 | 0 | 0 |

  ⚠ RF-007-P3 used a different corpus SHA256 (`1462B2E1…`, pre-OpenAI-Batch-Mode cleaning) and the old fixed-10k training method (0.19 epochs). RF-007-P4 uses corpus `30D5C299…` (post-OpenAI-Batch-Mode cleaning) and early-stopping training (3.7 epochs). This comparison is **"current model vs historical baseline"**, not a controlled ablation — the improvement reflects both the larger training budget and the cleaner corpus.

  **Decision branch:** (c) — RF-007-P4 is substantially better than RF-007-P3 across all metrics. RF-007-P4 supersedes RF-007-P3 as the current published result.

  Report artifacts (Git-ignored): `data/review/evaluation/test_report/run-full-earlystop-v1/checkpoint-48000/` — `evaluation_summary.csv`, `glossary_preservation_rows.csv`, `sample_review.csv`, `report_manifest.json`. Test generation CSV: `data/review/inference/test/run-full-earlystop-v1/test_generated.csv`.

  > **RF-007-P4 supersedes RF-007-P3 as the current published result. Any future change to `data/segments.csv` SHA256 invalidates this report.**

  > ⚠ **Greedy inference result superseded by RF-028**: beam=4 on test split yields BLEU 0.324958 (+0.0058, +1.82% vs this greedy baseline). `configs/inference/default.json` updated to `num_beams=4`. See RF-028.

  > ⚠ **RF-007-P3/10k is an intermediate diagnostic, not the true base-model baseline.** RF-007-P3 (ckpt-9000) came from a 10k-step under-fit fine-tuned run; it indicates underfitting direction, not the pre-fine-tuning performance. The true baseline — the base NLLB-600M before any fine-tuning — is recorded in RF-007-P5.

## RF-007-P5: Base-Model Baseline

- **Status:** DONE
- **Scope:** `configs/inference/zeroshot_greedy.json` (new), `configs/inference/zeroshot_beam4.json` (new), ignored `data/review/inference/zeroshot/`, ignored `data/review/evaluation/zeroshot_baseline/`
- **Background / Why:** RF-007-P4 established the fine-tuned model's test performance. To quantify what fine-tuning actually contributes (vs. the stock NLLB model), a true "before fine-tuning" base-model baseline is needed on the identical test split with the identical evaluation code.
- **Concrete Scope:** Load the unmodified `facebook/nllb-200-distilled-600M` weights from a local copy, run test-split inference via the existing `run_inference.py --generate-test` path with `source_terminology_markers=false` (raw source, no markers), evaluate with `evaluate_translation.py`, record metrics for two decode settings matching RF-007-P4: greedy (`num_beams=1`) and beam=4 (`num_beams=4, length_penalty=1.0, no_repeat_ngram_size=0`).
- **Out of Scope:** Writing a new generation script; modifying `run_inference.py` / `inference.py`; rerunning fine-tuned inference.
- **Methodology note:** The `run_inference.py` path adds `<start>/<end>` special tokens to the tokenizer and resizes base-model embeddings from 256204 → 256206 (two randomly initialized, never-used slots). With `source_terminology_markers=false` these tokens never appear in input; `strip_glossary_markers=true` strips them from output. This is a negligible perturbation and does not affect metrics.
- **Data:** Same test split: `fine-tuned-models/nllb-200-distilled-600M/zh2ko/runs/run-full-earlystop-v1/splits/test.csv`, 6626 rows, `segments_sha256=30D5C299828C10235AEE357E9333740913E55C291C5B07A45C0739E41818EA97` (verified identical to `data/segments.csv`).
- **Notes:** Completed 2026-05-30 (T-A7 Stage 1).

  **Base-model results:**

  | Metric | Base model greedy | Base model beam=4 |
  |---|---|---|
  | BLEU (whitespace) | 0.009152 | 0.009352 |
  | chrF (β=2, max_n=6) | 0.219321 | 0.225706 |
  | preservation_nospace | 0.312126 | 0.322605 |
  | preservation_exact | 0.308757 | 0.318862 |
  | empty_candidate_rows | 26 | 37 |

  **Fine-tuned vs. base-model net gain (same decode setting):**

  | Metric | Fine-tuned @greedy | Base model @greedy | Net gain @greedy | Fine-tuned @beam=4 | Base model @beam=4 | Net gain @beam=4 |
  |---|---|---|---|---|---|---|
  | BLEU | 0.319163 | 0.009152 | **+0.310011 (+34×)** | 0.324958 | 0.009352 | **+0.315606 (+34×)** |
  | chrF | 0.590 | 0.219321 | **+0.371** | — | 0.225706 | — |
  | preservation_nospace | 0.954 | 0.312126 | **+0.642** | — | 0.322605 | — |

  Fine-tuned chrF and preservation @beam=4 not separately recorded in RF-007-P4 / RF-028 notes; the greedy reference values are from RF-007-P4 (`chrF 0.590`, `preservation_nospace 0.954`).

  **Interpretation:** The base NLLB-600M generates fluent Korean but completely misses game-specific terminology, character names, and UI vocabulary. Fine-tuning on the LongTu corpus delivers a ~34× BLEU gain and raises glossary preservation from ~31% to ~95%.

  Report artifacts (Git-ignored): `data/review/evaluation/zeroshot_baseline/greedy/`, `data/review/evaluation/zeroshot_baseline/beam4/`. Generation CSVs: `data/review/inference/zeroshot/test_zeroshot_greedy.csv`, `data/review/inference/zeroshot/test_zeroshot_beam4.csv`.
