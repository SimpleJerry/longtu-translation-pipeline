# ADR-0008：词汇表pipeline以最终词汇表为基准

- 状态：已接受
- 日期：2026-05-24

## 背景

词汇表语义pipeline的早期版本以历史审计 CSV 作为基准读取。历史审计基准和原始源文件不被提交，因为它们是中间数据或敏感数据。这使得pipeline对于仅有已提交版本库的人员无法复现。

## 决策

词汇表语义pipeline将当前 `data/glossary.csv` 作为权威基准读取，并仅将审计 CSV 作为本地忽略产物写入 `data/review/` 下。

附加约束：
- 较长的业务规则列表和阈值存放于 `configs/glossary/`（不硬编码）。
- `segments.csv` SHA256 哈希记录在审计输出中以供追溯，但不得作为必须满足的源代码gate被硬编码。

## 后果

- pipeline可从已提交语料复现，无需外部基准文件。
- `data/review/glossary_*` 下的审计 CSV 是本地产物，每次pipeline运行时重新生成。
- 业务规则可审查且可配置，无需修改代码。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-010、RF-011
- 相关代码：`scripts/glossary_semantic_pipeline.py`、`configs/glossary/`
