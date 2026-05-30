# ADR-0027：语段片段与目标污染为训练噪声

- 状态：已接受
- 日期：2026-05-26

## 背景

严格 10k 诊断运行后的验证集样本审查发现了两类无效训练行：
1. 孤立的单字 CJK 片段（如 `艮 -> 간`），无法作为 seq2seq 句子对使用。
2. 韩语目标端仍含中文字符，或完全没有韩文字符的行——不是可靠的翻译样本。

若保留在语料中，这些行会降低未来每次 train/validation/test 拆分的质量。

## 决策

高置信度的非语段片段和韩语侧目标语言污染，在训练前从 `data/segments.csv` 中删除。

永久规则：
- **纯单字 CJK 片段**（`AUTO_REMOVE_NON_SEGMENT_FRAGMENT`）：删除。
- **目标语言污染**（`AUTO_REMOVE_TARGET_LANGUAGE_CONTAMINATION`）：当 `ko` 含 CJK 字符，或 `ko` 非空但不含韩文字符时删除。

目标污染规则对当前语料有意从严：不使用占位符、ID 或版本号白名单。

注意：将 2-3 字短片段从语段迁移至词汇表的一次性操作（RF-013）是针对混合语料的历史修复，**不是定期pipeline步骤**。

## 后果

- 这些删除规则是永久性的，每次 `segments_cleaning_pipeline.py --apply` 均会应用。
- 严格污染策略可能删除部分类 ID 或纯占位符行；用户接受了这一 seq2seq 训练语料质量方面的权衡。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-013
- 相关代码：`scripts/segments_cleaning_pipeline.py`
- 相关文档：`docs/architecture/data-cleaning-pipeline.md`
