# 可复现性操作手册

本文档是端到端复现「已提交语料 → 发布模型」全流程的操作参考。

**可复现性边界（ADR-0041）：** 复现承诺的范围是 `data/segments.csv` / `data/glossary.csv` → 发布于 HF Hub 的模型检查点。LLM 语义清洗（ADR-0026、ADR-0030）等在语料冻结之前执行的一次性步骤在边界之外，不需要也无法完全确定性复现。

---

## 确定性保证

| 属性 | 锁定方式 |
|------|----------|
| 数据拆分 | 8:1:1，seed=42（ADR-0023） |
| 训练随机性 | Transformers `seed=42`（`configs/training/earlystop.json`） |
| 语料完整性 | `run_manifest.json` 中的 `segments_sha256` 字段 |
| 依赖版本 | `requirements.txt`（pip lock）+ `pyproject.toml` |
| 检查点选择 | `scripts/select_checkpoint.py` 写入 `checkpoint_selection_manifest.json`（ADR-0041） |
| 发布 revision | `configs/serving/docker.json` 中的 `model.revision` tag（ADR-0038） |

---

## 端到端复现步骤

### 前提条件

```bash
git clone <repo>
cd longtu-translation-pipeline
pip install -e . --no-deps
pip install -r requirements.txt
```

确认语料指纹：

```bash
python -c "
import hashlib, pathlib
data = pathlib.Path('data/segments.csv').read_bytes()
print(hashlib.sha256(data).hexdigest().upper())
"
# 预期：30D5C299828C10235AEE357E9333740913E55C291C5B07A45C0739E41818EA97
```

### 步骤 1：词汇表一致性检查

```bash
python scripts/segments_glossary_cross_cleaning_pipeline.py --strict-check
```

通过后（`strict_current_mismatch_rows=0`）方可继续（ADR-0019）。

### 步骤 2：训练

```bash
python scripts/train_model.py --config configs/training/earlystop.json --train
```

产物写入 `fine-tuned-models/.../runs/earlystop-v{N}/`，其中：
- `run_manifest.json`：语料 SHA256、拆分路径、早停步数
- `splits/train.csv`, `splits/validation.csv`, `splits/test.csv`
- `checkpoint-{step}/`：各保留检查点

### 步骤 3：checkpoint 选择

```bash
python scripts/select_checkpoint.py \
    --run-dir fine-tuned-models/.../runs/earlystop-v{N} \
    --dry-run   # 先确认发现了正确的 checkpoint
```

```bash
python scripts/select_checkpoint.py \
    --run-dir fine-tuned-models/.../runs/earlystop-v{N}
```

产物：`checkpoint_selection_manifest.json`（记录胜出者与所有得分，ADR-0041）。

### 步骤 4：测试集单次评估

```bash
python scripts/run_inference.py \
    --config configs/inference/default.json \
    --generate-test \
    --run-dir fine-tuned-models/.../runs/earlystop-v{N} \
    --model-path fine-tuned-models/.../runs/earlystop-v{N}/checkpoint-{winner}

python scripts/evaluate_translation.py \
    --config configs/evaluation/generation_report.json \
    --input <test generation CSV>
```

测试集每个模型**仅评估一次**（ADR-0023）。

### 步骤 5：发布

```bash
HF_TOKEN=<write-token> python scripts/publish_model.py \
    --checkpoint fine-tuned-models/.../runs/earlystop-v{N}/checkpoint-{winner} \
    --tag earlystop-v{N}-ckpt{winner}
```

发布后验证：

```bash
python scripts/verify_hf_publish.py \
    --repo SimpleJerry/longtu-nllb-zh2ko \
    --tag earlystop-v{N}-ckpt{winner} \
    --skip-model-load
```

---

## 已知手工及非确定步骤

| 步骤 | 非确定性来源 | 说明 |
|------|------------|------|
| LLM 语义清洗（ADR-0026、ADR-0030） | 外部 LLM API（模型版本、温度采样） | **在复现边界之外**；语料已冻结，SHA256 可验证 |
| 词汇表语义清洗（ADR-0025） | 同上 | 同上 |
| Checkpoint 选择 | 已脚本化（`scripts/select_checkpoint.py`），现为确定性 | 历史首次运行为人工选择，见 `docs/product/model-card.md` |
| HF Hub 上传 | 网络延迟 / API token | 确定性内容，非确定性传输 |

---

## 验证已发布模型可达性

```bash
python scripts/verify_hf_publish.py \
    --repo SimpleJerry/longtu-nllb-zh2ko \
    --tag earlystop-v1-ckpt48000 \
    --skip-model-load
```

无需 HF_TOKEN（公开仓库，ADR-0037）。

---

## 参考文档

| 文档 | 说明 |
|------|------|
| [ADR-0020](decisions/adr/ADR-0020-formal-training-runs-require-split-artifacts-and-manifests.md) | 正式训练须生成拆分产物和运行清单 |
| [ADR-0023](decisions/adr/ADR-0023-formal-experiments-use-held-out-test-splits.md) | 8:1:1 / seed=42 拆分契约 |
| [ADR-0031](decisions/adr/ADR-0031-formal-training-uses-early-stopping-on-composite-metric.md) | 早停与复合指标 |
| [ADR-0037](decisions/adr/ADR-0037-model-distribution-via-public-hf-hub.md) | 公开 HF Hub 分发 |
| [ADR-0041](decisions/adr/ADR-0041-reproducibility-boundary-and-checkpoint-selection.md) | 可复现性边界与 checkpoint 选择脚本化 |
| `docs/product/model-card.md` | 已发布检查点的确切指标与溯源 |
