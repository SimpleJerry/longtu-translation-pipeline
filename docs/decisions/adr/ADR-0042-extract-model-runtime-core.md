# ADR-0042：抽出 model_runtime 核心,解 inference→training 分层倒置（M2）

- 状态：**已接受** — 子决策已于 2026-06-04 全部确认(全按推荐,见下)
- 日期：2026-06-04

## 背景

`inference.py` 从 `training.py` import 了 5 个函数(`add_marker_special_tokens`、`cuda_device_name`、`cuda_memory_summary`、`find_latest_checkpoint`、`resolve_training_device`);`serving.py` 与 `demo/app.py` 又依赖 `inference` → **整个推理/serving/demo 栈传递性依赖训练模块**。此外 `scripts/select_checkpoint.py` 取 `list_checkpoint_paths`、`scripts/sweep_inference_params.py` 取 2 个。

这些函数**不是训练编排逻辑**,而是「tokenizer / 设备 / checkpoint」通用运行时工具,仅因历史原因住在 `training.py`。这是一处**分层倒置**:推理不应依赖训练。今天无运行时损害(`training` 顶层只 import stdlib、torch 函数内惰性导入,无循环依赖),但方向是反的——未来要独立打包/部署 serving 时会被 `training` 整个拽进去。

与 **M1(拆分 `training.py`)对比**:M1 改动面大、收益模糊、且有破坏「顶层 stdlib + 惰性 heavy import」不变量的风险,已决定**不做**。M2 是**定向、小切口、收益具体**的反向解耦。

## 决策

### 1. 新增中性模块 `src/longtu_translation_pipeline/model_runtime.py`

纯行为搬迁(ADR-0033 风格),迁入以下运行时工具:

| 函数 | 说明 |
|------|------|
| `add_marker_special_tokens(tokenizer) -> int` | 注入 `<start>/<end>` 特殊 token |
| `configure_tokenizer_language_codes(tokenizer, src_code: str, tgt_code: str) -> list[str]` | **统一签名**,消除 training/inference 两份重复(L3) |
| `resolve_training_device(device) -> str` | 保留原名(ADR-0006);仅迁位 |
| `cuda_device_name(device) -> str` | 设备信息 |
| `cuda_memory_summary(device) -> str` | 设备信息 |
| `list_checkpoint_paths(output_dir) -> list[Path]` | checkpoint 发现 |
| `find_latest_checkpoint(output_dir) -> Path \| None` | checkpoint 发现 |

### 2. 不变量约束（关键，必须守住）

`model_runtime.py` **顶层 import 必须保持 stdlib-only,`torch` 一律函数内惰性 import**——保住「dry-run / serving / CI-CPU 轻量导入路径」(`conftest.py` eager-import 注释、serving fail-fast、ADR-0014 分阶段加载都依赖它)。

→ **新增守卫测试**(`tests/test_model_runtime.py`):`import model_runtime` 后断言 `"torch" not in sys.modules`,并对纯函数(`list_checkpoint_paths`/`find_latest_checkpoint`)做单测。

### 3. 导入改向（打破倒置）

- `inference.py` / `scripts/select_checkpoint.py` / `scripts/sweep_inference_params.py`:`from ...training import` → `from ...model_runtime import`。**这一步真正切断推理对训练的依赖。**
- `training.py` 内部调用改为 `from .model_runtime import ...`。
- `training.py` 保留一段 **thin re-export**(`from .model_runtime import find_latest_checkpoint, list_checkpoint_paths, ...`)→ 任何既有 `from .training import X`(含 `tests/test_training_pipeline.py:23,33`、外部)仍可用,满足 ADR-0006,把测试改动降为**零**。

### 4. 留在 `training.py`（训练专属，不迁）

`load_nllb_tokenizer`、`resolve_trainer_precision`(trainer fp16/bf16)、`checkpoint_step`、`Seq2SeqTrainer` 构建、所有 DTO / formatter / run_manifest / git / split 逻辑。

### 5. 明确划界（不做）

- **不拆 `training.py`(M1)。**
- 不改任何公开 CLI 或 `__init__` 公共 API(这 7 个函数本就不在 `__init__` 导出面)。
- 不改任何行为 / 解码 / 指标 / 契约——纯搬迁 + 导入改向。
- **命名碰撞提示:** `cuda_device_name` / `cuda_memory_summary` **既是函数名也是 DTO 字段名**;本 ADR 只迁**函数**,DTO 字段名与 kwargs 不动(grep 噪声多来自字段,勿误改)。

## 后果

- **正面:** 推理/serving/demo 不再(传递性)依赖训练模块,serving 边界变干净、未来可独立打包;消除一处 L3 重复;`training.py` 略瘦(~70 行)。
- **改动面(小、定向):** 1 新模块 + `training.py`(删 defs / 加 import / 留 re-export)+ `inference.py`(1 个 import 块)+ 2 个脚本各 1 行 import + 1 个新测试。**保留 re-export 时 tests 零改动。**
- **风险:** 唯一实质风险是 `model_runtime` 顶层误引入 heavy import → 由 §2 守卫测试封住。
- **可复现性 / 契约:** 无影响。

## 已确认的决策（2026-06-04，全按推荐）

1. **保留 `training.py` thin re-export** — 既有 `from .training import X`（含测试、外部）继续可用,测试零改动(ADR-0006)。
2. **模块命名 `model_runtime.py`** — 单模块,不拆 `device.py` / `checkpoints.py`。
3. **纳入 `configure_tokenizer_language_codes` 统一(L3)** — 统一为 `(tokenizer, src_code, tgt_code) -> list[str]` 入 `model_runtime`;`training.py` / `inference.py` 两处调用点改为传 language code 字符串。
4. **不纳入 `require_columns`** — 属 io 关注点(CSV schema 校验),留作独立小项 / 后续 `io_utils`,不在本 ADR 范围。

## 参考

- [ADR-0033](ADR-0033-extract-data-cleaning-core-into-src.md)：数据清理 core 提取(确立「纯行为搬迁 + 薄入口 / re-export」模式)
- [ADR-0006](ADR-0006-preserve-public-compatibility-by-default.md)：保留公开兼容
- [ADR-0034](ADR-0034-serving-contract-synchronous-http-api.md) / [ADR-0038](ADR-0038-serving-pull-model-from-public-hf.md)：serving 契约(受益于边界解耦)
- 接手 review:M2 分层倒置;M1 已决定不做(改动面大、无明确收益)
