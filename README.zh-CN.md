# LongtuKorea Translation Model

[한국어](README.md) | [English](README.en.md) | [中文](README.zh-CN.md)

这是 LongtuKorea 的游戏本地化机器翻译实验仓库。当前重点是基于 NLLB 的简体中文（`zh-CN`）到韩语（`ko`）微调流程，同时覆盖术语匹配、代码/标签保护、翻译结果生成、BLEU 评估、术语与代码保留率检查。

这份 README 用来梳理当前仓库的真实状态。它还不是一个已经工程化封装好的生产项目，更接近“数据处理脚本 + 研究 notebook”的实验工作区。

## 当前范围

- 仓库只保留最终训练语料和术语表，不提交敏感 raw Excel/CSV 输入。
- 使用本地 semantic pipeline 清洗中文-韩文游戏术语表。
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
├── data/
│   ├── glossary.csv
│   ├── segments.csv
│   └── review/                # 本地生成，Git 忽略
├── configs/
│   ├── glossary/
│   └── segments/
├── scripts/
│   ├── glossary_semantic_pipeline.py
│   └── segments_cleaning_pipeline.py
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

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `data/segments.csv` | 最终正文/句段训练语料，只包含 `segment_id`、`zh-CN` 与 `ko`。 |
| `data/glossary.csv` | 最终中文-韩文游戏术语表，只包含 `term_id`、`zh-CN` 与 `ko`。 |
| `data/review/` | 本地数据清洗审计和人工核对 CSV，默认不提交。 |
| `configs/glossary/` | glossary 清洗的 seed、词表和规则配置。 |
| `configs/segments/` | segments 清洗的结构化字符串拆分、term/entity seed 和语义阈值配置。 |
| `scripts/glossary_semantic_pipeline.py` | 本地 glossary semantic 清洗 pipeline，使用 Stanza、jieba、kiwipiepy、wordfreq 与 `BAAI/bge-m3`。 |
| `scripts/segments_cleaning_pipeline.py` | 本地 segments 语义清洗 pipeline，默认 dry-run 生成 review CSV。 |
| `nllb-fine-tune_all.ipynb` | NLLB 微调基础流程。 |
| `T&N method.ipynb` | Terminology and Notation 方案，实验术语特殊 token。 |
| `T&N+R preprocess.ipynb` | 包含术语与代码保护的预处理实验。 |
| `T&N+R method.ipynb` | 同时应用术语、标记和返回码保护的训练实验。 |
| `model-generation.ipynb` | 使用微调模型生成翻译结果。 |
| `train_eval_loss_picture.ipynb` | 从训练日志生成 train/eval loss 曲线。 |

## 运行环境

建议使用 Windows 或 Linux 的 Python 虚拟环境。`requirements.txt` 当前记录了 CUDA 13.2 版本 PyTorch 与本地术语清洗所需依赖。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
jupyter lab
```

注意：

- Stanza 中文/韩文模型、Hugging Face embedding 缓存放在本地虚拟环境目录下，不提交到 Git。
- BLEU notebook 使用 `nltk.translate.bleu_score`，如果环境里没有 `nltk`，需要另行安装。
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

该 pipeline 会先剥离 `<c=...>` 等表现层样式标签并解开对称外层包装，再使用 Stanza、jieba、kiwipiepy 和 `BAAI/bge-m3` 判断 term/entity-like segment；placeholder 行默认保留，只做 mismatch 审计。该命令不会改写 `data/segments.csv`，只会在本地 `data/review/segments/` 下生成审计 CSV。人工确认后再使用 `--apply` 重写最终语料。

训练 notebook 中的语言列按 NLLB 语言代码转换：

```text
zh-CN -> zho_Hans
zh-TW -> zho_Hant
en    -> eng_Latn
ja    -> jpn_Jpan
ko    -> kor_Hang
```

使用 `T&N method.ipynb` 或 `T&N+R method.ipynb` 执行术语/代码保护预处理与微调，再使用生成和评估 notebook 检查 BLEU、术语保留率和代码保留率。

## 架构与重构入口

长期重构待办不放在 README 中维护。请查看：

- [重构 backlog](docs/refactor/backlog.md)
- [重构决策记录](docs/refactor/decisions.md)
- [AI/Codex 工作规则](AGENTS.md)
