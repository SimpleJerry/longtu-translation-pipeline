# Notebook Inventory

This document records the current notebook set, why each notebook exists, and how it should be treated during refactor work. It is intentionally an inventory first: old experiments are archived before any deletion decision.

## Timeline Summary

- **2023-09:** Baseline NLLB fine-tuning, early BLEU/model testing, and the first terminology experiments.
- **2023-10:** `<start>/<middle>/<end>` terminology protection, tokenizer/special-token tests, generation experiments, and train/eval loss visualization.
- **2023-10-31 to 2023-11-01:** `T&N method_modified`, `<code>` / `<code_id=*>` protection, and the first `T&N+R` main workflow.
- **2023-11-03:** Glossary and code preservation accuracy notebooks for `T&N+R`.
- **2023-11-28 to 2023-11-29:** `T&N+R preprocess` fixes and return-code token restoration experiments.
- **2026-05-19:** Mechanical CSV reference update. Many notebooks still reference intermediate files that are no longer committed.
- **2026-05-24:** RF-004 inventory and archive pass. Root notebooks were moved into `notebooks/main/`, `notebooks/analysis/`, and `notebooks/archive/2023-legacy/`.

## Classification

### Main Notebooks

These notebooks describe the main experiment path and should remain findable until RF-005, RF-006, and RF-007 replace their logic with importable modules and CLI entry points.

| Notebook | Timeline | Experiment Meaning | Current Dependency Status | Recommendation | Replacement Path |
| --- | --- | --- | --- | --- | --- |
| `notebooks/main/nllb-fine-tune_all.ipynb` | First committed 2023-09-06; last meaningful update 2023-09-18. | Baseline NLLB fine-tuning workflow. | References old `all_files_merged.csv` and local training config/state not committed now. | Keep as baseline experiment record. | RF-006 should replace training config and launch flow. |
| `notebooks/main/T&N+R preprocess.ipynb` | Originates from late 2023 tag/code preprocessing experiments; key creation 2023-11-28. | Final notebook-shaped preprocessing experiment for terminology, tags, and code/return-token protection. | Uses current `data/glossary.csv`; still has templated local CSV/log references. | Keep as main reference until extracted. | RF-005 should extract protection logic. |
| `notebooks/main/T&N+R method.ipynb` | Main `T&N+R` method formed around 2023-11-01; updated through 2023-11-29 and mechanically in 2026. | Closest historical notebook to the complete terminology/code-aware training method. | Uses current `data/glossary.csv`; still references old merged/tagged CSV files not committed. | Keep as main method record. | RF-005 and RF-006 should replace preprocessing and training setup. |
| `notebooks/main/model-generation.ipynb` | Renamed/created around 2023-10-27; mechanically updated in 2026. | Inference/generation entry for fine-tuned models. | References old validation/tagged CSV paths and local fine-tuned model outputs. | Keep as generation reference. | RF-006 should replace model path and inference config. |
| `notebooks/main/T&N+R method glossary accuracy testing.ipynb` | Created 2023-11-03; mechanically updated in 2026. | Glossary preservation accuracy check for the `T&N+R` method. | References historical `tests/files/translation_result...` outputs not committed now. | Keep as evaluation formula reference. | RF-007 should automate glossary preservation metrics. |
| `notebooks/main/T&N+R method code accuracy testing.ipynb` | Created 2023-11-03; mechanically updated in 2026. | Code-token preservation accuracy check for the `T&N+R` method. | References historical `tests/files/translation_result...` outputs not committed now. | Keep as evaluation formula reference. | RF-007 should automate code preservation metrics. |

### Analysis Notebooks

| Notebook | Timeline | Experiment Meaning | Current Dependency Status | Recommendation | Replacement Path |
| --- | --- | --- | --- | --- | --- |
| `notebooks/analysis/train_eval_loss_picture.ipynb` | Created 2023-10-26; updated 2023-11-02. | Utility notebook for visualizing train/eval loss curves. | Requires local `trainer_state.json` under ignored fine-tuned model outputs. | Keep as auxiliary analysis record. | RF-006 or RF-007 may replace with a small reporting script if still useful. |

### Archived Legacy Notebooks

These notebooks are kept for historical traceability but should not be treated as the active workflow.

| Notebook | Timeline | Experiment Meaning | Current Dependency Status | Recommendation | Replacement Path |
| --- | --- | --- | --- | --- | --- |
| `notebooks/archive/2023-legacy/T&N method.ipynb` | First committed 2023-09-06; evolved through 2023-10. | Early terminology-only workflow using glossary special tokens. | Uses current `data/glossary.csv`; references old merged CSV files not committed now. | Archive, not main. | Superseded by `T&N+R` notebooks and future RF-005 module. |
| `notebooks/archive/2023-legacy/T&N method_modified.ipynb` | Created 2023-10-31; updated around 2023-11-01. | Transitional experiment from terminology-only protection toward code protection. | References old merged/tagged CSV files not committed now. | Archive, not main. | Superseded by `T&N+R preprocess` and RF-005. |
| `notebooks/archive/2023-legacy/T&N method glossary accuracy testing.ipynb` | Originated in early testing flow; last mechanical update 2026-05-19. | Legacy glossary-preservation evaluation for `T&N`. | References old translation-result CSV not committed now. | Archive, later delete candidate after RF-007. | Superseded by `T&N+R` glossary evaluation and RF-007. |
| `notebooks/archive/2023-legacy/T&N method code accuracy testing.ipynb` | Created 2023-11-01; mechanically updated in 2026. | Legacy code-preservation evaluation for `T&N`. | References old translation-result CSV not committed now. | Archive, later delete candidate after RF-007. | Superseded by `T&N+R` code evaluation and RF-007. |
| `notebooks/archive/2023-legacy/special_token_test.ipynb` | Created 2023-10-24 as a one-off experiment. | Tokenizer/special-token behavior test. | Does not depend on committed data, but is exploratory rather than workflow documentation. | Archive, later delete candidate after fixture tests exist. | RF-005 can replace with tokenizer/protection tests. |
| `notebooks/archive/2023-legacy/return code tokens.ipynb` | Created 2023-11-29; mechanically updated in 2026. | One-off return-code token restoration experiment. | References local translation CSV and `{0}_code_logs.pkl` outputs not committed now. | Archive, later delete candidate after RF-005. | RF-005 should replace with round-trip restoration tests. |

## Deletion Candidates

No notebook is deleted in the first RF-004 pass. These files are candidates for a later deletion-only task after this inventory has been reviewed:

- `notebooks/archive/2023-legacy/special_token_test.ipynb`
- `notebooks/archive/2023-legacy/return code tokens.ipynb`
- `notebooks/archive/2023-legacy/T&N method.ipynb`
- `notebooks/archive/2023-legacy/T&N method_modified.ipynb`
- `notebooks/archive/2023-legacy/T&N method glossary accuracy testing.ipynb`
- `notebooks/archive/2023-legacy/T&N method code accuracy testing.ipynb`

## Known Dependency Gaps

- Several notebooks still reference removed intermediate corpus files such as `all_files_merged.csv`, `all_files_merged_zh-CN_ko.csv`, tagged CSV outputs, historical `translation_result...csv` files, and ignored training outputs.
- This inventory records missing references but does not repair notebook logic. Path fixes, module extraction, config migration, and automated evaluation belong to RF-005, RF-006, and RF-007.
- Raw data and review/intermediate outputs are intentionally not committed; final committed data lives in `data/segments.csv` and `data/glossary.csv`.
