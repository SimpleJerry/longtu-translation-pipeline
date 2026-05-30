# ADR-0022：正式训练使用显式配置文件

- 状态：已接受
- 日期：2026-05-25

## 背景

从工程冒烟测试过渡到分阶段全数据训练引入了一个风险：若正式 `--train` 从冒烟/试验性配置继承小步数默认值，可能浪费 GPU 时间，或产生无法判断该运行是冒烟还是真实训练的模糊清单。

## 决策

正式全数据训练必须为关键训练参数使用显式配置文件或 CLI 覆盖；`--train` 不得继承小步数的冒烟/试验性默认值。

首个分阶段配置文件：
- 文件：`configs/training/full_10k.json`
- `max_steps=10000`，`save_steps=1000`，`eval_steps=5000`，`save_total_limit=6`

后续更长时间的运行或早停运行添加新的命名配置文件（如 `full_earlystop.json`），而非依赖记忆中的 CLI 参数。旧配置文件作为历史基准保留，不得删除。

## 后果

- `--train` 拒绝缺少 `max_steps` 的配置，除非 CLI 提供该参数（适用于 `full_10k` 风格的配置文件；`full_earlystop` 使用 `num_train_epochs` 代替）。
- `full_10k.json` 在早停取代其作为默认方法后（参见 ADR-0031）仍作为历史基准保留。
- `save_steps` 和 `eval_steps` 为独立设置。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-006-P9、RF-006-P11
- 相关代码：`configs/training/full_10k.json`、`configs/training/full_earlystop.json`
