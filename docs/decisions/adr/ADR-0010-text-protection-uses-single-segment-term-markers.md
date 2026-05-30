# ADR-0010：文本保护使用单语段术语标记

- 状态：已接受
- 日期：2026-05-24

## 背景

代码库中存在两种术语保护格式：
1. **单语段**：`<start>term<end>`，独立应用于源端和目标端。
2. **T&N+R**：`<start>source<middle>target<end>`——用于术语替换的三元组格式。
3. **代码/标签保护**：`<code_id=N>`，用于保护 UI 标签和代码片段。

T&N+R 格式在分词、评估和推理对齐方面引入了复杂性。用户决定将当前主线简化为单一统一格式。

## 决策

当前术语保护仅在源端和目标端使用 `<start>...<end>`。历史 T&N+R 格式（`<middle>`）和 `<code_id=N>` 代码/标签保护已从当前工程主线中废弃。

历史Notebook中仍可包含 `<middle>` 和 `<code_id=N>` 输出作为实验记录，但新的可复用代码不得生成这些格式，除非未来任务明确重新引入该行为。

## 后果

- `src/longtu_translation_pipeline/text_protection.py` 提供规范的 `<start>...<end>` 标记实现。
- 当前模块、测试、README 和配置路径均不依赖 `<middle>` 或 `<code_id=N>`。
- 未来 RF-006/RF-007 工作仅使用单语段标记格式。
- 训练/推理标记对齐使用相同格式（参见 ADR-0028）。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-005
- 相关代码：`src/longtu_translation_pipeline/text_protection.py`、`tests/test_text_protection.py`
