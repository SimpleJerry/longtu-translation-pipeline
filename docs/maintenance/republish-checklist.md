# 重新发布检查清单 — 新检查点

发布一条新训练好的检查点(用于替换或补充当前生产模型 `earlystop-v1-ckpt48000`)时,按本清单逐步执行。

---

## 1. 训练

```powershell
python scripts/train_model.py \
  --config configs/training/earlystop.json \
  --train \
  --run-name <new-run>
```

产物:含检查点的 run 目录 + `run_manifest.json`(记录语料 SHA256、拆分 seed/比例、行数、检查点路径)。

## 2. 评估

在 held-out test 拆分上运行推理,再计算指标:

```powershell
python scripts/run_inference.py \
  --config configs/inference/default.json \
  --generate-test \
  --run-dir <run-dir>

python scripts/evaluate_translation.py \
  --config configs/evaluation/generation_report.json \
  --input <generated-csv>
```

记录新的 BLEU / chrF / glossary preservation(no-space 与 exact)。依据 [ADR-0023](../decisions/adr/ADR-0023-formal-experiments-use-held-out-test-splits.md):test 拆分每个模型**只评估一次**,且从不用于检查点选择。

## 3. 发布到 HF Hub

```powershell
python scripts/publish_model.py \
  --checkpoint <path-to-checkpoint-dir> \
  --tag <new-run>-ckpt<N>
```

上传精选的推理必需文件 + `run_manifest.json`,刷新 model card,并将仓库可见性设为 public。需要 `HF_TOKEN`(write scope)。参见 [ADR-0037](../decisions/adr/ADR-0037-model-distribution-via-public-hf-hub.md)。

## 4. 在 serving 配置中固定 revision(强制 — ADR-0038)

更新**两个**文件中的 `revision` 字段:

| 文件 | 字段 |
|------|------|
| `configs/serving/docker.json` | `model.revision` |
| `demo/space.json` | `model.revision` |

新值:`<new-run>-ckpt<N>`(第 3 步产生的 tag)。

## 5. 同步 Gradio Demo Space

将 `demo/space.json` 重新上传到 HF Spaces(或推送更新后的文件并触发 Space 同步)。参见 [ADR-0040](../decisions/adr/ADR-0040-public-gradio-demo-space.md)。

## 6. 更新五处规范位置的指标

五处必须显示一致的数字(或一致地指向 model card):

| 文件 | 章节 |
|------|------|
| `README.md` (ko) | 결과 |
| `README.en.md` | Results |
| `README.zh-CN.md` | 成果 |
| `docs/product/model-card.md` | 保留测试集结果 |
| `demo/app.py` | `_DESCRIPTION` 常量 |

## 7. 更新 model-card 溯源(若语料变更)

若 `data/segments.csv` 发生变更,更新 `docs/product/model-card.md`:

- Run / 检查点 ID(第 1 步的 tag)
- 语料 SHA256(来自 `run_manifest.json`)
- 行数与各拆分大小

## 8. 验证

```powershell
pytest -n auto   # 必须保持绿色(当前 289 passed)
```

可选冒烟检查:

```powershell
python scripts/serve.py --dry-run          # 配置校验
# docker run ... (serving 冒烟,见 ADR-0035)
# 确认 live demo 已加载新的 revision
```

---

_参考 ADR:[ADR-0020](../decisions/adr/ADR-0020-formal-training-runs-require-split-artifacts-and-manifests.md) · [ADR-0023](../decisions/adr/ADR-0023-formal-experiments-use-held-out-test-splits.md) · [ADR-0031](../decisions/adr/ADR-0031-formal-training-uses-early-stopping-on-composite-metric.md) · [ADR-0034](../decisions/adr/ADR-0034-serving-contract-synchronous-http-api.md) · [ADR-0035](../decisions/adr/ADR-0035-docker-jenkins-deployment-contract.md) · [ADR-0037](../decisions/adr/ADR-0037-model-distribution-via-public-hf-hub.md) · [ADR-0038](../decisions/adr/ADR-0038-serving-pull-model-from-public-hf.md) · [ADR-0039](../decisions/adr/ADR-0039-packaging-pyproject-remove-syspath.md) · [ADR-0040](../decisions/adr/ADR-0040-public-gradio-demo-space.md)_
