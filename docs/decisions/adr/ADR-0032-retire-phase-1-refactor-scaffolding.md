# ADR-0032：退役第一阶段重构脚手架

- 状态：已接受
- 日期：2026-05-30
- 废弃：ADR-0002

## 背景

第一阶段工程重构（RF-001 至 RF-022，以及后续的 RF-026–RF-031）已告完成。所有持久性决策均已迁移至独立的 ADR 文件（ADR-0001–ADR-0031）。指标和模型溯源存放于 [`docs/product/model-card.md`](../../product/model-card.md)。数据清理规则存放于 [`docs/architecture/data-cleaning-pipeline.md`](../../architecture/data-cleaning-pipeline.md)。不变量存放于 [`docs/architecture/invariants.md`](../../architecture/invariants.md)。产品范围存放于 [`docs/product/scope.md`](../../product/scope.md)。

`docs/refactor/` 是该阶段的过程性脚手架：

| 文件 | 内容 | 状态 |
|------|------|------|
| `backlog.md` | RF-001–RF-031 任务池及各任务运行日志 | 所有任务均已完成或明确延期 |
| `decisions.md` | 指向 ADR 目录的指针（已被 ADR-0003 废弃） | 已废弃 |
| `follow-up-tasks.md` | 并行轨道分配图 | 不再活跃 |
| `audit-2026-05-26.md` | 一次性版本库审计快照 | 仅供历史参考 |
| `task-briefs/T-*.md` | 各任务实施简报（T-A1–T-F5） | 已完成；仅为过程历史 |

值得评估的唯一"承重"内容：

- **RF-006-P12 检查点对比表**：已废弃的 10k 步运行的中间验证数据。当前模型的关键数字已在模型卡片中；该表为过程历史，不提取。
- **RF-007-P5 基础模型基准**：已汇总至 [`docs/product/model-card.md`](../../product/model-card.md) §参考基准。
- **RF-016–RF-022 工程决策**：均已 ADR 化（ADR-0014–ADR-0022 及 ADR-0031）。
- **`audit-2026-05-26.md`**：一次性审计快照；价值在审计时已体现，不提取。

## 决策

通过以下步骤退役 `docs/refactor/`：

1. 创建注释 git 标签 `phase-1-refactor-archive`，指向仍包含完整脚手架的最后一个提交，使历史记录随时可恢复。
2. 运行 `git rm -r docs/refactor/` 将该目录从工作树和索引中删除。

ADR-0002（确立 `docs/refactor/backlog.md` 为重构任务单一真相源）被本决策废弃——待办列表的使命已完成，目录已退役。

未来的重构或功能工作应使用：
- 本 ADR 系统处理持久性决策，或
- 临时性任务文档（版本库外，或作为短期分支）处理实施追踪。

## 后果

- 本次变更后，`docs/refactor/` 不再存在于工作树中。
- ADR-0002 标记为**已废弃（见 ADR-0032）**。
- 如需查看任何历史任务简报、待办说明或审计发现，请检出标签：`git show phase-1-refactor-archive:docs/refactor/backlog.md`
- 不影响任何代码、配置、测试或数据文件——这是纯文档变更。

## 参考

- 废弃：[ADR-0002](ADR-0002-refactor-backlog-lives-in-docs-refactor-backlog.md)
- 相关：[ADR-0003](ADR-0003-architecture-decisions-log-superseded.md)（decisions.md 已废弃）
- Git 标签：`phase-1-refactor-archive`
