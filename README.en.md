# LongtuKorea Translation Model

[한국어](README.md) | [English](README.en.md) | [中文](README.zh-CN.md)

This repository contains LongtuKorea's experimental game localization machine translation workflow. The current focus is NLLB-based fine-tuning for Simplified Chinese (`zh-CN`) to Korean (`ko`), with glossary matching, code/tag protection, translation generation, BLEU evaluation, and terminology/code preservation checks.

This README documents the repository as it exists today. The project is still closer to a research notebook workspace than a packaged production codebase.

## Current Scope

- Keep only final training corpora and glossary data in the repository; sensitive raw Excel/CSV inputs are not committed.
- Clean the Chinese-Korean game glossary with a local semantic pipeline.
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
├── data/
│   ├── glossary.csv
│   ├── segments.csv
│   └── review/                # generated locally, ignored by Git
├── configs/
│   └── glossary/
├── scripts/
│   └── glossary_semantic_pipeline.py
├── nllb-fine-tune_all.ipynb
├── T&N method.ipynb
├── T&N method_modified.ipynb
├── T&N+R preprocess.ipynb
├── T&N+R method.ipynb
├── model-generation.ipynb
├── special_token_test.ipynb
├── return code tokens.ipynb
└── train_eval_loss_picture.ipynb
```

## Key Files

| File | Purpose |
| --- | --- |
| `data/segments.csv` | Final segment training corpus with `segment_id`, `zh-CN`, and `ko` columns. |
| `data/glossary.csv` | Final Chinese-Korean game glossary with `term_id`, `zh-CN`, and `ko` columns. |
| `data/review/` | Local data-cleaning audit CSVs and review artifacts; not committed by default. |
| `configs/glossary/` | Seeds, lexicons, and rules for glossary cleanup. |
| `scripts/glossary_semantic_pipeline.py` | Local glossary semantic cleanup pipeline using Stanza, jieba, kiwipiepy, wordfreq, and `BAAI/bge-m3`. |
| `nllb-fine-tune_all.ipynb` | Baseline NLLB fine-tuning workflow. |
| `T&N method.ipynb` | Terminology and Notation experiment using glossary special tokens. |
| `T&N+R preprocess.ipynb` | Preprocessing experiment for terminology and code protection. |
| `T&N+R method.ipynb` | Training experiment that combines terminology, notation, and return-code protection. |
| `model-generation.ipynb` | Generates translations with a fine-tuned model. |
| `train_eval_loss_picture.ipynb` | Builds train/eval loss charts from training logs. |

## Environment

A Python virtual environment on Windows or Linux is recommended. `requirements.txt` records CUDA 13.2 PyTorch packages plus the local glossary-cleanup dependencies.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
jupyter lab
```

Notes:

- Stanza Chinese/Korean models and Hugging Face embedding caches live under the local virtual environment and are not committed.
- The BLEU notebook imports `nltk.translate.bleu_score`; install `nltk` separately if it is missing from your environment.
- Large models, fine-tuned outputs, translation results, raw data, and local model caches are excluded by `.gitignore`.

## Basic Workflow

The training data entry points committed to this repository are final CSVs:

- `data/segments.csv`
- `data/glossary.csv`

Sensitive raw Excel/CSV files are not committed. `data/glossary.csv` is iteratively cleaned by the local semantic cleanup pipeline, and audit files are generated under local `data/review/` but ignored by Git.
`data/segments.csv` provides current product-corpus evidence for glossary cleanup, but it is not the only criterion or a sufficient keep signal.
The pipeline also uses local word frequency, POS shape, embeddings, and game-domain signals to separate common words from game terms.
Both final CSVs are intentionally bilingual: non-Chinese/Korean training columns are removed from the committed corpus.

To rerun glossary cleanup, download the Stanza models first:

```powershell
$env:STANZA_RESOURCES_DIR="D:\longtu-translation-pipeline\venv\stanza_resources"
venv\Scripts\python.exe -c "import stanza; stanza.download('zh', model_dir=r'D:\longtu-translation-pipeline\venv\stanza_resources'); stanza.download('ko', model_dir=r'D:\longtu-translation-pipeline\venv\stanza_resources')"
```

Then run the local pipeline:

```powershell
$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"
$env:STANZA_RESOURCES_DIR="D:\longtu-translation-pipeline\venv\stanza_resources"
venv\Scripts\python.exe scripts\glossary_semantic_pipeline.py
```

The default rule directory is `configs/glossary/`, which contains seed files, lexicons, and `rules.json`; pass `--config-dir`, `--game-seeds`, and `--common-noun-seeds` to use alternatives.

Training notebooks convert language columns to NLLB language codes:

```text
zh-CN -> zho_Hans
zh-TW -> zho_Hant
en    -> eng_Latn
ja    -> jpn_Jpan
ko    -> kor_Hang
```

Run `T&N method.ipynb` or `T&N+R method.ipynb` for terminology/code-aware preprocessing and fine-tuning, then use the generation and evaluation notebooks for BLEU, glossary preservation, and code preservation checks.

## Architecture and Refactor Notes

Long-term refactor tasks are not maintained in README files. See:

- [Refactor backlog](docs/refactor/backlog.md)
- [Refactor decisions](docs/refactor/decisions.md)
- [AI/Codex working rules](AGENTS.md)
