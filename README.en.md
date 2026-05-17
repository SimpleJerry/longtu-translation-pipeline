# LongtuKorea Translation Model

[한국어](README.md) | [English](README.en.md) | [中文](README.zh-CN.md)

This repository contains LongtuKorea's experimental game localization machine translation workflow. The current focus is NLLB-based fine-tuning for Simplified Chinese (`zh-CN`) to Korean (`ko`), with glossary matching, code/tag protection, translation generation, BLEU evaluation, and terminology/code preservation checks.

This README documents the repository as it exists today. The project is still closer to a research notebook workspace than a packaged production codebase.

## Current Scope

- Clean multilingual Excel source files and merge them into language-pair CSV files.
- Fine-tune `facebook/nllb-200-*` models on game localization data.
- Preserve glossary terms during translation with `<start>`, `<middle>`, and `<end>` special tokens.
- Experiment with `<code_id=*>` tokens to protect placeholders, return codes, and game UI tags.
- Export translation results to Excel/CSV and evaluate BLEU, glossary preservation, and code preservation.

## Repository Layout

```text
.
├── README.md
├── README.en.md
├── README.zh-CN.md
├── requirements.txt
├── glossary_all.xlsx
├── data/
│   ├── data-cleaning-and-merging.py
│   └── input/
│       ├── 盾勇/
│       └── 스크립트(열강,검마,WOG)/
├── tests/
│   └── BLEU-score-calculating.ipynb
├── nllb-fine-tune_all.ipynb
├── T&N method.ipynb
├── T&N method_modified.ipynb
├── T&N+R preprocess.ipynb
├── T&N+R method.ipynb
├── model-generation.ipynb
├── model-generation-manual.ipynb
├── special_token_test.ipynb
├── return code tokens.ipynb
├── tag.ipynb
└── train_eval_loss_picture.ipynb
```

## Key Files

| File | Purpose |
| --- | --- |
| `data/data-cleaning-and-merging.py` | Reads multiple Excel files and sheets, normalizes language columns, and creates merged files plus language-pair CSV files. |
| `data/input/` | Raw game script and glossary Excel files. |
| `glossary_all.xlsx` | Combined terminology data used in Chinese-Korean glossary experiments. |
| `nllb-fine-tune_all.ipynb` | Baseline NLLB fine-tuning workflow. |
| `T&N method.ipynb` | Terminology and Notation experiment using glossary special tokens. |
| `T&N+R preprocess.ipynb` | Preprocessing experiment for terminology and code protection. |
| `T&N+R method.ipynb` | Training experiment that combines terminology, notation, and return-code protection. |
| `model-generation.ipynb` | Generates translations with a fine-tuned model. |
| `model-generation-manual.ipynb` | Generates translations with manual decoding that preserves special tokens. |
| `tests/BLEU-score-calculating.ipynb` | Calculates BLEU between generated translations and references. |
| `train_eval_loss_picture.ipynb` | Builds train/eval loss charts from training logs. |

## Environment

A Python virtual environment on Windows or Linux is recommended. `requirements.txt` pins CUDA 11.8 PyTorch packages for GPU training.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
jupyter lab
```

Notes:

- If `torch==2.0.1+cu118` fails to install, you may need to use the PyTorch CUDA 11.8 wheel index.
- The BLEU notebook imports `nltk.translate.bleu_score`; install `nltk` separately if it is missing from your environment.
- Large models, fine-tuned outputs, translation results, and generated data outputs are excluded by `.gitignore`.

## Basic Workflow

1. Put raw Excel files under `data/input/`.
2. Run the data merge script from the `data/` directory.

```powershell
cd data
python data-cleaning-and-merging.py
```

3. Check the generated outputs.

```text
data/output/
data/all_files_merged.xlsx
data/all_files_merged.csv
data/output/all_files_merged_zh-CN_ko.csv
```

4. Convert language columns to NLLB language codes in the training notebooks.

```text
zh-CN -> zho_Hans
zh-TW -> zho_Hant
en    -> eng_Latn
ja    -> jpn_Jpan
ko    -> kor_Hang
```

5. Run `T&N method.ipynb` or `T&N+R method.ipynb` for terminology/code-aware preprocessing and fine-tuning.
6. Use `model-generation.ipynb` or `model-generation-manual.ipynb` to generate translations.
7. Evaluate output quality with the BLEU, glossary accuracy, and code accuracy notebooks.

## Current Limitations

- Core logic is scattered across notebooks, making reuse and automation difficult.
- Data paths, model paths, language pairs, and training arguments are hard-coded.
- Tests are evaluation notebooks rather than automated unit tests.
- Versioning rules for raw data and experiment outputs are not defined yet.
- `requirements.txt` captures a full experiment environment; training, inference, and documentation dependencies should eventually be separated.

## Refactor Direction

When moving into a new repository, this structure is recommended:

```text
.
├── src/
│   └── longtu_l10n_mt/
│       ├── data/
│       ├── tokenization/
│       ├── training/
│       ├── inference/
│       └── evaluation/
├── configs/
│   ├── data.yaml
│   ├── train.zh-ko.yaml
│   └── inference.zh-ko.yaml
├── scripts/
│   ├── prepare_data.py
│   ├── train.py
│   ├── translate.py
│   └── evaluate.py
├── notebooks/
│   └── experiments/
├── tests/
├── docs/
└── README.md
```

Suggested priorities:

1. Move Excel merging, terminology tagging, and code tagging into `src/` modules.
2. Move language-code mappings and paths into YAML configs.
3. Keep notebooks as experiment records, and move repeatable workflows into CLI scripts.
4. Add unit tests for glossary preservation, code preservation, and tag preservation.
5. Define storage rules for training and inference artifacts.
