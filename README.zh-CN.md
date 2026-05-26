# LongtuKorea Translation Model

[한국어](README.md) | [English](README.en.md) | [中文](README.zh-CN.md)

这是 LongtuKorea 的游戏本地化机器翻译实验仓库。当前重点是基于 NLLB 的简体中文（`zh-CN`）到韩语（`ko`）微调流程，同时覆盖术语匹配、翻译结果生成、BLEU 评估与术语保留率检查。

这份 README 用来梳理当前仓库的真实状态。它还不是一个已经工程化封装好的生产项目，更接近“数据处理脚本 + 研究 notebook”的实验工作区。

## 当前范围

- 仓库只保留最终训练语料和术语表，不提交敏感 raw Excel/CSV 输入。
- 使用本地 semantic pipeline 清洗中文-韩文游戏术语表。
- 基于 `facebook/nllb-200-*` 系列模型进行游戏本地化语料微调。
- 使用统一的 `<start>...<end>` 特殊 token 在翻译中标记术语。
- T&N+R 和 code-id code/tag 保护只作为历史实验保留，不再作为当前主线。
- 将翻译结果导出为 Excel/CSV，并评估 BLEU 与术语保留率。

## 仓库结构

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
│   └── review/                # 本地生成，Git 忽略
├── configs/
│   ├── cross_cleaning/
│   ├── glossary/
│   ├── evaluation/
│   ├── inference/
│   ├── segments/
│   └── training/
├── scripts/
│   ├── glossary_semantic_pipeline.py
│   ├── evaluate_translation.py
│   ├── segments_cleaning_pipeline.py
│   ├── segments_glossary_cross_cleaning_pipeline.py
│   ├── run_inference.py
│   └── train_model.py
├── src/
│   └── longtu_translation_pipeline/
├── notebooks/
│   ├── main/
│   ├── analysis/
│   └── archive/2023-legacy/
└── docs/
    ├── data-cleaning.md
    ├── notebooks/inventory.md
    └── refactor/
```

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `data/segments.csv` | 最终正文/句段训练语料，只包含 `segment_id`、`zh-CN` 与 `ko`。 |
| `data/glossary.csv` | 最终中文-韩文游戏术语表，只包含 `term_id`、`zh-CN` 与 `ko`。 |
| `data/review/` | 本地数据清洗审计和人工核对 CSV，默认不提交。 |
| `configs/glossary/` | glossary 清洗的 seed、词表和规则配置。 |
| `configs/segments/` | segments 清洗的结构化字符串拆分、term/entity seed 和语义阈值配置。 |
| `configs/cross_cleaning/` | glossary 与 segments 交叉一致性清洗的阈值配置。 |
| `configs/training/default.json` | RF-006 第一阶段训练配置，声明数据路径、语言码、模型名、输出目录和基础训练参数。 |
| `configs/training/full_10k.json` | 首轮 full-data 10k 训练 profile，显式声明步数、checkpoint、eval 和优化器参数。 |
| `configs/inference/default.json` | RF-006 第一阶段推理配置，声明模型路径、输入/输出路径、语言码和生成参数。 |
| `configs/evaluation/default.json` | RF-007 评估配置，声明翻译结果 CSV、glossary、BLEU 口径和本地报告目录。 |
| `scripts/glossary_semantic_pipeline.py` | 本地 glossary semantic 清洗 pipeline，使用 Stanza、jieba、kiwipiepy、wordfreq 与 `BAAI/bge-m3`。 |
| `scripts/evaluate_translation.py` | 翻译结果评估 CLI，计算 BLEU 与 glossary preservation，不加载模型。 |
| `scripts/segments_cleaning_pipeline.py` | 本地 segments 语义清洗 pipeline，默认 dry-run 生成 review CSV。 |
| `scripts/segments_glossary_cross_cleaning_pipeline.py` | glossary/segments 交叉清洗 CLI，删除高置信术语冲突训练行并输出本地 review。 |
| `scripts/train_model.py` | 训练 CLI；支持配置 dry-run、本地 tiny tokenizer smoke、真实 tokenizer + tiny Trainer smoke、真实 NLLB 模型 1-step smoke、pilot training 和正式 run 目录训练。 |
| `scripts/run_inference.py` | 推理 CLI；支持配置 dry-run 和基于真实 checkpoint 的小样本 generation。 |
| `src/longtu_translation_pipeline/text_protection.py` | 可测试的术语 marker 保护纯函数模块。 |
| `src/longtu_translation_pipeline/config.py` | 训练/推理 JSON 配置的 dataclass 解析和校验。 |
| `src/longtu_translation_pipeline/training.py` | 可导入的训练数据准备和 Trainer 链路 API。 |
| `src/longtu_translation_pipeline/inference.py` | 可导入的推理输入计划 dry-run API。 |
| `src/longtu_translation_pipeline/evaluation.py` | 可导入的 BLEU 与 glossary preservation 评估 API。 |
| `notebooks/main/` | 主线训练、预处理、生成和评估实验 notebook。 |
| `notebooks/analysis/` | 辅助分析 notebook，例如训练 loss 可视化。 |
| `notebooks/archive/2023-legacy/` | 2023 年旧实验归档，第一轮不直接删除。 |
| `docs/notebooks/inventory.md` | Notebook 时间线、用途、依赖状态和保留/归档/删除建议。 |
| `docs/data-cleaning.md` | 数据清洗规则说明，包含样式 tag、结构化字符串、短碎片、目标语言污染和 strict gate 示例。 |
| `requirements-training.txt` | RF-006 训练 smoke / 后续训练链路依赖。 |

## 运行环境

建议使用 Windows 或 Linux 的 Python 虚拟环境。`requirements.txt` 当前记录已经实际落地使用的本地 semantic cleaning 依赖与 CUDA 13.2 版本 PyTorch；基础 CLI、dry-run、测试和 RF-007 evaluation 主要使用标准库，不代表所有场景都必须安装完整依赖。`requirements-training.txt` 记录 RF-006 训练 smoke / 后续训练链路依赖，目前包含 `transformers`、`tokenizers`、`accelerate`、`sentencepiece` 及其直接运行依赖；`datasets` 尚未进入当前最小链路。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
jupyter lab
```

