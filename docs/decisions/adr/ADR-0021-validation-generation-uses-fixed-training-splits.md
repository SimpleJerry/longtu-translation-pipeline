# ADR-0021：验证集生成使用固定的训练拆分

- 状态：已接受
- 日期：2026-05-25

## 背景

RF-006-P6 样本生成验证了检查点加载和生成结构，但从 `data/segments.csv` 的前 N 行生成翻译，而非从正式训练运行写入的确定性验证集拆分生成。使用临时行切片而非固定拆分会破坏可复现性：同一语段可能同时出现在训练集和评估集中。

## 决策

验证集生成（`scripts/run_inference.py --generate-validation`）必须从正式运行清单中读取 `splits/validation.csv`（参见 ADR-0020），而非从 `data/segments.csv` 取前 N 行。

默认检查点为运行目录中最新的数字编号检查点；可通过 `--checkpoint` 覆盖。

生成的验证集 CSV 保持 RF-007 兼容的 `segment_id,source,references,candidates` 模式（参见 ADR-0016），并保留为本地忽略产物。

## 后果

- 验证集生成与训练运行的数据拆分确定性绑定。
- 验证集拆分用于检查点选择（参见 ADR-0023）。
- 测试集拆分保留用于最终保留测试集报告。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-006-P8、RF-007-P3
- 相关代码：`scripts/run_inference.py`、`src/longtu_translation_pipeline/inference.py`
