# ADR-0016：推理输出保持 RF-007 兼容

- 状态：已接受
- 日期：2026-05-25

## 背景

项目需要生成输出能直接流入现有 BLEU 和词汇表保留率评估器，同时保留与 `data/segments.csv` 的行级关联。考虑了两种模式选项：直接使用评估器现有的 `source,references,candidates` 列，或添加 `segment_id` 以实现行可追溯性。

## 决策

检查点推理以 `segment_id,source,references,candidates` 模式写入 CSV。RF-007 评估读取 `source`、`references` 和 `candidates` 列；`segment_id` 提供行可追溯性。

生成的推理 CSV 是被忽略的 `data/review/inference/` 下的本地产物。

## 后果

- `scripts/run_inference.py` 的生成输出可直接导入 `scripts/evaluate_translation.py`，无需转换。
- `segment_id` 允许在不丢失数据的情况下进行行级调试和样本审查。
- 完整验证集生成和固定拆分选择属于后续 RF-006/RF-007 阶段。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-006-P6、RF-007-P2
- 相关代码：`src/longtu_translation_pipeline/inference.py`、`scripts/run_inference.py`
