# Notebook 清单

本文档记录当前Notebook集合、各Notebook的存在理由及在重构工作中的处理建议。本文档首要目的是建立清单：历史实验在任何删除决定之前均需先归档。

## 时间线概要

- **2023-09：** 基线 NLLB 微调、早期 BLEU/模型测试及首批术语实验。
- **2023-10：** `<start>/<middle>/<end>` 术语保护、分词器/特殊 token 测试、生成实验及训练/评估损失可视化。
- **2023-10-31 至 2023-11-01：** `T&N method_modified`、`<code>` / `<code_id=*>` 保护及首个 `T&N+R` 主工作流。
- **2023-11-03：** `T&N+R` 的词汇表和代码保留准确率Notebook。
- **2023-11-28 至 2023-11-29：** `T&N+R preprocess` 修复及返回码 token 恢复实验。
- **2026-05-19：** 机械性 CSV 引用更新。许多Notebook仍引用已不再提交的中间文件。
- **2026-05-24：** RF-004 清单与归档整理。根目录Notebook已移入 `notebooks/main/`、`notebooks/analysis/` 和 `notebooks/archive/2023-legacy/`。

## 分类

### 主要Notebook

这些Notebook描述了历史主实验路径，在替代模块和 CLI 入口点存在之前应保持可查阅。2026-05-24 RF-005 决定后，T&N+R Notebook已作为废弃历史实验处理，因为当前术语标记政策不再使用 `<middle>` 或 `<code_id=N>`。

| Notebook | 时间线 | 实验意义 | 当前依赖状态 | 建议 | 替代路径 |
| --- | --- | --- | --- | --- | --- |

### 分析Notebook

| Notebook | 时间线 | 实验意义 | 当前依赖状态 | 建议 | 替代路径 |
| --- | --- | --- | --- | --- | --- |
| `notebooks/analysis/train_eval_loss_picture.ipynb` | 创建于 2023-10-26；更新于 2023-11-02。 | 用于可视化训练/评估损失曲线的工具Notebook。 | 依赖被忽略的微调模型输出下的本地 `trainer_state.json`。 | 保留为辅助分析记录。 | 若仍有用，RF-006 或 RF-007 可用小型报告脚本替代。 |

### 已归档历史Notebook

这些Notebook保留用于历史可溯源性，不应视为当前工作流。

