# LongtuKorea Translation Model

[한국어](README.md) | [English](README.en.md) | [中文](README.zh-CN.md)

This repository contains LongtuKorea's experimental game localization machine translation workflow. The current focus is NLLB-based fine-tuning for Simplified Chinese (`zh-CN`) to Korean (`ko`), with glossary matching, translation generation, BLEU evaluation, and terminology preservation checks.

This README documents the repository as it exists today. The project is still closer to a research notebook workspace than a packaged production codebase.

## Current Scope

- Keep only final training corpora and glossary data in the repository; sensitive raw Excel/CSV inputs are not committed.
- Clean the Chinese-Korean game glossary with a local semantic pipeline.
- Fine-tune `facebook/nllb-200-*` models on game localization data.
- Mark glossary terms during translation with a single `<start>...<end>` special-token shape.
- Keep T&N+R and code-id code/tag protection only as historical experiments, not as the current mainline.
- Export translation results to Excel/CSV and evaluate BLEU and glossary preservation.

## Repository Layout

```text
.
├── README.md
├── README.en.md
├── README.zh-CN.md
├── requirements.txt
├── requirements-training.txt
├── data/
│   ├── glossary.csv
│   ├── segments.csv
│   └── review/                # generated locally, ignored by Git
├── configs/
│   ├── glossary/
│   ├── evaluation/
│   ├── inference/
│   ├── segments/
│   └── training/
├── scripts/
│   ├── glossary_semantic_pipeline.py
│   ├── evaluate_translation.py
│   ├── segments_cleaning_pipeline.py
│   ├── run_inference.py
│   └── train_model.py
├── src/
│   └── longtu_translation_pipeline/
├── notebooks/
│   ├── main/
│   ├── analysis/
│   └── archive/2023-legacy/
└── docs/
    ├── notebooks/inventory.md
    └── refactor/
```

## Key Files

| File | Purpose |
| --- | --- |
| `data/segments.csv` | Final segment training corpus with `segment_id`, `zh-CN`, and `ko` columns. |
| `data/glossary.csv` | Final Chinese-Korean game glossary with `term_id`, `zh-CN`, and `ko` columns. |
| `data/review/` | Local data-cleaning audit CSVs and review artifacts; not committed by default. |
| `configs/glossary/` | Seeds, lexicons, and rules for glossary cleanup. |
| `configs/segments/` | Structured-string splitting, term/entity seeds, and semantic thresholds for segment cleanup. |
| `configs/training/default.json` | RF-006 phase 1 training config for data paths, language codes, model name, output directory, and basic training parameters. |
| `configs/inference/default.json` | RF-006 phase 1 inference config for model path, input/output paths, language codes, and generation parameters. |
| `configs/evaluation/default.json` | RF-007 evaluation config for translation-result CSVs, glossary path, BLEU settings, and local report output. |
| `scripts/glossary_semantic_pipeline.py` | Local glossary semantic cleanup pipeline using Stanza, jieba, kiwipiepy, wordfreq, and `BAAI/bge-m3`. |
| `scripts/evaluate_translation.py` | Translation evaluation CLI for BLEU and glossary preservation; it does not load models. |
| `scripts/segments_cleaning_pipeline.py` | Local semantic segment cleanup pipeline; dry-run review output by default. |
| `scripts/train_model.py` | Training CLI for config dry-run, local tiny-tokenizer smoke, real tokenizer + tiny Trainer smoke, real NLLB model one-step smoke, pilot training, and formal run-directory training. |
| `scripts/run_inference.py` | Inference CLI for config dry-run and real checkpoint-based sample generation. |
| `src/longtu_translation_pipeline/text_protection.py` | Testable pure-function module for terminology marker protection. |
| `src/longtu_translation_pipeline/config.py` | Dataclass parsing and validation for training/inference JSON configs. |
| `src/longtu_translation_pipeline/training.py` | Importable training-data preparation and Trainer wiring API. |
| `src/longtu_translation_pipeline/inference.py` | Importable inference-input planning dry-run API. |
| `src/longtu_translation_pipeline/evaluation.py` | Importable BLEU and glossary-preservation evaluation API. |
| `notebooks/main/` | Main training, preprocessing, generation, and evaluation experiment notebooks. |
| `notebooks/analysis/` | Auxiliary analysis notebooks, such as train/eval loss visualization. |
| `notebooks/archive/2023-legacy/` | Archived 2023 legacy experiments; not deleted in the first pass. |
| `docs/notebooks/inventory.md` | Notebook timeline, purpose, dependency status, and keep/archive/delete guidance. |
| `requirements-training.txt` | RF-006 training smoke-test and future training-chain dependencies. |

## Environment

