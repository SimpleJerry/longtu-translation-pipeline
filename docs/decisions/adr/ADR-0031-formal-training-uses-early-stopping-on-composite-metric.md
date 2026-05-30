# ADR-0031：正式训练在复合指标上执行早停

- 状态：已接受
- 日期：2026-05-27

## 背景

RF-006-P11 使用了 `max_steps=10000`（约 0.189 个 epoch）。在第 10000 步时，`eval_loss` 仍在下降，验证集 BLEU 仍在上升，表明模型处于欠拟合状态。固定步数上限既无法检测欠拟合（停得太早），也无法检测过拟合（若验证质量下降则停得太晚）。

备选方案调研：事后最优检查点选择（无自动停止）、ReduceLROnPlateau（仅基于损失，忽略词汇表保留率）、平滑早停、学习曲线外推、贝叶斯超参数优化。最终选择了 patience + 复合指标 + 最优检查点的组合，这是符合本项目阶段的标准 NMT 微调实践。

## 决策

新的正式训练运行使用 `Seq2SeqTrainer` 配合 `EarlyStoppingCallback`（patience=5，threshold=0.0）及 `load_best_model_at_end=True`，由复合指标驱动：

```
eval_composite = 0.5 · eval_bleu + 0.5 · eval_glossary_preservation_nospace
```

- `num_train_epochs` 为上限（默认 10）；`max_steps` 不设置，由早停循环决定何时停止。
- `step10k.json` 配置文件（`max_steps=10000`）作为历史基准**保留**，不得删除。
- **循环内评估使用 1,000 行验证子集**（`metrics.eval_subset_rows=1000`）以提升性能：完整的 6,626 行验证集在 `predict_with_generate=True` 时每次评估约需 38 分钟，使 10 epoch 上限变得不切实际。
- 剩余的 5,626 行验证集保留用于早停触发后的事后 top-K（3）完整验证重排。
- 循环内使用 `generation_max_length=256`（韩语输出 token 的 p99.9 为 225；约 0.06% 截断）；`configs/inference/default.json` 对事后及最终推理保留 `max_length=400`。

复合权重（当前 BLEU 和 preservation_nospace 各 0.5）只能通过新的 RF 修订，不得悄悄编辑。

普通 `Trainer`（非 Seq2Seq）路径对冒烟/试验性/`step10k.json` 保持可用，确保现有测试和旧配置文件继续工作。

## 后果

- 正式训练在复合指标趋于稳定时自动停止，而非在任意步数处停止。
- 推理时超参数探索（束宽、长度惩罚）属于独立工作（RF-028），不属于本决策范围。
- 循环内评估使用廉价的 1k 行子集；最终检查点选择使用事后完整验证集评估。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-006-P13、T-A5
- 相关代码：`src/longtu_translation_pipeline/training.py`、`src/longtu_translation_pipeline/training_metrics.py`、`configs/training/earlystop.json`
