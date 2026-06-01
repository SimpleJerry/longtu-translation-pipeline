# ADR-0034：服务契约 —— 同步 HTTP/JSON 翻译接口

- 状态：已接受
- 日期：2026-06-02

> 本 ADR 于 2026-06-02 接受。**接受时已同步**:ADR 状态 + 索引、[`scope.md`](../../product/scope.md)(serving 移入范围)、[`invariants.md`](../../architecture/invariants.md)(新增「serving 契约」行)。**推迟到实现阶段**(避免对尚不存在的服务过度声明):[`model-card.md`](../../product/model-card.md) 与三语 README 的 serving 可用性表述(阶段 2–3,服务可运行后)、requirements 的 `fastapi`/`uvicorn`(阶段 2,实际安装后)。

## 背景

CLAUDE.md「Mission」把项目终点定义为「a **deployable** zh-CN → ko translation model that **serves inference**」,而「ADR Rules」明确将 *inference / serving contract* 列为**必须先立 ADR** 的决策。但 ADR 索引止于 ADR-0033(全部为 cleanup / 重构),**尚无任何 serving 契约**;代码侧亦无任何 serving 痕迹(无 `fastapi` / `flask` / `uvicorn` / `http.server`)。因此直接编写 serving 会绕过项目自身的治理规则。

同时存在一处必须显式处理的冲突:[`docs/product/scope.md`](../../product/scope.md) 当前把「自动化部署或生产服务」列在**「不在范围(当前主线)」**。本 ADR 即是把 serving 从「未来 Mission」搬入「当前范围」的开关,因此**同时是一次 product-scope 变更**(经用户决策:契约 + 纳入范围 + 立即实现)。

现有「推理」全部是**离线批处理 CSV→CSV**([`src/longtu_translation_pipeline/inference.py`](../../../src/longtu_translation_pipeline/inference.py) + [`scripts/run_inference.py`](../../../scripts/run_inference.py)),其数据模型 `InferenceRecord` **强制要求 `reference`**(`read_inference_records` 在 reference 为空时直接 `raise`),整条 `generate_records` 路径都假定「有 gold reference」并输出 RF-007 评估模式 `segment_id,source,references,candidates`([ADR-0016](ADR-0016-inference-output-stays-rf007-compatible.md))。serving 是**在线、无 reference**(调用方正因为没有译文才请求翻译),故现有 core **不能直接复用**。

已锁定的相关不变量(本 ADR 不超越,而是绑定并复用):

- **术语标记**:推理在分词前对**源端**应用 `<start>...<end>`,否则训练/服务输入分布不匹配([ADR-0028](ADR-0028-inference-uses-source-terminology-markers.md)、[ADR-0010](ADR-0010-text-protection-uses-single-segment-term-markers.md))。
- **解码默认值**:`num_beams=4, length_penalty=1.0, no_repeat_ngram_size=0, max_length=400`,变更受 [ADR-0006](ADR-0006-preserve-public-compatibility-by-default.md) 约束(见 [`model-card.md`](../../product/model-card.md))。
- **可复现性**:任何对外报告的数字必须可由记录的设置重建;运行溯源记录于 `run_manifest.json`(corpus SHA256 / seed / checkpoint)。

## 决策

定义一个**同步 HTTP/JSON** 翻译服务契约。传输为 **FastAPI + uvicorn**(新增运行时依赖)。

### 1. 接口形态与端点

| 端点 | 方法 | 语义 |
|------|------|------|
| `/translate` | POST | 同步翻译;请求体始终为数组(单条 = 长度 1 的数组)。 |
| `/health` | GET | 存活探针,**不触发模型推理**,返回 `{"status":"ok"}`。 |
| `/info` | GET | 暴露模型溯源与契约参数(provenance + 解码默认值 + marker 策略),供审计。 |

### 2. 请求 / 响应 schema(**不复用 RF-007 wire 格式**)

RF-007 模式(`segment_id,source,references,candidates`)是**离线评估 CSV**,带 `references`(gold)。serving 在线无 reference,故**定义独立的 JSON schema**,只在字段命名上保持心智一致(`id` / `source` / 单数 `translation`,丢弃 `references`,`candidates`→`translation`)。RF-007 继续作为 evaluation 契约,两者共享 marker / decoding **语义**,不共享传输格式。

