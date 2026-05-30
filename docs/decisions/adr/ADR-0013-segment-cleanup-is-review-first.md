# ADR-0013：语段清理以审校为先

- 状态：已接受
- 日期：2026-05-24

## 背景

Seq2seq 语段清理的误报风险高于词汇表清理。短 UI 标签、含机器占位符的结构化字符串以及音译游戏术语，用简单启发式规则可能看起来像噪声，但实际上是有效的训练样本。在没有人工审校步骤的情况下直接应用删除操作，可能在不知不觉中降低语料质量。

## 决策

语段清理pipeline（`scripts/segments_cleaning_pipeline.py`）默认以dry-run模式运行，仅在明确使用 `--apply` 参数时才改写 `data/segments.csv`。

附加约束：
- 术语/实体类删除使用本地语义信号（Stanza 词性、embedding 相似度、游戏领域种子词接近度），而非固定文本长度阈值。
- 表现层标签（`<c=...>`）在保留被包裹文本的同时被去除。
- 对称外层包装器被展开；有效机器占位符被审计，而非删除。
- 结构化元组式字符串在安全对齐时被拆分；仅在解析失败时删除。

## 后果

- 每次清理运行在数据变更之前都会在 `data/review/segments/` 下写入审校 CSV。
- `--apply` 是操作者的主动决策，而非默认行为。
- `configs/segments/` 中的规则无需修改代码即可配置。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-010、RF-013
- 相关代码：`scripts/segments_cleaning_pipeline.py`、`configs/segments/`
- 相关文档：`docs/architecture/data-cleaning-pipeline.md`
