# ADR-0024：评估对空模型输出报告而非报错

- 状态：已接受
- 日期：2026-05-25

## 背景

首次 10k 验证集生成产生了少量空候选行。将空 `candidates` 单元格视为硬性模式错误会完全阻塞完整运行的评估报告，并隐藏一个有价值的模型质量信号：空候选项表明模型失败的情况，这些情况应在摘要中可见。

## 决策

生成翻译 CSV 中的空 `candidates` 单元格是有效的模型输出失败，用于报告，而非模式错误。

评估将空候选项计为：
- 零长度 BLEU 候选项。
- 词汇表未命中。
- 摘要和报告清单中的 `empty_candidate_rows` 计数。

空 `source` 和 `references` 仍为硬性错误，因为它们表明无效的评估输入，而非模型行为。

## 后果

- `scripts/evaluate_translation.py` 不再在空候选单元格上失败。
- 即使模型产生部分空输出，也始终可以生成完整运行报告。
- 空候选率是 `report_manifest.json` 中可见的质量信号。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-007、RF-007-P2
- 相关代码：`src/longtu_translation_pipeline/evaluation.py`、`tests/test_evaluation.py`