请求 `POST /translate`:

```json
{
  "items": [
    { "id": "seg-001", "text": "中文原文……" }
  ]
}
```

- `items`:长度 1..N,N ≤ `serving.max_items_per_request`。
- `id`:可选,原样回显以便调用方对齐;`text`:必填、非空。

响应 `200`:

```json
{
  "model": {
    "checkpoint": "earlystop-v1/checkpoint-48000",
    "corpus_sha256": "…(权威值见 model-card.md)",
    "seed": 42,
    "decoding": { "num_beams": 4, "length_penalty": 1.0, "no_repeat_ngram_size": 0, "max_length": 400 }
  },
  "results": [
    { "id": "seg-001", "source": "中文原文(无 marker)", "translation": "한국어 번역" }
  ]
}
```

### 3. 术语 marker 策略(绑定 ADR-0028 / ADR-0010)

- **输入打 marker**:服务端**内部**在分词前对源端应用 `<start>...<end>`(复用 `mark_source_glossary_terms`);API 仅接收**原始**中文,glossary 成为**启动期依赖**。marker 不暴露给调用方。
- **输出 strip marker**:`translation` 默认**剥除** marker(`strip_glossary_markers=true`),返回干净韩文。
- 响应 `source` 回显**原始未打 marker** 文本(与 ADR-0028 保持 source 列无 marker 一致)。

### 4. 解码默认值(绑定 ADR-0006 + model-card)

服务**固定**使用 `num_beams=4, length_penalty=1.0, no_repeat_ngram_size=0, max_length=400`。beam search 确定性 → 同输入同输出。这些默认值是公开兼容面,变更须走 ADR-0006 破坏性变更流程;请求体**不接受**逐请求覆写解码参数(避免不可复现的对外输出)。

### 5. 模型来源与 provenance 暴露(可复现性)

- 服务从配置的 checkpoint 路径加载(同 inference `model.path`);**默认服务 model-card 已发布的 checkpoint**(`earlystop-v1 / checkpoint-48000`)。
- 启动时读取该运行的 `run_manifest.json`,并通过 `/info` 与每次响应的 `model` 块暴露 **checkpoint id + corpus SHA256 + seed + 解码默认值**,使任一部署实例可审计、其输出可重建。

### 6. 并发 / 限制 / 超时(契约层)

- **单进程单模型实例**;请求对同一模型串行执行(GPU 串行)。横向扩展 = 无状态进程副本。
- **输入上限**:`text` 超过 `max_length` token 即拒绝(不静默截断);`items` 超过 `max_items_per_request` 即拒绝。
- 文档化请求 timeout;并发达到 `max_concurrency` 上限时返回 `429`。
- **硬 SLA(吞吐 / p99)取决于尚未确定的硬件,本 ADR 不锁定**,留作 Open Question。

### 7. 错误语义(延续 ADR-0024 精神:报告而非崩溃)

| 情形 | 响应 |
|------|------|
| `items` 为空 / `text` 为空 | `422` |
| `text` 超 `max_length` token / `items` 超上限 | `422`,detail 指明限制 |
| 并发超 `max_concurrency` | `429` |
| 生成内部错误 | `500`,安全错误体 |
| 启动期 model / tokenizer / glossary 缺失 | **进程启动失败(fail fast)**,不进入可服务态 |

### 8. 无状态 / 确定性

每个请求相互独立、不保留请求间状态;确定性 beam search 保证同输入同输出。

### 9. pure core 重构(thin interface,实现第一步)

因现有 core 绑死 reference(见「背景」),serving 实现**第一步**是一次行为保持的「thin interface, pure core」重构:从 CSV / reference 包装中抽出 reference-optional 的纯生成函数

```
translate(texts: list[str]) -> list[str]   # mark source → tokenize → generate → strip
```

现有离线 CSV 路径(`generate_records`)在其上重建,serving 层也复用同一函数。该重构对离线路径**行为保持**,以 characterization test 兜底(契合 CLAUDE.md「Thin interfaces, pure core」)。

### 10. 配置

