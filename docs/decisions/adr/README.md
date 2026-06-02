# 架构决策记录

本目录是项目的权威架构决策记录（ADR）日志。
每个文件代表一项持久的架构或 pipeline 决策——从真实备选方案中做出的选择，且对未来行为具有约束力。

原始的按时间顺序排列的决策日志已被本 ADR 目录取代。
完整的第一阶段重构 scaffolding（包括原始 `decisions.md`）已归档至 git 历史
（标签：`phase-1-refactor-archive`；参见 ADR-0032）。

---

| ADR | 标题 | 状态 | 日期 | 摘要 |
|-----|------|------|------|------|
| [ADR-0001](ADR-0001-readme-and-agents-do-not-carry-long-term-task-pools.md) | README 与 AGENTS 不承载长期任务池 | 已接受 | 2026-05-17 | README/AGENTS 保持专注；所有重构 TODO 进入 backlog。 |
| [ADR-0002](ADR-0002-refactor-backlog-lives-in-docs-refactor-backlog.md) | 重构 backlog作为单一真相源（已废弃，见 ADR-0032） | 已废弃 | 2026-05-17 | 重构 backlog曾是第一阶段任务的单一真相源（现已退役）。 |
| [ADR-0003](ADR-0003-architecture-decisions-log-superseded.md) | 架构决策日志（已废弃） | 已废弃 | 2026-05-17 | 按时间顺序的 `decisions.md` 已被本 ADR 系统取代。 |
| [ADR-0004](ADR-0004-csv-in-git-raw-xlsx-outside-git-tracking.md) | CSV 纳入 Git，原始 XLSX 排除 Git 跟踪 | 已接受 | 2026-05-17 | 规范化 CSV 提交；原始 Excel 文件列入 `.gitignore`。 |
| [ADR-0005](ADR-0005-gradual-engineering-refactor-approach.md) | 渐进式工程重构方法 | 已接受 | 2026-05-17 | 增量重构；Notebook 保留为实验记录。 |
| [ADR-0006](ADR-0006-preserve-public-compatibility-by-default.md) | 默认保留公开兼容性 | 已接受 | 2026-05-17 | 破坏性变更需明确的待办范围和 README 更新。 |
| [ADR-0007](ADR-0007-segment-evidence-not-sufficient-glossary-keep-signal.md) | 语段证据不足以作为词汇表保留信号 | 已接受 | 2026-05-22 | 语段存在是删除 gate，而非保留投票。 |
| [ADR-0008](ADR-0008-glossary-pipeline-uses-final-glossary-as-baseline.md) | 词汇表 pipeline 以最终词汇表为基准 | 已接受 | 2026-05-24 | pipeline 读取 `data/glossary.csv`；审计 CSV 为本地忽略产物。 |
| [ADR-0009](ADR-0009-notebook-deletion-requires-inventory-first.md) | Notebook 删除前须先建立清单 | 已接受 | 2026-05-24 | Notebook 归档并建立清单后再做任何删除决定。 |
| [ADR-0010](ADR-0010-text-protection-uses-single-segment-term-markers.md) | 文本保护使用单语段术语标记 | 已接受 | 2026-05-24 | 仅使用 `<start>...<end>`；T&N+R 和 `<code_id=N>` 已废弃。 |
| [ADR-0011](ADR-0011-training-inference-configs-use-json-dry-run-entrypoints.md) | 训练与推理配置使用 JSON 及 dry-run 入口点 | 已接受 | 2026-05-24 | JSON 配置；`--dry-run` 不加载模型。 |
| [ADR-0012](ADR-0012-evaluation-uses-bleu-and-glossary-preservation-only.md) | 评估仅使用 BLEU 和词汇表保留率 | 已接受 | 2026-05-24 | 核心指标为 BLEU + 词汇表保留率；chrF/COMET 为可选扩展。 |
| [ADR-0013](ADR-0013-segment-cleanup-is-review-first.md) | 语段清理以审校为先 | 已接受 | 2026-05-24 | `--apply` 为显式操作；默认输出 dry-run 审校结果。 |
| [ADR-0014](ADR-0014-engineering-smoke-tests-use-staged-model-loading.md) | 工程冒烟测试使用分阶段模型加载 | 已接受 | 2026-05-25 | 第一阶段：微型随机模型；第二阶段：真实权重，各运行一步。 |
| [ADR-0015](ADR-0015-pilot-training-may-save-ignored-local-checkpoints.md) | 试验性训练可保存被忽略的本地检查点 | 已接受 | 2026-05-25 | 试验性检查点为本地工程产物，非交付物。 |
| [ADR-0016](ADR-0016-inference-output-stays-rf007-compatible.md) | 推理输出保持 RF-007 兼容 | 已接受 | 2026-05-25 | 输出模式：`segment_id,source,references,candidates`。 |
| [ADR-0017](ADR-0017-generation-evaluation-reports-are-local-artifacts.md) | 生成评估报告为本地工程产物 | 已接受 | 2026-05-25 | 报告存放于被忽略的 `data/review/evaluation/`；不提交。 |
| [ADR-0018](ADR-0018-cross-cleaning-deletes-conflicts-not-translations.md) | 交叉清理删除强冲突，不删除翻译 | 已接受 | 2026-05-25 | 交叉清理仅删除，从不自动改写韩语。 |
| [ADR-0019](ADR-0019-full-training-requires-strict-glossary-consistency-check.md) | 正式训练前须通过严格词汇表一致性检查 | 已接受 | 2026-05-25 | `--strict-check` 必须通过（`strict_current_mismatch_rows=0`）才能训练。 |
| [ADR-0020](ADR-0020-formal-training-runs-require-split-artifacts-and-manifests.md) | 正式训练运行须生成拆分产物和运行清单 | 已接受 | 2026-05-25 | `--train` 写入固定拆分 + `run_manifest.json`；强制执行恢复保护。 |
| [ADR-0021](ADR-0021-validation-generation-uses-fixed-training-splits.md) | 验证集生成使用固定的训练拆分 | 已接受 | 2026-05-25 | 从运行清单读取 `splits/validation.csv`，而非临时行切片。 |
| [ADR-0022](ADR-0022-full-training-uses-explicit-profiles.md) | 正式训练使用显式配置文件 | 已接受 | 2026-05-25 | 命名 JSON 配置文件；旧配置文件保留为历史基准。 |
| [ADR-0023](ADR-0023-formal-experiments-use-held-out-test-splits.md) | 正式实验使用保留测试拆分（8:1:1，seed=42） | 已接受 | 2026-05-25 | 8:1:1 / seed=42 已锁定；每个模型仅使用一次测试集。 |
| [ADR-0024](ADR-0024-evaluation-reports-empty-model-outputs-instead-of-failing.md) | 评估对空模型输出报告而非报错 | 已接受 | 2026-05-25 | 空候选项计为质量失败，而非模式错误。 |
| [ADR-0025](ADR-0025-cloud-llm-glossary-cleanup-is-delete-only.md) | 云端 LLM 词汇表清理仅允许删除 | 已接受 | 2026-05-26 | LLM 只可删除词汇表行；不允许改写、添加或合并。 |
| [ADR-0026](ADR-0026-cloud-llm-segment-cleanup-may-rewrite-korean-with-local-guards.md) | 云端 LLM 语段清理可在本地保护下改写韩语 | 已接受 | 2026-05-26 | 仅在所有本地验证保护通过后才允许改写韩语。 |
| [ADR-0027](ADR-0027-segment-fragments-and-target-contamination-are-training-noise.md) | 语段片段与目标污染为训练噪声 | 已接受 | 2026-05-26 | 单字 CJK 片段和被污染目标端永久删除。 |
| [ADR-0028](ADR-0028-inference-uses-source-terminology-markers.md) | 推理在源端应用术语标记 | 已接受 | 2026-05-26 | 推理在分词前将 `<start>...<end>` 应用于源端。 |
| [ADR-0029](ADR-0029-glossary-preservation-reports-exact-and-nospace-metrics.md) | 词汇表保留率同时报告精确匹配和无空格指标 | 已接受 | 2026-05-26 | 精确匹配与无空格保留率并排报告。 |
| [ADR-0030](ADR-0030-llm-cleanup-defaults-to-batch-api-with-strict-json-schema.md) | LLM 清理默认使用批量 API 及严格 JSON Schema | 已接受 | 2026-05-27 | 默认 `--batch-mode batch`；所有补全请求使用严格 `json_schema`。 |
| [ADR-0031](ADR-0031-formal-training-uses-early-stopping-on-composite-metric.md) | 正式训练在复合指标上执行早停 | 已接受 | 2026-05-27 | `Seq2SeqTrainer` + `EarlyStoppingCallback`；复合指标 = 0.5·BLEU + 0.5·preservation_nospace。 |
| [ADR-0032](ADR-0032-retire-phase-1-refactor-scaffolding.md) | 退役第一阶段重构 scaffolding | 已接受 | 2026-05-30 | 第一阶段重构完成；`docs/refactor/` 退役至 git 历史（标签：`phase-1-refactor-archive`）。废弃 ADR-0002。 |
| [ADR-0033](ADR-0033-extract-data-cleaning-core-into-src.md) | 数据清理 core 提取至 src/ | 已接受 | 2026-05-31 | cleanup/ 与 llm/ 领域逻辑迁入 src/；scripts/ 退化为薄入口；纯行为保持搬迁。 |
| [ADR-0034](ADR-0034-serving-contract-synchronous-http-api.md) | 服务契约：同步 HTTP/JSON 翻译接口 | 已接受 | 2026-06-02 | 同步 FastAPI/JSON 翻译服务；源端打 marker、输出 strip、固定解码默认值、provenance 暴露；独立于 RF-007 评估 schema。serving 纳入 scope。 |
| [ADR-0035](ADR-0035-docker-jenkins-deployment-contract.md) | 部署契约：Docker 镜像 + Jenkins 流水线 + 模型挂载协议 | 已接受 | 2026-06-02 | python:3.12-slim 基础镜像（torch cu132 wheel 自带 CUDA runtime）；模型只读卷挂载；Jenkins 五阶段 pipeline；部署自动化纳入 scope。 |
