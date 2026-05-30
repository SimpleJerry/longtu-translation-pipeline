# 架构文档

本目录包含系统与pipeline架构文档。

## 文档列表

| 文件 | 说明 |
|------|------|
| [invariants.md](invariants.md) | 项目不变量的权威目录（数据模式、拆分契约、标记形状等），每条不变量均绑定到对应的 ADR。由宪法的「不变量」章节引用。 |
| [data-cleaning-pipeline.md](data-cleaning-pipeline.md) | 数据清理规则说明（附示例）：样式标签、结构化字符串、短片段、目标语言污染、词汇表/语段交叉清理及严格gate。 |

## pipeline总览

完整的端到端pipeline总览（数据清理 → 微调 → 评估 → 推理），请参阅顶层 README 的**项目状态与结果**章节：

- [README.md](../../README.md)（한국어）
- [README.en.md](../../README.en.md)（English）
- [README.zh-CN.md](../../README.zh-CN.md)（中文）
