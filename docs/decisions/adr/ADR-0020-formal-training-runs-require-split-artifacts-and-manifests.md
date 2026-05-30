# ADR-0020：正式训练运行须生成拆分产物和运行清单

- 状态：已接受
- 日期：2026-05-25

## 背景

试验性训练（参见 ADR-0015）验证了检查点保存和恢复，但未提供足够的元数据或拆分稳定性以使未来的完整运行可复现。没有固定的拆分产物，每次训练恢复都可能悄悄使用不同的数据子集。

## 决策

正式训练（`scripts/train_model.py --train`）必须：
1. 在被忽略的 `fine-tuned-models/.../runs/{run-name}` 目录下写入固定的 `splits/train.csv`、`splits/validation.csv` 和 `splits/test.csv`。
2. 记录 `run_manifest.json`，包含：命令、拆分比例、拆分 seed、行数、拆分路径、`data/segments.csv` SHA256、检查点策略、依赖版本、损失值和 git 元数据。

恢复保护：
- 显式 `--limit-rows` 必须与已有清单中的行限制相匹配。
- 检查点步数必须小于请求的 `max_steps`。

## 运行命名约定

通过 `--run-name` 手动指定的正式运行使用格式 `{strategy}-v{N}`：
- 不加 `run-` 前缀（`run-` 保留给未传 `--run-name` 时自动生成的 `run-YYYYMMDD-HHMMSS` 非正式运行）
- 不加 `full`（正式运行天然使用全量数据，无需标注）
- 不加数据来源标记（数据指纹由 run_manifest.json 的 SHA256 追踪，不编码进名字）
- 配置文件采用相同的 `{strategy}.json` 命名，与运行名保持直观对应

示例：`step10k-v1`（固定步数上限 10k）、`earlystop-v1`（复合指标早停）对应配置 `step10k.json`、`earlystop.json`。

## 后果

- 验证集生成从清单中读取 `splits/validation.csv`（参见 ADR-0021）。
- 最终测试报告从清单中读取 `splits/test.csv`（参见 ADR-0023）。
- 清单不匹配的运行目录（例如来自修正前的双向拆分）视为已过时的工程产物。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-006-P7、RF-006-P10
- 相关代码：`scripts/train_model.py`、`src/longtu_translation_pipeline/training.py`