A Python virtual environment on Windows or Linux is recommended. `requirements.txt` currently records dependencies that are already used by local semantic-cleaning workflows plus CUDA 13.2 PyTorch. Base CLIs, dry runs, tests, and RF-007 evaluation are mostly standard-library and do not imply that every workflow needs the full dependency set. `requirements-training.txt` records the RF-006 training smoke-test and future training-chain dependencies, including `transformers`, `tokenizers`, `accelerate`, `sentencepiece`, and their direct runtime dependencies; `datasets` is not part of the current minimal chain yet.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
jupyter lab
```

To run RF-006-P2 and later training/inference-chain commands, also install the training-chain dependencies:

```powershell
python -m pip install -r requirements-training.txt
```

Notes:

- Stanza Chinese/Korean models and Hugging Face embedding caches live under the local virtual environment and are not committed.
- Legacy BLEU notebooks used `nltk.translate.bleu_score`; the current RF-007 evaluation CLI uses a pure-Python implementation and does not require `nltk`.
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

To inspect or iterate segment cleanup, run a dry run first:

```powershell
venv\Scripts\python.exe scripts\segments_cleaning_pipeline.py --dry-run
```

This pipeline first strips presentation tags such as `<c=...>` and unwraps symmetric outer wrappers, then uses Stanza, jieba, kiwipiepy, and `BAAI/bge-m3` to score term/entity-like segments. Placeholder rows are kept by default and only audited for mismatch. The command does not rewrite `data/segments.csv`; it only writes local audit CSVs under `data/review/segments/`. Use `--apply` only after manual review.

The training/inference engineering entry points are currently in the RF-006 smoke-test/pilot/formal-run hardening phase. Dry-run reads config, validates data, and plans train/validation counts. RF-006-P2 adds a local tiny-tokenizer smoke test; RF-006-P3 uses the real NLLB tokenizer and a randomly initialized tiny seq2seq model for a one-step Trainer smoke test; RF-006-P4 uses real NLLB model weights for a one-step smoke test to validate CUDA, special-token resize, data tensors, and Trainer wiring; RF-006-P5 runs a small real-model pilot training job to validate checkpoint saving, resume, loss logging, and output directories; RF-006-P6 loads a checkpoint, writes a sample generation CSV, and verifies the RF-007-compatible evaluation schema. RF-007-P2 evaluates that generation CSV into a fixed report directory with summary, glossary rows, sample review, and manifest files. RF-006-P7 adds a formal `--train` command that writes fixed split artifacts and `run_manifest.json` under ignored `fine-tuned-models/.../runs/run-*`. RF-006-P8 generates translation CSVs from that fixed validation split instead of the first N rows of `data/segments.csv`. P4/P5/P6/P7/P8/P2 are engineering-chain checks until a full training run is explicitly started.

```powershell
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --dry-run
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --smoke-test
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --nllb-smoke-test --smoke-rows 2
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --real-model-smoke-test --smoke-rows 2
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --pilot-train --pilot-rows 64 --max-steps 4 --save-steps 2
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --train --limit-rows 128 --max-steps 4 --save-steps 2 --save-total-limit 2 --logging-steps 1
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --train --run-dir fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-name --resume-from-checkpoint latest --max-steps 6 --save-steps 2 --save-total-limit 2 --logging-steps 1
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --dry-run
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate --model-path fine-tuned-models\nllb-200-distilled-600M\zh2ko\pilot\run-20260525-093832\checkpoint-4 --sample-rows 8
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate-validation --run-dir fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-name
```

To evaluate an existing translation-result CSV, use the RF-007 evaluation entry point. Input uses the historical notebook output columns: `source`, `references`, and `candidates`. BLEU defaults to Korean whitespace tokenization, and glossary preservation strips `<start>...<end>` markers from candidate text before checking Korean term presence.

```powershell
venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\default.json --input translation_result.csv
venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\generation_report.json --checkpoint fine-tuned-models\nllb-200-distilled-600M\zh2ko\pilot\run-20260525-093832\checkpoint-4
```

Training notebooks convert language columns to NLLB language codes:

```text
zh-CN -> zho_Hans
zh-TW -> zho_Hant
en    -> eng_Latn
ja    -> jpn_Jpan
ko    -> kor_Hang
```

Notebooks are retained as experiment records. T&N+R notebooks are now deprecated historical experiments; see `docs/notebooks/inventory.md` for each notebook's purpose, order, and dependency status.

Current terminology protection logic now lives in `src/longtu_translation_pipeline/text_protection.py`. The module uses only the single `<start>...<end>` marker shape; the old dual-term marker and code-id protection are deprecated from the current engineering mainline. Notebooks are not rewritten to import it in this pass; they remain experiment records.

## Architecture and Refactor Notes

Long-term refactor tasks are not maintained in README files. See:

- [Refactor backlog](docs/refactor/backlog.md)
- [Refactor decisions](docs/refactor/decisions.md)
- [Notebook inventory](docs/notebooks/inventory.md)
- [AI/Codex working rules](AGENTS.md)
