# 龙图韩国游戏本地化翻译管道

[한국어](README.md) | [English](README.en.md) | [中文](README.zh-CN.md)

本仓库是作者在㈜룽투코리아（LONGTU KOREA Inc.，龙图韩国，现更名为 STACO LINK Co., Ltd. / ㈜스타코링크）担任系统工程师期间所从事的游戏本地化翻译管道工作的复现。原始形态是一批 Jupyter Notebook 文件，大多数是实验过程中产生的中间文件。此后通过 Claude Code 与 Codex 逐步对旧有工程进行重构，整理成现在这个可复现的管道。

项目背景如下：龙图韩国（LONGTU KOREA Inc.，现 STACO LINK Co., Ltd.）在韩国市场运营游戏时，面临大量将中文文本本地化为韩文的需求，每年的翻译外包费用高达数千万韩元。本项目的目标是基于公司掌握的游戏语料对 NLLB 模型进行微调，辅以少量人工校对，从而实现翻译自动化，节省翻译成本。

本仓库当前重点是基于 NLLB 的简体中文（`zh-CN`）到韩语（`ko`）微调流程，同时覆盖术语匹配、翻译结果生成、BLEU 评估与术语保留率检查。

## 项目状态与成果

本仓库同时包含一条可复现的 zh-CN → ko 微调管道和一个已训练、已评估的模型。

- **数据清洗** —— 对中韩并行语料和游戏术语表进行了系统性清洗。包括：基于本地 semantic pipeline（Stanza / jieba / kiwipiepy / wordfreq / `BAAI/bge-m3`）的 glossary 清洗、含 markup/wrapper 归一化与目标语言污染删除的 segment 清洗，以及 glossary-segment 交叉一致性检查。最终通过全量云端 LLM pass（OpenAI Batch API）对语料质量进行了额外验证。
- **微调与训练** —— 基于 `facebook/nllb-200-distilled-600M` 对游戏本地化语料进行微调，使用确定性 8:1:1 划分（seed 42）和 early-stopping 自动选出复合质量指标最优的 checkpoint。
- **评估** —— 在 held-out test split 上测量了 BLEU + chrF + glossary preservation（exact & no-space）。
- **推理** —— 构建了推理 CLI，使用训练好的 checkpoint 将新中文文本翻译为韩文并导出为 CSV。

**当前模型。** early-stopping run 的 `checkpoint-48000`，beam search（`num_beams=4`）解码。held-out test split（seed 42，训练和 checkpoint 选择中均未见过）：

| 指标 | 分数 |
| --- | --- |
| BLEU（空格分词） | 0.325 |
| chrF (max_n=6, β=2) | 0.590 |
| Glossary preservation (no-space) | 0.954 |
| Glossary preservation (exact) | 0.950 |

**能力阶梯**（相同 test split，全程 beam=4 解码）：

| 阶段 | BLEU | chrF | Preservation (no-space) |
| --- | --- | --- | --- |
| Base NLLB-600M *（微调前基线 —— 无 marker）* | 0.009 | 0.226 | 0.323 |
| Fine-tuned `checkpoint-48000`，beam=4 **（当前模型）** | **0.325** | **0.590** | **0.954** |

![性能对比：Base vs. Fine-tuned NLLB-200](docs/figures/capability_comparison.png)

微调 + 数据清洗带来的净增益：同档 beam=4 解码下 **+0.316 BLEU（~34×）**；glossary preservation 从 ~32% 升至 ~95%。Base 模型能生成听起来流畅的韩文，但完全无法命中游戏专有术语和角色名称，微调与数据清洗共同解释了全部差距。

## 当前范围

