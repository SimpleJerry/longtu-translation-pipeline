# ADR-0012：评估仅使用 BLEU 和词汇表保留率

- 状态：已接受
- 日期：2026-05-24

## 背景

旧评估Notebook使用了历史 `<middle>` 和 `<code_id>` 假设，与 RF-005 的单语段标记格式不再匹配。项目在 RF-006 进入真实训练或生成之前需要自动化评估。代码 token 保留评估依赖于现已废弃的 `<code_id=N>` 格式，因此超出当前范围。

备选方案：包含代码 token 保留（已拒绝：依赖废弃格式）；立即包含 COMET（已拒绝：约 1.5 GB 依赖，与核心指标同时添加过于复杂）；立即包含 chrF（已拒绝：推迟至 T-F1 作为独立任务）。

## 决策

RF-007 评估自动化 `<start>...<end>` 标记策略下的语料 BLEU 和词汇表保留率。代码 token 保留不属于当前评估主线。

- BLEU 默认使用韩语空格分词；字符分词为配置选项。
- 词汇表保留率在从候选项中去除标记后检查韩语术语存在性。
- 精确匹配和无空格精确匹配指标均有报告（参见 ADR-0029）。

未来的指标扩展（通过 T-F1 添加 chrF，通过 T-F2 添加 COMET）是对本契约的扩展，而非替代。

## 后果

- `scripts/evaluate_translation.py` 和 `src/longtu_translation_pipeline/evaluation.py` 是规范的评估入口点。
- 历史 `<middle>` 和 `<code_id>` 评估路径仅保留为归档。
- 扩展指标集需要新任务和新 ADR。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-007、RF-024（chrF）、RF-025（COMET）
- 相关代码：`src/longtu_translation_pipeline/evaluation.py`、`configs/evaluation/`
