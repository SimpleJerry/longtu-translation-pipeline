# ADR-0011：训练与推理配置使用 JSON 及dry-run入口点

- 状态：已接受
- 日期：2026-05-24

## 背景

模型路径、语言对、批量大小和输出目录被硬编码在Notebook单元格中。在添加重量级训练依赖之前，项目需要可审查的配置。快速验证检查不应要求下载 NLLB 权重。

## 决策

训练和推理设置存放于 JSON 配置文件中。RF-006 第一阶段入口点在导入或dry-run执行期间不得加载模型。

- `configs/training/default.json` — 基础训练配置
- `configs/inference/default.json` — 基础推理配置
- `scripts/train_model.py --dry-run` 和 `scripts/run_inference.py --dry-run` 在不加载模型的情况下验证配置和数据。

## 后果

- 配置可审查且受版本控制。
- CI/导入时检查可在任何无 GPU 或模型缓存的机器上安全运行。
- 实际模型加载、Trainer 连接、分词和生成在后续阶段添加。
- 配置漂移是主要风险；JSON 配置文件应按用途命名（参见 ADR-0022）。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-006
- 相关代码：`configs/training/`、`configs/inference/`、`src/longtu_translation_pipeline/config.py`
