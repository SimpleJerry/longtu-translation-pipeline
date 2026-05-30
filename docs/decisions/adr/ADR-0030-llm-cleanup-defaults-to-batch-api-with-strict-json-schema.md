# ADR-0030：LLM 清理默认使用批量 API 及严格 JSON Schema

- 状态：已接受
- 日期：2026-05-27

## 背景

T-A1 定价评估估算剩余语段语料约需 730 万输入 token + 230 万输出 token。旧的同步 `/v1/chat/completions` 传输方式没有 `response_format` 约束，也没有 `max_tokens` 上限，需要正则回退来解析 JSON，且不享受任何费用折扣。

OpenAI Batch API 提供 50% 费用折扣，而严格 `json_schema` 通过要求服务器验证 JSON 响应模式消除了正则回退。经定价评估，`gpt-4.1-mini` + Batch API + 严格 schema 被确认为成本最优配置（剩余语料估算约 $1.5–3，而同步 `gpt-4o-mini` 约 $2.5）。

## 决策

两个 LLM 清理流水线（`scripts/segments_llm_cleanup_pipeline.py` 和 `scripts/glossary_llm_cleanup_pipeline.py`）均默认 `--batch-mode batch`，为整个语料提交一个 OpenAI `/v1/batches` 任务并下载 JSONL 结果。

每个 chat completion 请求负载（同步或批量）均携带：
- `response_format={"type":"json_schema","strict":true}`
- `parallel_tool_calls=false`
- `max_tokens=batch_size*45`（语段）或 `batch_size*30`（词汇表）

旧的同步路径保留在 `--batch-mode sync` 后，仅用于单元测试和小型临时调试运行。

批量运行通过 `batch_state.json` 支持恢复（原子写入阶段 ∈ {init, input_written, uploaded, submitted, completed, downloaded} + ID）。

未添加新的第三方依赖；多部分上传在 `llm_common.py` 中手动实现，以保留仅 urllib 的审计面（§P0-1）。

## 后果

- Batch API SLA 为 24 小时；相应设置 `--max-wait-sec`。
- 同步模式接受相同的严格 `json_schema` 验证，旧调用方获得等效的服务器端验证。
- 流水线成本在提交前即可确定和预测。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-029、T-A1
- 相关代码：`scripts/llm_common.py`、`scripts/segments_llm_cleanup_pipeline.py`、`scripts/glossary_llm_cleanup_pipeline.py`
