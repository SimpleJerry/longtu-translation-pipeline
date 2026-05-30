# LONGTU KOREA Inc. — Game Localization Translation Pipeline

[한국어](README.md) | [English](README.en.md) | [中文](README.zh-CN.md)

This repository reproduces the game localization translation pipeline developed by the author during his tenure as a Systems Engineer at LONGTU KOREA Inc. (㈜룽투코리아; since renamed to STACO LINK Co., Ltd. / ㈜스타코링크). The original form was a collection of Jupyter Notebook files — mostly intermediate experiment artifacts. These were gradually reconstructed using Claude Code and Codex into the reproducible pipeline you see today.

The background: LONGTU KOREA Inc. (now STACO LINK Co., Ltd.) operated games in the Korean market and faced a continuous demand to localize large volumes of Chinese-language game text into Korean. Translation outsourcing costs ran into tens of millions of KRW per year. The goal of this project was to fine-tune an NLLB model on the company's proprietary game corpus and supplement the output with lightweight human proofreading, thereby automating a significant portion of the localization workflow.

The repository centers on an NLLB-based fine-tuning pipeline for Simplified Chinese (`zh-CN`) to Korean (`ko`), covering glossary matching, translation generation, BLEU evaluation, and terminology preservation checks.

## Project Status & Results

This repository holds a complete, reproducible zh-CN → ko fine-tuning pipeline and a trained, evaluated model.

- **Data cleaning** — systematic cleanup of a Chinese-Korean parallel corpus and game glossary. This includes local semantic pipeline (Stanza / jieba / kiwipiepy / wordfreq / `BAAI/bge-m3`) glossary cleaning, segment cleaning with markup/wrapper normalization and target-language-contamination removal, and glossary-segment cross-consistency checks. A full-corpus cloud LLM pass (OpenAI Batch API) provided final quality validation.
- **Fine-tuning & training** — fine-tuned `facebook/nllb-200-distilled-600M` on the game localization corpus, using a deterministic 8:1:1 split (seed 42) and early stopping to automatically select the best checkpoint on a composite quality metric.
- **Evaluation** — measured BLEU + chrF + glossary preservation (exact & no-space) on the held-out test split.
- **Inference** — built an inference CLI that translates new Chinese text to Korean using the trained checkpoint and exports results to CSV.

**Current model.** `checkpoint-48000` from the early-stopping run, decoded with beam search (`num_beams=4`). Held-out test split (seed 42, unseen during training and checkpoint selection):

| Metric | Score |
| --- | --- |
| BLEU (whitespace) | 0.325 |
| chrF (max_n=6, β=2) | 0.590 |
| Glossary preservation (no-space) | 0.954 |
| Glossary preservation (exact) | 0.950 |

**Capability ladder** (same test split, beam=4 throughout):

| Stage | BLEU | chrF | Preservation (no-space) |
| --- | --- | --- | --- |
| Base NLLB-600M *(pre-fine-tuning baseline — no markers)* | 0.009 | 0.226 | 0.323 |
| Fine-tuned `checkpoint-48000`, beam=4 **(current model)** | **0.325** | **0.590** | **0.954** |

![Performance comparison: Base vs. Fine-tuned NLLB-200](docs/figures/capability_comparison.png)

Net gain from fine-tuning + data cleaning: **+0.316 BLEU (~34×)** at the same beam=4 decode; glossary preservation rises from ~32% to ~95%. The base model generates fluent-sounding Korean but completely misses game-specific terminology and character names; fine-tuning and data cleaning together account for the full gap.

## Current Scope

- Keep only final training corpora and glossary data in the repository; sensitive raw Excel/CSV inputs are not committed.
- Clean the Chinese-Korean game glossary with a local semantic pipeline.
- Fine-tune `facebook/nllb-200-*` models on game localization data.
- Mark glossary terms during translation with a single `<start>...<end>` special-token shape.
- Keep T&N+R and code-id code/tag protection only as historical experiments, not as the current mainline.
- Export translation results to Excel/CSV and evaluate BLEU and glossary preservation.

