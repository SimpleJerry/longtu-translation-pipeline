# ADR-0014：工程冒烟测试使用分阶段模型加载

- 状态：已接受
- 日期：2026-05-25

## 背景

训练链涉及多个高风险的集成点：真实 NLLB 分词器、语言代码处理、标记 token、张量形状、Trainer 连接、CUDA 执行及embedding 层扩展。在单次完整模型训练运行中验证所有这些内容将使故障难以隔离，且代价不必要地高昂。

为此建立了两个中间冒烟阶段：

**第一阶段（RF-006-P3）：** 使用真实 NLLB 分词器，但配合微型**随机初始化**的 `M2M100ForConditionalGeneration` 模型。验证内容：语言代码、标记 token、数据集张量、Trainer 连接——无需下载真实权重。

**第二阶段（RF-006-P4）：** 使用真实 NLLB 分词器和真实 `facebook/nllb-200-distilled-600M` 权重。验证内容：实际模型加载、`<start>/<end>` 的embedding 层扩展、CUDA 执行、FP16 自动混合精度——无需运行完整训练 epoch。

## 决策

工程冒烟测试使用分阶段模型加载：
- `--nllb-smoke-test`（第一阶段）：真实分词器 + 微型随机模型，`max_steps=1`。
- `--real-model-smoke-test`（第二阶段）：真实分词器 + 真实权重，`max_steps=1`。

两个阶段均将输出写入被忽略的 `data/review/training_smoke/`。两个阶段均不保留检查点，也不构成正式训练运行。

## 后果

- 冒烟测试失败可在对应阶段诊断，无需浪费 GPU 时间。
- 真实模型冒烟测试在试验性或正式训练前确认 CUDA/嵌入路径。
- 第一阶段无需下载 NLLB 模型权重（约 600 MB），保持 CI 安全路径轻量。

## 参考

- 原始条目：第一阶段重构决策日志（已归档，两条条目已合并；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-006-P3、RF-006-P4
- 相关代码：`scripts/train_model.py`、`src/longtu_translation_pipeline/training.py`
