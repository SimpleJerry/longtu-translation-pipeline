# 不变量

本文档是项目不变量的权威目录——即宪法
（[CLAUDE.md](../../CLAUDE.md)）**不变量**章节所引用的各项契约。
每条不变量均由一个 ADR 确立，未经新的 ADR 超越即不得变更。
在被明确废弃之前，请将每条条目视为约束。

| 不变量 | 契约内容 | ADR |
|--------|----------|-----|
| **数据模式** | `data/segments.csv` = `segment_id,zh-CN,ko`；`data/glossary.csv` = `term_id,zh-CN,ko`。仅提交最终语料和配置文件；检查点、运行产物、审校 CSV 及模型缓存保持 Git 忽略。 | [ADR-0004](../decisions/adr/ADR-0004-csv-in-git-raw-xlsx-outside-git-tracking.md)、[ADR-0017](../decisions/adr/ADR-0017-generation-evaluation-reports-are-local-artifacts.md) |
| **拆分契约** | 确定性 train/validation/test = 8:1:1，seed 42；正式运行写入拆分产物及携带 `segments_sha256` 的运行清单。 | [ADR-0020](../decisions/adr/ADR-0020-formal-training-runs-require-split-artifacts-and-manifests.md)、[ADR-0023](../decisions/adr/ADR-0023-formal-experiments-use-held-out-test-splits.md) |
| **保留测试集** | 测试拆分在验证集上完成检查点选择后仅评估一次。反复迭代测试数字即为数据泄漏。 | [ADR-0023](../decisions/adr/ADR-0023-formal-experiments-use-held-out-test-splits.md) |
| **术语标记** | 仅使用单一 `<start>...<end>` 形式；`<middle>` 和 `<code_id=N>` 已废弃。 | [ADR-0010](../decisions/adr/ADR-0010-text-protection-uses-single-segment-term-markers.md) |
| **严格词汇表gate** | 正式训练前，词汇表与语段的严格一致性检查必须通过。 | [ADR-0019](../decisions/adr/ADR-0019-full-training-requires-strict-glossary-consistency-check.md) |
| **LLM 清理政策** | 云端词汇表清理仅允许删除；语段清理仅在通过所有本地验证后才可改写韩语目标端。 | [ADR-0025](../decisions/adr/ADR-0025-cloud-llm-glossary-cleanup-is-delete-only.md)、[ADR-0026](../decisions/adr/ADR-0026-cloud-llm-segment-cleanup-may-rewrite-korean-with-local-guards.md) |
| **检查点选择** | 正式训练在复合指标上执行早停；已发布检查点通过在完整验证集上重新排序选出，而非使用训练器循环内的自动最优检查点。 | [ADR-0031](../decisions/adr/ADR-0031-formal-training-uses-early-stopping-on-composite-metric.md) |
| **公开兼容性** | 除非 ADR 明确授权破坏性变更，否则保留已记录的命令、配置格式和 CSV 模式。 | [ADR-0006](../decisions/adr/ADR-0006-preserve-public-compatibility-by-default.md) |
| **serving 契约** | 同步 HTTP/JSON 翻译服务：源端内部打 `<start>...<end>`、输出默认 strip、固定解码默认值（`num_beams=4` 等）、provenance（checkpoint / corpus SHA256 / seed）经 `/info` 暴露；独立于 RF-007 评估 schema。 | [ADR-0034](../decisions/adr/ADR-0034-serving-contract-synchronous-http-api.md) |

如需变更某项不变量，请提交一个超越它的新 ADR；不得直接编辑本表以提前放宽契约。