## Technical Background

**Terminology marker (`<start>...<end>`) method.** To preserve game-specific terminology during translation, the pipeline uses source-side terminology injection. This approach is based on Dinu et al. (ACL 2019), *"Training Neural Machine Translation to Apply Terminology Constraints"*, where source-side glossary matches are wrapped with special token pairs and the model is trained on data where the target already contains the required term. The model learns a soft constraint — it reproduces glossary terms naturally from context rather than having tokens forcibly inserted at decode time (hard constrained decoding), which would risk disrupting fluency. A single marker shape is used to minimize tokenizer vocabulary expansion.

**Evaluation metrics.** BLEU (Papineni et al., 2002) measures n-gram precision and is the standard MT metric. Per Google Cloud Translate's [BLEU score interpretation guide](https://cloud.google.com/translate/docs/advanced/bleu-scores), a score of 0.30–0.40 (30–40%) corresponds to "Understandable to good translations" — the current model's 0.325 sits in this range. Korean's whitespace tokenization can underrepresent morpheme-level quality, so chrF (character n-gram F-score, Popović 2015) is reported alongside: character-level scoring correlates more strongly with human judgment for morphologically rich languages where surface word forms vary heavily by grammatical context. Glossary preservation is a domain-specific metric that directly checks whether glossary terms appear in the translation. Reporting both exact-match and no-space variants separates true term omissions from harmless spacing inconsistencies.

**Avoiding overfitting.**

1. **Early stopping** — a composite score (BLEU + chrF + glossary preservation) is monitored on the validation split; training halts when improvement stalls and the best checkpoint is automatically selected.
2. **Deterministic 8:1:1 data split** — fixed with seed 42; the test split is used exactly once for final reporting and never for checkpoint selection, preventing information leakage.
3. **Data quality gate** — noisy rows (contaminated translations, inconsistent terminology, structural fragments) act as overfitting signals, so only data passing the strict gate enters training.

## Repository Layout

