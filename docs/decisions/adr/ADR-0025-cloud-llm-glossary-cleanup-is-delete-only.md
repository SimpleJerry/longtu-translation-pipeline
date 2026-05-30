# ADR-0025：云端 LLM 词汇表清理仅允许删除

- 状态：已接受
- 日期：2026-05-26

## 背景

本地词汇表清理是首选，因为它可复现且不会将公司术语发送至本地机器以外。然而，确定性规则难以处理的剩余语义噪声——通用词、短语和错误词对——可能需要 LLM 级别的判断。

用户接受使用兼容 OpenAI 的云端 LLM 进行激进的净化处理，但附加了一个关键约束：新翻译将在 `data/glossary.csv` 中产生未经审查的术语冲突。

## 决策

可选的云端 LLM 词汇表清理（`scripts/glossary_llm_cleanup_pipeline.py`）可对当前 `data/glossary.csv` 行进行分类，但**只能删除行**。不得：
- 改写韩语值。
- 添加新术语。
- 合并术语。
- 从版本库中选用硬编码的模型。

所需环境变量：`OPENAI_API_KEY`、`LLM_MODEL`。
可选：`OPENAI_BASE_URL`。

任何 LLM 删除操作后，须重新运行严格词汇表/语段gate（参见 ADR-0019），并在训练前重新生成训练拆分。

## 后果

- 词汇表净化是单向的：行只能被删除，不能被修改。
- 审校产物保留在被忽略的 `data/review/llm_glossary_cleanup/` 下。
- 模型名称是运行时参数，而非已提交的常量。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-014、RF-029
- 相关代码：`scripts/glossary_llm_cleanup_pipeline.py`
- 相关文档：`docs/architecture/data-cleaning-pipeline.md`
