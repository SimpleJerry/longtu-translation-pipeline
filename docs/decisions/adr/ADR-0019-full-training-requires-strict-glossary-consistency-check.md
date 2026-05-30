# ADR-0019：正式训练前须通过严格词汇表一致性检查

- 状态：已接受
- 日期：2026-05-25

## 背景

如果词汇表/语段冲突保留在最终语料中，将污染所有下游的 train、validation 和 test 拆分。若某语段的源端包含保留的词汇表术语，但韩语目标端不含词汇表中对应的韩文形式，则模型会在该术语上接受不一致的信号进行训练。

## 决策

在正式训练或最终保留测试集评估之前，`data/segments.csv` 必须通过严格词汇表一致性检查：

```powershell
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check
```

预期的训练前门控结果为：
```
strict_current_mismatch_rows=0
```

严格清理通过使用真实语段翻译来确定**可强制执行**的词汇表：
- 自然短语变体较多或韩文形式不稳定的术语从词汇表中删除，而非删除良好的句子数据。
- 之后可运行 `--strict-apply` 删除剩余不匹配的语段行，但不得自动改写韩语翻译。

## 后果

- `--strict-check` 是每次正式训练运行和保留测试集评估前的门控。
- 词汇表质量受限于当前语料中实际可强制执行的范围。
- 每轮严格应用后术语统计可能发生变化，可在多轮中运行严格应用。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-012、RF-013
- 相关代码：`scripts/segments_glossary_cross_cleaning_pipeline.py`
- 相关文档：`docs/architecture/data-cleaning-pipeline.md`