```text
.
├── README.md
├── README.en.md
├── README.zh-CN.md
├── AGENTS.md
├── .env.example
├── requirements.txt
├── requirements-training.txt
├── data/
│   ├── glossary.csv
│   ├── segments.csv
│   └── review/                # generated locally, ignored by Git
├── configs/
│   ├── cross_cleaning/
│   ├── glossary/
│   ├── evaluation/
│   ├── inference/
│   ├── segments/
│   └── training/
├── scripts/
│   ├── cleanup_common.py
│   ├── llm_common.py
│   ├── glossary_semantic_pipeline.py
│   ├── glossary_llm_cleanup_pipeline.py
│   ├── evaluate_translation.py
│   ├── segments_cleaning_pipeline.py
│   ├── segments_llm_cleanup_pipeline.py
│   ├── segments_glossary_cross_cleaning_pipeline.py
│   ├── sweep_inference_params.py
│   ├── run_inference.py
│   └── train_model.py
├── src/
│   └── longtu_translation_pipeline/
├── tests/
├── logs/
├── notebooks/
│   ├── analysis/
│   └── archive/2023-legacy/
└── docs/
    ├── data-cleaning.md
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
| `configs/cross_cleaning/` | Thresholds for glossary/segments cross-consistency cleanup. |
| `configs/training/default.json` | Smoke/dry-run training config for data paths, language codes, model name, output directory, and basic parameters. |
| `configs/training/full_10k.json` | Full-data 10k-step training profile with explicit step, checkpoint, eval, and optimizer settings. |
| `configs/training/full_earlystop.json` | Early-stopping training profile; produced the current final model (`checkpoint-48000`). |
| `configs/inference/default.json` | Inference config for model path, input/output paths, language codes, and generation parameters. |
| `configs/evaluation/default.json` | Evaluation config for translation-result CSVs, glossary path, BLEU settings, and local report output. |
| `scripts/cleanup_common.py` | Shared utility functions used by segment and glossary cleanup pipelines. |
| `scripts/llm_common.py` | Shared OpenAI-compatible Chat Completions API client module. |
| `scripts/sweep_inference_params.py` | CLI for sweeping inference parameters (beam width, etc.) to find the best decoding configuration. |
| `scripts/glossary_semantic_pipeline.py` | Local glossary semantic cleanup pipeline using Stanza, jieba, kiwipiepy, wordfreq, and `BAAI/bge-m3`. |
| `scripts/glossary_llm_cleanup_pipeline.py` | Cloud OpenAI-compatible aggressive glossary cleanup entry point; it can only delete terms and writes local ignored review output. |
| `scripts/evaluate_translation.py` | Translation evaluation CLI for BLEU and glossary preservation; it does not load models. |
| `scripts/segments_cleaning_pipeline.py` | Local semantic segment cleanup pipeline; dry-run review output by default. |
| `scripts/segments_llm_cleanup_pipeline.py` | Cloud OpenAI-compatible full-segment cleanup entry point; Korean rewrites are applied only after local validation. |
| `scripts/segments_glossary_cross_cleaning_pipeline.py` | Glossary/segments cross-cleaning CLI for high-confidence terminology conflicts with local review output. |
| `scripts/train_model.py` | Training CLI for config dry-run, local tiny-tokenizer smoke, real tokenizer + tiny Trainer smoke, real NLLB model one-step smoke, pilot training, and formal run-directory training. |
| `scripts/run_inference.py` | Inference CLI for config dry-run and real checkpoint-based sample generation. |
| `src/longtu_translation_pipeline/text_protection.py` | Testable pure-function module for terminology marker protection. |
| `src/longtu_translation_pipeline/training_metrics.py` | Composite quality metric calculation and best-checkpoint selection logic used during training. |
| `src/longtu_translation_pipeline/config.py` | Dataclass parsing and validation for training/inference JSON configs. |
| `src/longtu_translation_pipeline/training.py` | Importable training-data preparation and Trainer wiring API. |
| `src/longtu_translation_pipeline/inference.py` | Importable inference-input planning dry-run API. |
| `src/longtu_translation_pipeline/evaluation.py` | Importable BLEU and glossary-preservation evaluation API. |
| `notebooks/analysis/` | Auxiliary analysis notebooks, such as train/eval loss visualization. |
| `notebooks/archive/2023-legacy/` | Archived 2023 original experiment notebooks. |
| `docs/notebooks/inventory.md` | Notebook timeline, purpose, dependency status, and keep/archive/delete guidance. |
| `docs/architecture/data-cleaning-pipeline.md` | Data-cleaning rule notes with examples for style tags, structured strings, short fragments, target contamination, and the strict gate. |
| `requirements-training.txt` | Training-chain dependencies: transformers, accelerate, sentencepiece, and CUDA PyTorch. |

## Environment

A Python virtual environment on Windows or Linux is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt           # data cleaning and evaluation
pip install -r requirements-training.txt  # add for training/inference (includes CUDA 13.2 PyTorch)
```

Stanza language models, Hugging Face caches, fine-tuned outputs, and raw data are all excluded by `.gitignore`.

## Basic Workflow

The training data entry points are two final CSVs. Raw Excel/CSV files are not committed.

- `data/segments.csv` — Chinese-Korean parallel corpus
- `data/glossary.csv` — game glossary

**Glossary cleanup** — download Stanza models first, then run the local pipeline.

```powershell
$env:STANZA_RESOURCES_DIR="D:\longtu-translation-pipeline\venv\stanza_resources"
venv\Scripts\python.exe -c "import stanza; stanza.download('zh', model_dir=r'D:\longtu-translation-pipeline\venv\stanza_resources'); stanza.download('ko', model_dir=r'D:\longtu-translation-pipeline\venv\stanza_resources')"
$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"
venv\Scripts\python.exe scripts\glossary_semantic_pipeline.py
```