- 仓库只保留最终训练语料和术语表，不提交敏感 raw Excel/CSV 输入。
- 使用本地 semantic pipeline 清洗中文-韩文游戏术语表。
- 基于 `facebook/nllb-200-*` 系列模型进行游戏本地化语料微调。
- 使用统一的 `<start>...<end>` 特殊 token 在翻译中标记术语。
- T&N+R 和 code-id code/tag 保护只作为历史实验保留，不再作为当前主线。
- 将翻译结果导出为 Excel/CSV，并评估 BLEU 与术语保留率。

## 技术背景

**术语 marker（`<start>...<end>`）方法论。** 为在翻译中保留游戏专有术语，管道采用源端术语注入（source-side terminology injection）方案。该方案基于 Dinu et al.（ACL 2019）*"Training Neural Machine Translation to Apply Terminology Constraints"*：在源中文文本中，将与 glossary 匹配的部分用 `<start>...<end>` 特殊 token 对包裹，并以此形式进行训练。这样模型通过上下文学习到一种软约束，能在目标韩文中自然复现对应术语，而不需要在解码阶段强制插入 token（hard constrained decoding），从而不损伤翻译流畅度。采用单一 marker 形式是为了将 tokenizer 词表扩展控制在最小范围。

**评估指标。** BLEU（Papineni et al., 2002）是基于 n-gram 精确率的标准 MT 指标。根据 Google Cloud Translate 的 [BLEU 分数解读指南](https://cloud.google.com/translate/docs/advanced/bleu-scores)，0.30~0.40 区间对应"可理解到良好的翻译（Understandable to good translations）"，本模型的 0.325 属于该区间。对于形态丰富的韩语，空格级分词会低估实际翻译质量，因此同时报告 chrF（字符级 n-gram F-score，Popović 2015）作为补充指标，chrF 在词形变化丰富的语言中与人类判断的相关性更高。Glossary preservation 是领域专有指标，直接检测译文中是否出现术语表条目，同时报告精确匹配（exact）和去空格匹配（no-space），以区分真正的术语遗漏与无害的空格差异。

**过拟合防控。**

1. **Early stopping** —— 在 validation split 上监测 BLEU + chrF + glossary preservation 复合分数，无改善时提前终止训练并自动选出最优 checkpoint。
2. **确定性 8:1:1 数据划分** —— 以 seed 42 固定 train/validation/test 分割，test split 仅用于最终报告，不参与 checkpoint 选择，防止信息泄漏。
3. **数据质量门禁** —— 污染行、不一致术语等噪声会成为过拟合信号，因此只有通过 strict gate 的语料才进入训练。

## 仓库结构

```text
.
├── README.md
├── README.en.md
├── README.zh-CN.md
├── CLAUDE.md
├── .env.example
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
│   ├── train_model.py
│   └── plot_training_loss.py
├── src/
│   └── longtu_translation_pipeline/
├── tests/
└── docs/
    ├── architecture/data-cleaning-pipeline.md
    └── notebooks/inventory.md
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
| `configs/training/default.json` | smoke/dry-run 用基础训练配置，声明数据路径、语言码、模型名、输出目录和基础参数。 |
| `configs/training/step10k.json` | Full-data 10k step 训练 profile，显式声明步数、checkpoint、eval 和优化器参数。 |
| `configs/training/earlystop.json` | Early-stopping 训练 profile，生成了当前最终模型（`checkpoint-48000`）。 |
| `configs/inference/default.json` | 推理配置，声明模型路径、输入/输出路径、语言码和生成参数。 |
| `configs/evaluation/default.json` | 评估配置，声明翻译结果 CSV、glossary、BLEU 口径和本地报告目录。 |
| `scripts/cleanup_common.py` | segment/glossary 清洗 pipeline 共用的通用工具函数。 |
| `scripts/llm_common.py` | OpenAI-compatible Chat Completions API 调用的公共 client 模块。 |
| `scripts/sweep_inference_params.py` | 扫描 beam width 等推理参数以寻找最优解码配置的 CLI。 |
| `scripts/glossary_semantic_pipeline.py` | 本地 glossary semantic 清洗 pipeline，使用 Stanza、jieba、kiwipiepy、wordfreq 与 `BAAI/bge-m3`。 |
| `scripts/glossary_llm_cleanup_pipeline.py` | 云端 OpenAI-compatible glossary 激进清洗入口，只允许删除术语并写本地 ignored review。 |
| `scripts/evaluate_translation.py` | 翻译结果评估 CLI，计算 BLEU 与 glossary preservation，不加载模型。 |
| `scripts/segments_cleaning_pipeline.py` | 本地 segments 语义清洗 pipeline，默认 dry-run 生成 review CSV。 |
| `scripts/segments_llm_cleanup_pipeline.py` | 云端 OpenAI-compatible segments 全量清洗入口，允许经本地校验的韩文改写。 |
| `scripts/segments_glossary_cross_cleaning_pipeline.py` | glossary/segments 交叉清洗 CLI，删除高置信术语冲突训练行并输出本地 review。 |
| `scripts/train_model.py` | 训练 CLI；支持配置 dry-run、本地 tiny tokenizer smoke、真实 tokenizer + tiny Trainer smoke、真实 NLLB 模型 1-step smoke、pilot training 和正式 run 目录训练。 |
| `scripts/run_inference.py` | 推理 CLI；支持配置 dry-run 和基于真实 checkpoint 的小样本 generation。 |
| `scripts/plot_training_loss.py` | 从 `trainer_state.json` 绘制训练/评估损失曲线的 CLI；传入 `--output` 可保存为文件。 |
| `src/longtu_translation_pipeline/text_protection.py` | 可测试的术语 marker 保护纯函数模块。 |
| `src/longtu_translation_pipeline/training_metrics.py` | 训练期间复合质量指标计算与最优 checkpoint 选择逻辑。 |
| `src/longtu_translation_pipeline/config.py` | 训练/推理 JSON 配置的 dataclass 解析和校验。 |
| `src/longtu_translation_pipeline/training.py` | 可导入的训练数据准备和 Trainer 链路 API。 |
| `src/longtu_translation_pipeline/inference.py` | 可导入的推理输入计划 dry-run API。 |
| `src/longtu_translation_pipeline/evaluation.py` | 可导入的 BLEU 与 glossary preservation 评估 API。 |
| `docs/notebooks/inventory.md` | 2023 年实验 Notebook 的时间线、用途与退役记录。如需查阅原始 Notebook 文件，请检出 git 标签 `notebooks-retire`。 |
| `docs/architecture/data-cleaning-pipeline.md` | 数据清洗规则说明，包含样式 tag、结构化字符串、短碎片、目标语言污染和 strict gate 示例。 |
| `requirements-training.txt` | 训练链路依赖，包含 transformers、accelerate、sentencepiece 与 CUDA PyTorch。 |

## 运行环境

建议使用 Windows 或 Linux 的 Python 虚拟环境。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt           # 数据清洗与评估
pip install -r requirements-training.txt  # 训练/推理时额外安装（含 CUDA 13.2 PyTorch）
```

Stanza 语言模型、Hugging Face 缓存、微调产物和 raw 数据均通过 `.gitignore` 排除在 Git 之外。

## 基本流程

训练数据入口是两个最终 CSV。Raw Excel/CSV 文件不提交到仓库。

- `data/segments.csv` —— 中韩并行语料
- `data/glossary.csv` —— 游戏术语表

**Glossary 清洗** —— 先下载 Stanza 模型，再运行本地 pipeline。

```powershell
$env:STANZA_RESOURCES_DIR="D:\longtu-translation-pipeline\venv\stanza_resources"
venv\Scripts\python.exe -c "import stanza; stanza.download('zh', model_dir=r'D:\longtu-translation-pipeline\venv\stanza_resources'); stanza.download('ko', model_dir=r'D:\longtu-translation-pipeline\venv\stanza_resources')"
$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"
venv\Scripts\python.exe scripts\glossary_semantic_pipeline.py
```

本地规则不足时，可追加云端 LLM delete-only 清洗。

```powershell
$env:OPENAI_API_KEY="<your-key>"; $env:LLM_MODEL="<your-model>"
venv\Scripts\python.exe scripts\glossary_llm_cleanup_pipeline.py --apply
```

**Segment 清洗** —— 先 dry-run 确认，再 apply。训练前必须通过 strict-check。

```powershell
venv\Scripts\python.exe scripts\segments_cleaning_pipeline.py --dry-run
venv\Scripts\python.exe scripts\segments_cleaning_pipeline.py --apply
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check
```

如需 LLM 全量复核：

```powershell
$env:OPENAI_API_KEY="<your-key>"; $env:LLM_MODEL="<your-model>"
venv\Scripts\python.exe scripts\segments_llm_cleanup_pipeline.py --dry-run
# 确认 review 后：--apply
```

各类清洗的详细规则和示例见 [docs/architecture/data-cleaning-pipeline.md](docs/architecture/data-cleaning-pipeline.md)。

**训练** —— 使用 `earlystop.json`（确定性 8:1:1 划分，seed 42，early-stopping）。

```powershell
venv\Scripts\python.exe scripts\train_model.py --config configs\training\earlystop.json --train --run-name <run-name>
```

快速 smoke/dry-run 验证：

```powershell
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --dry-run
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --nllb-smoke-test --smoke-rows 2
```

**推理** —— 指定训练 run 目录。

```powershell
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate-test --run-dir <run-dir>
```

**评估** —— 一次性报告 BLEU、chrF 与 glossary preservation。

```powershell
venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\generation_report.json --input <generated-csv>
```

## 更大的模型 (1.3B / 3.3B)

NLLB-200 还提供更大的基座（`nllb-200-1.3B`、`nllb-200-3.3B`）。更大的 dense MT 模型通常质量更好（边际收益递减），但**并不保证**，而且我们**没有**在本项目微调后的 zh-CN → ko 任务上基准测试过 1.3B/3.3B —— 因此这里不给出预期质量提升的数字。但成本是可预测的：

| | 600M（当前） | 1.3B | 3.3B |
| --- | --- | --- | --- |
| 参数量 | ~0.6B | ~1.3B (~2.1×) | ~3.3B (~5.4×) |
| 推理延迟（dense，与参数量成正比） | 1× | ~2.1× | ~5.4× |
| 全量微调显存（AdamW，混合精度） | 适配 16 GB（本项目在 RTX 4070 Ti SUPER 上用了 ~14.9 GB） | ~21 GB —— 超过 16 GB | ~53 GB —— 远超单张 16 GB GPU |

在本项目使用的 16 GB GPU 上，不借助省显存技术（gradient checkpointing、8-bit optimizer、LoRA、offload）**1.3B 全量微调放不下**，而 **3.3B 需要更大显存或多卡**。叠加当前 `num_beams=4` 默认值（已是 greedy 的 ~4×），3.3B 推理成本约为最初 600M greedy 的 ~21×。

来源：参数量与 ~17.6 GB 的 3.3B 磁盘 checkpoint 大小来自 Hugging Face 模型卡（[600M](https://huggingface.co/facebook/nllb-200-distilled-600M)、[1.3B](https://huggingface.co/facebook/nllb-200-distilled-1.3B)、[3.3B](https://huggingface.co/facebook/nllb-200-3.3B)）；显存数字基于本项目 600M 实测（`run_manifest.json`）加标准 AdamW 显存估算（权重 + 梯度 + optimizer state 约 16 bytes/参数）。

## 参考文档

- [架构决策记录 (ADR)](docs/decisions/adr/README.md)
- [Notebook inventory](docs/notebooks/inventory.md)
- [Agent 宪法 (CLAUDE.md)](CLAUDE.md)