| Notebook | 时间线 | 实验意义 | 当前依赖状态 | 建议 | 替代路径 |
| --- | --- | --- | --- | --- | --- |
| `notebooks/archive/2023-legacy/nllb-fine-tune_all.ipynb` | 首次提交于 2023-09-06；最后实质更新于 2023-09-18。 | 基线 NLLB 微调工作流。 | 引用旧版 `all_files_merged.csv` 及当前未提交的本地训练配置/状态。 | 归档（2026-05-27 从 main 移出）。 | RF-006 应替代训练配置和启动流程。 |
| `notebooks/archive/2023-legacy/T&N+R preprocess.ipynb` | 源于 2023 年末的标签/代码预处理实验；主要创建于 2023-11-28。 | 针对术语、标签及代码/返回 token 保护的废弃历史预处理实验。 | 使用当前 `data/glossary.csv`；仍含模板化的本地 CSV/日志引用。 | 归档（2026-05-27 从 main 移出）。 | RF-005 已用纯 `<start>...<end>` 替代当前术语标记逻辑。 |
| `notebooks/archive/2023-legacy/T&N+R method.ipynb` | `T&N+R` 主方法形成于 2023-11-01 前后；更新至 2023-11-29，并于 2026 年机械性更新。 | 废弃的术语/代码感知训练历史实验。 | 使用当前 `data/glossary.csv`；仍引用未提交的旧版合并/已标记 CSV 文件。 | 归档（2026-05-27 从 main 移出）。 | RF-006 应在不使用 T&N+R 假设的情况下定义未来训练路径。 |
| `notebooks/archive/2023-legacy/model-generation.ipynb` | 约创建于 2023-10-27；于 2026 年机械性更新。 | 微调模型的推理/生成入口。 | 引用旧版验证/已标记 CSV 路径及本地微调模型输出。 | 归档（2026-05-27 从 main 移出）。 | RF-006 应替代模型路径和推理配置。 |
| `notebooks/archive/2023-legacy/T&N+R method glossary accuracy testing.ipynb` | 创建于 2023-11-03；于 2026 年机械性更新。 | `T&N+R` 方法的废弃词汇表保留准确率检查。 | 引用当前未提交的历史 `tests/files/translation_result...` 输出。 | 归档（2026-05-27 从 main 移出）。 | RF-007 应为简化标记政策自动化词汇表保留指标。 |
| `notebooks/archive/2023-legacy/T&N+R method code accuracy testing.ipynb` | 创建于 2023-11-03；于 2026 年机械性更新。 | `T&N+R` 方法的废弃代码 token 保留准确率检查。 | 引用当前未提交的历史 `tests/files/translation_result...` 输出。 | 归档（2026-05-27 从 main 移出）。若代码 token 保护仍已废弃，RF-007 后可作为删除候选。 | RF-007 应替代。 |
| `notebooks/archive/2023-legacy/T&N method.ipynb` | 首次提交于 2023-09-06；演进至 2023-10。 | 使用词汇表特殊 token 的早期仅术语工作流。 | 使用当前 `data/glossary.csv`；引用未提交的旧版合并 CSV 文件。 | 归档，非主路径。 | 已被 `T&N+R` Notebook及未来 RF-005 模块取代。 |
| `notebooks/archive/2023-legacy/T&N method_modified.ipynb` | 创建于 2023-10-31；约更新于 2023-11-01。 | 从纯术语保护向代码保护过渡的实验。 | 引用未提交的旧版合并/已标记 CSV 文件。 | 归档，非主路径。 | 已被 `T&N+R preprocess` 和 RF-005 取代。 |
| `notebooks/archive/2023-legacy/T&N method glossary accuracy testing.ipynb` | 源于早期测试流程；最后机械性更新于 2026-05-19。 | `T&N` 的历史词汇表保留评估。 | 引用未提交的旧版翻译结果 CSV。 | 归档，RF-007 后可作为删除候选。 | 已被 `T&N+R` 词汇表评估和 RF-007 取代。 |
| `notebooks/archive/2023-legacy/T&N method code accuracy testing.ipynb` | 创建于 2023-11-01；于 2026 年机械性更新。 | `T&N` 的历史代码保留评估。 | 引用未提交的旧版翻译结果 CSV。 | 归档，RF-007 后可作为删除候选。 | 已被 `T&N+R` 代码评估和 RF-007 取代。 |
| `notebooks/archive/2023-legacy/special_token_test.ipynb` | 创建于 2023-10-24，为一次性实验。 | 分词器/特殊 token 行为测试。 | 不依赖已提交数据，但属于探索性内容而非工作流文档。 | 归档，固件测试存在后可作为删除候选。 | RF-005 可用分词器/保护测试替代。 |
| `notebooks/archive/2023-legacy/return code tokens.ipynb` | 创建于 2023-11-29；于 2026 年机械性更新。 | 一次性返回码 token 恢复实验。 | 引用本地翻译 CSV 及未提交的 `{0}_code_logs.pkl` 输出。 | 归档，RF-005 后可作为删除候选。 | RF-005 应用往返恢复测试替代。 |

## 删除候选

RF-004 第一轮整理中未删除任何Notebook。以下文件是后续仅删除任务的候选，待本清单审查后再处理：

- `notebooks/archive/2023-legacy/special_token_test.ipynb`
- `notebooks/archive/2023-legacy/return code tokens.ipynb`
- `notebooks/archive/2023-legacy/T&N method.ipynb`
- `notebooks/archive/2023-legacy/T&N method_modified.ipynb`
- `notebooks/archive/2023-legacy/T&N method glossary accuracy testing.ipynb`
- `notebooks/archive/2023-legacy/T&N method code accuracy testing.ipynb`
- `notebooks/archive/2023-legacy/T&N+R method.ipynb`
- `notebooks/archive/2023-legacy/T&N+R method code accuracy testing.ipynb`
- `notebooks/archive/2023-legacy/T&N+R method glossary accuracy testing.ipynb`
- `notebooks/archive/2023-legacy/T&N+R preprocess.ipynb`
- `notebooks/archive/2023-legacy/nllb-fine-tune_all.ipynb`
- `notebooks/archive/2023-legacy/model-generation.ipynb`

## 已知依赖缺口

- 多个Notebook仍引用已删除的中间语料文件，如 `all_files_merged.csv`、`all_files_merged_zh-CN_ko.csv`、已标记 CSV 输出、历史 `translation_result...csv` 文件及被忽略的训练输出。
- 本清单记录缺失引用，但不修复Notebook逻辑。路径修复、模块提取、配置迁移及自动化评估属于 RF-005、RF-006 和 RF-007 的工作范围。
- 原始数据和审校/中间输出有意不提交；最终已提交数据存放于 `data/segments.csv` 和 `data/glossary.csv`。
