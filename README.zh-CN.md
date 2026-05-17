# LongtuKorea Translation Model

[한국어](README.md) | [English](README.en.md) | [中文](README.zh-CN.md)

这是 LongtuKorea 的游戏本地化机器翻译实验仓库。当前重点是基于 NLLB 的简体中文（`zh-CN`）到韩语（`ko`）微调流程，同时覆盖术语匹配、代码/标签保护、翻译结果生成、BLEU 评估、术语与代码保留率检查。

这份 README 用来梳理当前仓库的真实状态。它还不是一个已经工程化封装好的生产项目，更接近“数据处理脚本 + 研究 notebook”的实验工作区。

## 当前范围

- 清洗多语言 Excel 原始数据，并合并为语言对 CSV。
- 基于 `facebook/nllb-200-*` 系列模型进行游戏本地化语料微调。
- 使用 `<start>`、`<middle>`、`<end>` 特殊 token 在翻译中保护术语。
- 使用 `<code_id=*>` token 实验占位符、返回码、游戏 UI 标签保护。
- 将翻译结果导出为 Excel/CSV，并评估 BLEU、术语保留率和代码保留率。

## 仓库结构

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

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `data/data-cleaning-and-merging.py` | 读取多个 Excel 文件和 sheet，标准化语言列，生成总合并文件与语言对 CSV。 |
| `data/input/` | 原始游戏脚本和术语表 Excel 文件。 |
| `glossary_all.xlsx` | 中文-韩文术语实验使用的合并术语数据。 |
| `nllb-fine-tune_all.ipynb` | NLLB 微调基础流程。 |
| `T&N method.ipynb` | Terminology and Notation 方案，实验术语特殊 token。 |
| `T&N+R preprocess.ipynb` | 包含术语与代码保护的预处理实验。 |
| `T&N+R method.ipynb` | 同时应用术语、标记和返回码保护的训练实验。 |
| `model-generation.ipynb` | 使用微调模型生成翻译结果。 |
| `model-generation-manual.ipynb` | 使用手动解码方式生成翻译结果，用于保留特殊 token。 |
| `tests/BLEU-score-calculating.ipynb` | 计算生成结果与 reference 翻译之间的 BLEU。 |
| `train_eval_loss_picture.ipynb` | 从训练日志生成 train/eval loss 曲线。 |

## 运行环境

建议使用 Windows 或 Linux 的 Python 虚拟环境。`requirements.txt` 当前固定了 CUDA 11.8 版本的 PyTorch，用于 GPU 训练。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
jupyter lab
```

注意：

- 如果 `torch==2.0.1+cu118` 安装失败，可能需要单独指定 PyTorch CUDA 11.8 wheel index。
- BLEU notebook 使用 `nltk.translate.bleu_score`，如果环境里没有 `nltk`，需要另行安装。
- 大模型、微调输出、翻译结果和数据清洗输出已通过 `.gitignore` 排除。

## 基本流程

1. 将原始 Excel 文件放在 `data/input/` 下。
2. 在 `data/` 目录中运行数据合并脚本。

```powershell
cd data
python data-cleaning-and-merging.py
```

3. 检查生成的主要产物。

```text
data/output/
data/all_files_merged.xlsx
data/all_files_merged.csv
data/output/all_files_merged_zh-CN_ko.csv
```

4. 在训练 notebook 中将语言列转换为 NLLB 语言代码。

```text
zh-CN -> zho_Hans
zh-TW -> zho_Hant
en    -> eng_Latn
ja    -> jpn_Jpan
ko    -> kor_Hang
```

5. 使用 `T&N method.ipynb` 或 `T&N+R method.ipynb` 执行术语/代码保护预处理与微调。
6. 使用 `model-generation.ipynb` 或 `model-generation-manual.ipynb` 生成翻译结果。
7. 通过 BLEU、术语准确率、代码准确率相关 notebook 检查质量。

## 当前限制

- 核心逻辑分散在 notebook 中，复用和自动化比较困难。
- 数据路径、模型路径、语言对和训练参数都直接写在代码里。
- 测试目前是评估 notebook，不是自动化 unit test。
- 原始数据和实验产物的版本管理规则还不清晰。
- `requirements.txt` 固定的是完整实验环境，后续应拆分训练、推理、文档等依赖。

## 重构方向

复制到新仓库时，建议采用以下结构：

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

建议优先级：

1. 将 Excel 合并、术语标记、代码标记逻辑迁移到 `src/` 模块。
2. 将语言代码映射和路径配置拆到 YAML config。
3. notebook 保留为实验记录，可重复执行流程迁移为 CLI script。
4. 为术语保留、代码保留、标签保留逻辑增加 unit test。
5. 明确训练和推理产物的保存规则。