When local rules are no longer sufficient, add a cloud LLM delete-only pass.

```powershell
$env:OPENAI_API_KEY="<your-key>"; $env:LLM_MODEL="<your-model>"
venv\Scripts\python.exe scripts\glossary_llm_cleanup_pipeline.py --apply
```

**Segment cleanup** — always dry-run first, apply after review. `--strict-check` must pass before training.

```powershell
venv\Scripts\python.exe scripts\segments_cleaning_pipeline.py --dry-run
venv\Scripts\python.exe scripts\segments_cleaning_pipeline.py --apply
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check
```

For a full LLM review pass:

```powershell
$env:OPENAI_API_KEY="<your-key>"; $env:LLM_MODEL="<your-model>"
venv\Scripts\python.exe scripts\segments_llm_cleanup_pipeline.py --dry-run
# after review: --apply
```

See [docs/architecture/data-cleaning-pipeline.md](docs/architecture/data-cleaning-pipeline.md) for detailed examples and rules for each cleanup type.

**Training** — uses `full_earlystop.json` (deterministic 8:1:1 split, seed 42, early stopping).

```powershell
venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_earlystop.json --train --run-name <run-name>
```

Quick smoke/dry-run checks:

```powershell
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --dry-run
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --nllb-smoke-test --smoke-rows 2
```

**Inference** — point to the training run directory.

```powershell
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate-test --run-dir <run-dir>
```

**Evaluation** — reports BLEU, chrF, and glossary preservation in one pass.

```powershell
venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\generation_report.json --input <generated-csv>
```

## Larger Models (1.3B / 3.3B)

NLLB-200 also ships larger bases — `nllb-200-1.3B` and `nllb-200-3.3B`. Larger dense MT models generally improve quality with diminishing returns, but this is **not guaranteed**, and we have **not** benchmarked 1.3B/3.3B on this project's fine-tuned zh-CN → ko task — so no expected quality-gain figure is given here. Cost, however, is predictable:

| | 600M (current) | 1.3B | 3.3B |
| --- | --- | --- | --- |
| Parameters | ~0.6B | ~1.3B (~2.1×) | ~3.3B (~5.4×) |
| Inference latency (dense, ∝ params) | 1× | ~2.1× | ~5.4× |
| Full fine-tune VRAM (AdamW, mixed precision) | fits 16 GB (this project used ~14.9 GB on an RTX 4070 Ti SUPER) | ~21 GB — exceeds 16 GB | ~53 GB — far exceeds a single 16 GB GPU |

On the 16 GB GPU used here, **1.3B full fine-tuning does not fit** without memory-saving techniques (gradient checkpointing, 8-bit optimizer, LoRA, or offload), and **3.3B needs a larger or multi-GPU setup**. Combined with the current `num_beams=4` default (already ~4× greedy), 3.3B inference would be on the order of ~21× the original 600M greedy cost.

Sources: parameter counts and the ~17.6 GB on-disk 3.3B checkpoint are from the Hugging Face model cards ([600M](https://huggingface.co/facebook/nllb-200-distilled-600M), [1.3B](https://huggingface.co/facebook/nllb-200-distilled-1.3B), [3.3B](https://huggingface.co/facebook/nllb-200-3.3B)); VRAM figures are this project's measured 600M run (`run_manifest.json`) plus standard AdamW memory accounting (~16 bytes/parameter for weights + gradients + optimizer state).

## Reference Documents

- [Refactor backlog](docs/refactor/backlog.md)
- [Follow-up tasks (parallel track map)](docs/refactor/follow-up-tasks.md)
- [Architecture decisions (ADR)](docs/decisions/adr/README.md)
- [Notebook inventory](docs/notebooks/inventory.md)
- [AI/Codex working rules](AGENTS.md)
