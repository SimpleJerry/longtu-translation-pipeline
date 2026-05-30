# ADR-0028：推理在源端应用术语标记

- 状态：已接受
- 日期：2026-05-26

## 背景

10k 验证集生成暴露了训练/推理不匹配问题：训练数据在中文源文本（以及韩语目标端）上应用了 `<start>...<end>` 术语标记，但推理时输入的是不带标记的原始源文本。这意味着模型在不符合其训练分布的输入上被评估。

## 决策

推理在分词前默认将仅源端 `<start>...<end>` 词汇表标记应用于源文本（推理配置中 `terminology_markers=true`）。

生成的 CSV 在 `source` 列保留**原始源文本**（不含标记）以供人工阅读。标记在分词前于内部应用，但不反映在输出 CSV 的 `source` 字段中。

当评估配置中 `strip_glossary_markers=true` 时，候选文本在报告输出前去除词汇表标记。

## 后果

- `<start>...<end>` 标记使用上的训练/推理输入分布已对齐。
- 输出 CSV 中的源文本仍便于人工阅读（无标记）。
- 生成摘要记录 `source_terminology_markers`、`marked_source_rows` 和 `source_terms_marked` 以供审计。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-006-P8（后续说明）
- 相关代码：`src/longtu_translation_pipeline/inference.py`、`configs/inference/default.json`