如需运行 RF-006-P2 及之后的训练/推理链路命令，再安装训练链路依赖：

```powershell
python -m pip install -r requirements-training.txt
```

注意：

- Stanza 中文/韩文模型、Hugging Face embedding 缓存放在本地虚拟环境目录下，不提交到 Git。
- 旧 BLEU notebook 曾使用 `nltk.translate.bleu_score`；当前 RF-007 evaluation CLI 使用纯 Python 实现，不需要 `nltk`。
- 大模型、微调输出、翻译结果、raw 数据和本地模型缓存已通过 `.gitignore` 排除。

## 基本流程

仓库中的训练数据入口是最终 CSV：

- `data/segments.csv`
- `data/glossary.csv`

raw Excel/CSV 文件包含敏感业务数据，不提交到仓库。`data/glossary.csv` 基于本地 semantic pipeline 继续迭代清洗；对应审计文件会生成到本地 `data/review/`，但不提交到 Git。
`data/segments.csv` 为 glossary 清洗提供当前产品语料证据，但不是术语保留的唯一标准或充分条件。
pipeline 还会结合本地词频、词性、embedding 和游戏域信号区分普通词与游戏术语。
最终提交的两个 CSV 都是中韩双语语料，非中韩训练列不再保留在最终 corpus 中。

如需重跑 glossary 清洗，先下载 Stanza 模型：

```powershell
$env:STANZA_RESOURCES_DIR="D:\longtu-translation-pipeline\venv\stanza_resources"
venv\Scripts\python.exe -c "import stanza; stanza.download('zh', model_dir=r'D:\longtu-translation-pipeline\venv\stanza_resources'); stanza.download('ko', model_dir=r'D:\longtu-translation-pipeline\venv\stanza_resources')"
```

然后运行本地 pipeline：

```powershell
$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"
$env:STANZA_RESOURCES_DIR="D:\longtu-translation-pipeline\venv\stanza_resources"
venv\Scripts\python.exe scripts\glossary_semantic_pipeline.py
```

默认规则目录是 `configs/glossary/`，其中包含 seed、词表和 `rules.json`；可用 `--config-dir`、`--game-seeds` 与 `--common-noun-seeds` 指定替代文件。

如需检查或迭代正文语料清洗，先运行 dry-run：

```powershell
venv\Scripts\python.exe scripts\segments_cleaning_pipeline.py --dry-run
```

该 pipeline 会先剥离 `<c=...>` 等表现层样式标签并解开对称外层包装，再删除高置信非句段碎片和 ko 侧目标语言污染，然后使用 Stanza、jieba、kiwipiepy 和 `BAAI/bge-m3` 判断 term/entity-like segment；placeholder 行默认保留，只做 mismatch 审计，除非目标侧已经触发强污染规则。该命令不会改写 `data/segments.csv`，只会在本地 `data/review/segments/` 下生成审计 CSV。人工确认后再使用 `--apply` 重写最终语料。各类清洗的例子见 `docs/data-cleaning.md`。

如需检查 glossary 与 segments 的术语一致性，先 dry-run，再在确认后 apply：

```powershell
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --dry-run
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --apply
```

交叉清洗只自动删除高置信 glossary 噪声或强术语冲突 segment，不自动改写韩文译文；删除内容会写入本地 `data/review/segments_glossary_cross/`。
它的基本步骤是：先用最长优先、非重叠的中文术语匹配扫描 `segments.csv`；再用 exact 和 no-space exact 检查韩文是否保留术语表译法；然后按 `configs/cross_cleaning/rules.json` 中的阈值统计每个 term 的 preserved/missing 证据，将 term 分为 glossary 噪声、强术语或待复核；最后只删除高置信 glossary 噪声和命中强术语但未按表翻译的 segment 行。
训练前可使用更严格的门禁模式，要求所有 remaining glossary 术语在所有 segment 中都按表保留：

