# ADR-0023：正式实验使用保留测试拆分（8:1:1，seed=42）

- 状态：已接受
- 日期：2026-05-25

## 背景

首次 10k 训练运行（RF-006-P9）在验证集拆分上报告了指标。验证集用于训练时的检查点选择；在验证集数据上报告最终模型性能是不可接受的，因为检查点选择可能过拟合于验证集。保留测试集拆分是 NMT 领域报告最终模型质量的标准做法。

## 决策

正式实验使用确定性的 **train / validation / test = 8:1:1 拆分**，**seed 42**。

- 验证集用于训练时评估和检查点观察。
- 测试集**仅保留用于最终性能报告**。
- 8:1:1 / seed=42 契约为 RF-006-P11 / RF-007-P3 可复现性锁定；变更拆分需要新任务和新 ADR。
- 测试集**每个模型仅使用一次**；通过反复迭代测试结果寻找"更好"的检查点属于数据泄漏。

## 后果

- `configs/training/default.json` 和 `configs/training/step10k.json` 均使用 8:1:1 / seed=42。
- RF-006-P9 的仅验证集报告被明确标记为历史工程产物。
- `scripts/run_inference.py --generate-test` 从运行清单中读取测试集拆分（参见 ADR-0020）。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-006-P10、RF-007-P3
- 相关代码：`src/longtu_translation_pipeline/training.py`、`scripts/run_inference.py`