新增 [`configs/serving/default.json`](../../../configs/serving/default.json),复用 inference 配置字段 + serving 块:

```json
{
  "model":      { "path": "fine-tuned-models/nllb-200-distilled-600M/zh2ko", "tokenizer_name": "facebook/nllb-200-distilled-600M" },
  "language":   { "source_code": "zho_Hans", "target_code": "kor_Hang" },
  "glossary":   { "path": "data/glossary.csv", "source_terminology_markers": true },
  "output":     { "strip_glossary_markers": true },
  "generation": { "batch_size": 8, "max_length": 400, "num_beams": 4, "length_penalty": 1.0, "no_repeat_ngram_size": 0 },
  "serving":    { "host": "127.0.0.1", "port": 8000, "max_items_per_request": 32, "max_concurrency": 1 }
}
```

## 后果

**本 ADR 接受后须同步(各为独立的一次逻辑提交):**

- [`docs/product/scope.md`](../../product/scope.md):把「自动化部署或生产服务」移出「不在范围」,并在「在范围内」新增 serving。
- [`docs/architecture/invariants.md`](../../architecture/invariants.md):新增「serving 契约」行,绑定本 ADR(同步 HTTP/JSON schema、marker 策略、固定解码默认值、provenance 暴露)。
- [`docs/product/model-card.md`](../../product/model-card.md):补「推理 / serving 默认参数」引用本 ADR。
- 三语 README(ko / en / zh):反映 serving 可用性(不复制易漂移数字,引用 model-card)。
- 依赖:`fastapi` / `uvicorn` 在成功安装后写入 requirements(Session Rules)。

**实现分阶段(每阶段一个可独立 review 的提交,仓库每步保持 green):**

1. **pure core 重构**:抽 `translate(texts)->candidates`,离线 CSV 路径在其上重建 + characterization test(行为保持)。
2. **serving 层**:FastAPI app(`/translate` / `/health` / `/info`),复用阶段 1 core + marker + strip + 固定解码 + provenance;薄入口 `scripts/serve.py`。
3. **docs / scope**:上述接受后同步项 + `configs/serving/default.json`。
4. **测试**:沿 [ADR-0011](ADR-0011-training-inference-configs-use-json-dry-run-entrypoints.md) 精神的无模型契约测试(schema 校验 / 错误码 / `/health` 不加载模型)+ 单条 & 批 round-trip + 超长 / 空输入 + marker round-trip。

**Open Questions(不阻塞接受,接受后在实现期收敛):**

1. 目标运行环境未知(内网单 GPU / CPU-only?)—— 决定 §6 并发模型与硬 SLA。
2. 认证 / 访问控制是否需要(内部工具可能不需要)。
3. `/translate` 是否需提供调用方可见的逐请求 `strip_markers` 开关(默认建议:仅 config 控制,不暴露)。

## 参考

- 驱动原则:CLAUDE.md「Mission」「ADR Rules」「Architecture Principles / Thin interfaces, pure core / Reproducibility first」
- 绑定 / 复用:[ADR-0028](ADR-0028-inference-uses-source-terminology-markers.md)、[ADR-0010](ADR-0010-text-protection-uses-single-segment-term-markers.md)(marker)、[ADR-0016](ADR-0016-inference-output-stays-rf007-compatible.md)(RF-007 评估契约,本 ADR 与之区分)、[ADR-0006](ADR-0006-preserve-public-compatibility-by-default.md)(解码默认值公开兼容)、[ADR-0011](ADR-0011-training-inference-configs-use-json-dry-run-entrypoints.md)(JSON 配置 + 无模型 dry-run 测试)、[ADR-0024](ADR-0024-evaluation-reports-empty-model-outputs-instead-of-failing.md)(报告而非崩溃)
- 相关代码:[`src/longtu_translation_pipeline/inference.py`](../../../src/longtu_translation_pipeline/inference.py)、[`src/longtu_translation_pipeline/text_protection.py`](../../../src/longtu_translation_pipeline/text_protection.py)、[`scripts/run_inference.py`](../../../scripts/run_inference.py)
- 相关配置:`configs/inference/default.json`、`configs/serving/default.json`(新增)