```powershell
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-dry-run
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check
```

严格模式会先根据真实 `segments.csv` 翻译选择可强制执行的 glossary：无缺失的 term 直接保留，强游戏域 term 需要足够 preserved evidence 且 missing rate 低于阈值，经验稳定 term 需要高 preserved count/rate；不满足条件且存在 mismatch 的 term 会从 glossary 移除。随后，仍命中可强制执行 glossary 但韩文未按表保留的 segment 会被删除。`--strict-check` 只检查当前数据，发现任意缺失即返回失败；确认 review 后再使用 `--strict-apply`。
full training 或最终 test report 前，`--strict-check` 必须通过。

训练/推理工程入口目前处于 RF-006 的 smoke-test / pilot / 正式 run 硬化阶段：dry-run 只做配置读取、数据校验和确定性的 train/validation/test 计划。RF-006-P7 会在 ignored 的 `fine-tuned-models/.../runs/run-*` 下写入固定 split artifact 和 `run_manifest.json`；RF-006-P10 将正式实验修正为 seed `42` 的 8:1:1 划分。validation 只用于训练期间 eval 和 checkpoint 观察，最终性能报告必须使用独立 test split。RF-006-P8 基于固定 validation split 生成翻译 CSV，`--generate-test` 基于固定 test split 生成最终评估 CSV。P4/P5/P6/P7/P8/P2 都是工程链路验证，直到显式启动 full training 之前不代表正式模型质量。

```powershell
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --dry-run
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --smoke-test
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --nllb-smoke-test --smoke-rows 2
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --real-model-smoke-test --smoke-rows 2
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --pilot-train --pilot-rows 64 --max-steps 4 --save-steps 2
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --train --limit-rows 128 --max-steps 4 --save-steps 2 --save-total-limit 2 --logging-steps 1
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --train --run-dir fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-name --resume-from-checkpoint latest --max-steps 6 --save-steps 2 --save-total-limit 2 --logging-steps 1
venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k.json --train --run-name run-full-10k-corrected-v1
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --dry-run
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate --model-path fine-tuned-models\nllb-200-distilled-600M\zh2ko\pilot\run-20260525-093832\checkpoint-4 --sample-rows 8
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate-validation --run-dir fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-name
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate-test --run-dir fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-full-10k-corrected-v1
```

如需评估已有翻译结果 CSV，使用 RF-007 评估入口。输入默认采用 notebook 旧输出列名：`source`、`references`、`candidates`。BLEU 默认按韩文空格词分词，glossary preservation 会去除候选译文中的 `<start>...<end>` marker 后检查韩文术语是否出现。模型生成的空 `candidates` 会作为评估结果中的 `empty_candidate_rows` 记录，而不是让报告中断。
推理入口默认会先用 `data/glossary.csv` 对输入 source 应用与训练一致的 `<start>...<end>` 术语 marker，但生成 CSV 仍保留原始 source 以便 review。RF-007 会同时报告 exact 与 no-space glossary preservation：exact 用于观察格式一致性，no-space 用于避免把韩文空格差异误判成真正术语缺失。

```powershell
venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\default.json --input translation_result.csv
venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\generation_report.json --checkpoint fine-tuned-models\nllb-200-distilled-600M\zh2ko\pilot\run-20260525-093832\checkpoint-4
venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\generation_report.json --input data\review\inference\test\run-full-10k-corrected-v1\test_generated.csv --report-dir data\review\evaluation\test_report\run-full-10k-corrected-v1 --checkpoint fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-full-10k-corrected-v1\checkpoint-10000
```

训练 notebook 中的语言列按 NLLB 语言代码转换：

```text
zh-CN -> zho_Hans
zh-TW -> zho_Hant
en    -> eng_Latn
ja    -> jpn_Jpan
ko    -> kor_Hang
```

Notebook 保留为实验记录；T&N+R 相关 notebook 已视为 deprecated historical experiments。各 notebook 的用途、顺序和依赖状态见 `docs/notebooks/inventory.md`。

当前术语保护逻辑已抽取到 `src/longtu_translation_pipeline/text_protection.py`。该模块只使用单段 `<start>...<end>` marker；旧双段术语 marker 和 code-id 保护已从当前工程主线中废弃。当前 notebook 尚未改写为 import 该模块；它们继续作为实验记录保留。

## 架构与重构入口

长期重构待办不放在 README 中维护。请查看：

- [重构 backlog](docs/refactor/backlog.md)
- [重构决策记录](docs/refactor/decisions.md)
- [Notebook inventory](docs/notebooks/inventory.md)
- [AI/Codex 工作规则](AGENTS.md)
