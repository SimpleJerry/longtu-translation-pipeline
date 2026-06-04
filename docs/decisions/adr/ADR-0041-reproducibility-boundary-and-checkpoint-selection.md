# ADR-0041：可复现性边界与检查点选择脚本化

- 状态：已接受
- 日期：2026-06-04

## 背景

随着项目进入发布后维护阶段，需要明确两个密切相关的方法学问题：

**可复现性边界（D6）：** 项目包含 LLM 语义清洗（ADR-0026、ADR-0030）等非确定性预处理步骤。若把这些步骤也纳入可复现性范围，则每次可复现性审计都需要访问外部 LLM API、支付推断费用，且结果在 API 版本升级后仍可能漂移。另一方面，`data/segments.csv` 与 `data/glossary.csv` 已提交 Git 并附有 SHA256 指纹（见 `run_manifest.json` 中的 `segments_sha256`），是稳定、可验证的锚点。

**检查点选择（D5）：** ADR-0031 规定"已发布检查点通过在完整验证集上重新排序选出"，但当时该选择由人工执行并未脚本化。现有 `earlystop-v1-ckpt48000` 是首次且已发布的结果，其选择已记录于 `docs/product/model-card.md`；本 ADR 对该既成事实无追溯影响，仅约束未来运行。

## 决策

### 可复现性边界

**可复现性承诺的范围是：已提交语料 → 训练好的模型权重。**

具体地：

- 边界**起点**：`data/segments.csv` 和 `data/glossary.csv`（已提交 Git，附 SHA256）。
- 边界**终点**：发布于 HF Hub 的模型检查点（通过 `revision=<tag>` 固定，见 ADR-0037/ADR-0038）。
- 边界内的所有步骤——数据拆分（seed=42，8:1:1，ADR-0023）、训练（ADR-0020、ADR-0031）、检查点选择（本 ADR §检查点选择）——必须**机械可复现**：固定 seed、固定依赖、脚本化。
- 边界**之外**（即 LLM 语义清洗、跨清理、批量 API 语义推断，ADR-0026、ADR-0027、ADR-0030）：这些是一次性、已审计的步骤，语料已冻结入库。这些步骤依赖外部 API，本身不可完全确定性复现；将其纳入边界只会制造虚假的确定性保证而无实际价值。`run_manifest.json` 中的 `segments_sha256` 是验证语料完整性的充分锚点。

### 检查点选择

**未来所有正式运行的检查点选择必须通过脚本 `scripts/select_checkpoint.py` 执行，结果写入 selection manifest。**

具体规程：

1. 训练结束后（早停触发，ADR-0031），对所有保留的 checkpoint 目录（`save_total_limit` 以内）在**完整验证集**（全部 6,626 行，非训练器循环内的 1,000 行子集）上运行推断与复合指标评分。
2. 复合指标 = `0.5 · BLEU + 0.5 · preservation_nospace`（与 ADR-0031 一致）。
3. 胜出的 checkpoint 目录路径、各 checkpoint 分数、评估时间戳写入运行目录下的 `checkpoint_selection_manifest.json`。
4. `checkpoint_selection_manifest.json` 与 `run_manifest.json` 并列存放于运行目录，均被 Git 忽略（ADR-0017），但在发布前须附在发布记录中。
5. 已有运行（`earlystop-v1`）的选择是本 ADR 接受前的人工选择，不受本规程约束，但已在 `docs/product/model-card.md` 记录且一致。

工程实现交付：`scripts/select_checkpoint.py` + 配套单元测试（ADR-0014 分阶段加载）；
实现里程碑归 T4（可复现性加固清单）。

## 后果

- `data/segments.csv` / `data/glossary.csv` 的 SHA256 是可复现性的唯一语料锚点；任何语料变更都需要重新训练与评估。
- LLM 语义清洗步骤无需也无法纳入自动化可复现性验证；维护者的审计责任止于确认语料 SHA256 一致。
- 未来每次正式运行发布前，必须提供 `checkpoint_selection_manifest.json`，缺失则视为可复现性不合规。
- `docs/architecture/invariants.md` 的「检查点选择」不变量升级为包含「脚本化执行」约束（见参考）。

## 参考

- [ADR-0020](ADR-0020-formal-training-runs-require-split-artifacts-and-manifests.md)：正式训练须生成拆分产物和运行清单
- [ADR-0023](ADR-0023-formal-experiments-use-held-out-test-splits.md)：8:1:1 / seed=42 拆分契约
- [ADR-0026](ADR-0026-cloud-llm-segment-cleanup-may-rewrite-korean-with-local-guards.md)：LLM 语段清洗（边界外）
- [ADR-0030](ADR-0030-llm-cleanup-defaults-to-batch-api-with-strict-json-schema.md)：LLM 批量清洗（边界外）
- [ADR-0031](ADR-0031-formal-training-uses-early-stopping-on-composite-metric.md)：早停与复合指标
- [ADR-0037](ADR-0037-model-distribution-via-public-hf-hub.md)：发布 tag 与 revision 固定
- `docs/product/model-card.md`：当前已发布检查点的选择记录
- `docs/reproducibility.md`（T5 交付）：端到端可复现性操作手册
