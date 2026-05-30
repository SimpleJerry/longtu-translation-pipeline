# ADR-0029：词汇表保留率同时报告精确匹配和无空格指标

- 状态：已接受
- 日期：2026-05-26

## 背景

严格清理（参见 ADR-0019）将精确匹配和无空格精确韩语保留均视为通过。然而，评估指标最初只报告精确保留率。这意味着像 `추가피해`（无空格）这样的有效翻译，当词汇表条目为 `추가 피해`（有空格）时会被评为失败——即使对于一个良好清洗的语料，也会产生误导性的低保留分数。

## 决策

RF-007 并排报告**两种**词汇表保留率指标：

- `glossary_preservation_rate`：精确匹配（向后兼容保留）。
- `glossary_preservation_rate_nospace`：无空格精确匹配（避免因有效的韩语空格变体而扣分）。

在判断跨韩语空格差异的术语保留时，使用 `glossary_preservation_rate_nospace`。需要严格字符级相等时，使用 `glossary_preservation_rate`。

## 后果

- 评估报告包含两项指标。
- 早停（参见 ADR-0031）使用 `eval_glossary_preservation_nospace` 作为复合指标的两个组成部分之一。
- 读取 `glossary_preservation_rate` 的现有代码无需修改，继续正常工作。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-007（后续说明）、RF-006-P13
- 相关代码：`src/longtu_translation_pipeline/evaluation.py`
