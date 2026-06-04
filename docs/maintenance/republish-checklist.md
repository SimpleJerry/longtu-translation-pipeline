# 重新发布检查清单 — 新检查点

发布一条新训练好的检查点(用于替换或补充当前生产模型 `earlystop-v1-ckpt48000`)时,按本清单逐步执行。

---

## 1. 训练

```powershell
python scripts/train_model.py `
  --config configs/training/earlystop.json `
  --train `
  --run-name <new-run>
```

产物:含检查点的 run 目录 + `run_manifest.json`(记录语料 SHA256、拆分 seed/比例、行数、检查点路径)。

## 2. checkpoint 选择(脚本化 — ADR-0041)

在完整验证集上对所有保留 checkpoint 重新排序,选出胜出者:

```powershell
python scripts/select_checkpoint.py `
  --run-dir <run-dir> `
  --dry-run        # 先确认发现了正确的 checkpoint

python scripts/select_checkpoint.py `
  --run-dir <run-dir>
```

产物:`checkpoint_selection_manifest.json`(胜出者 + 各 checkpoint 分数)。参见 [ADR-0041](../decisions/adr/ADR-0041-reproducibility-boundary-and-checkpoint-selection.md)。

## 3. 评估(保留测试集单次运行)

在 held-out test 拆分上运行推理,再计算指标:

```powershell
python scripts/run_inference.py `
  --config configs/inference/default.json `
  --generate-test `
  --run-dir <run-dir> `
  --model-path <checkpoint-dir-from-step-2>

python scripts/evaluate_translation.py `
  --config configs/evaluation/generation_report.json `
  --input <generated-csv>
```

记录新的 BLEU / chrF / glossary preservation(no-space 与 exact)。

> **派生值提示:** `+X.XXX BLEU` 与 `~NNx` 提升倍数须从本次结果与基准对比**重新计算**，不得照抄上次发布的数字。
> 基准(未微调 NLLB-200-distilled-600M): BLEU=0.009, chrF=0.226, preservation_nospace=0.323。

依据 [ADR-0023](../decisions/adr/ADR-0023-formal-experiments-use-held-out-test-splits.md):test 拆分每个模型**只评估一次**，且从不用于 checkpoint 选择。

## 4. 发布到 HF Hub

```powershell
$env:HF_TOKEN = "<write-token>"
python scripts/publish_model.py `
  --checkpoint <path-to-checkpoint-dir> `
  --tag <new-run>-ckpt<N>    # 必须显式传 --tag，无默认值
```

上传精选的推理必需文件 + `run_manifest.json`,刷新 model card,并将仓库可见性设为 public。需要 `HF_TOKEN`(write scope)。参见 [ADR-0037](../decisions/adr/ADR-0037-model-distribution-via-public-hf-hub.md)。

验证发布结果:

```powershell
python scripts/verify_hf_publish.py `
  --repo SimpleJerry/longtu-nllb-zh2ko `
  --tag <new-run>-ckpt<N>    # 必须显式传 --tag，无默认值
```

## 5. 在 serving 配置中固定 revision(强制 — ADR-0038)

更新**两个**文件中的 `revision` 字段(必须保持一致,否则 drift-guard 测试失败):

| 文件 | 字段 |
|------|------|
| `configs/serving/docker.json` | `model.revision` |
| `demo/space.json` | `model.revision` |

新值:`<new-run>-ckpt<N>`(第 4 步产生的 tag)。

可选:若需在本地运行 serving,同步更新 `configs/serving/default.json` 的 `model.path` 为本地 checkpoint 目录。

## 6. 同步 Gradio Demo Space

将 `demo/space.json` 重新上传到 HF Spaces(或推送更新后的文件并触发 Space 同步)。参见 [ADR-0040](../decisions/adr/ADR-0040-public-gradio-demo-space.md)。

## 7. 更新六处规范位置的指标

以下六处必须显示一致的数字(或一致地指向 model card)。其中 `+X.XXX / ~NNx` 等**派生值**须从本次测试集结果重算，不得照抄:

| 文件 | 章节 / 字段 |
|------|------------|
| `README.md` (ko) | 결과 — BLEU / chrF / preservation 三数 |
| `README.en.md` | Results — 同上三数 |
| `README.zh-CN.md` | 成果 — 同上三数 |
| `docs/product/model-card.md` | 保留测试集结果 |
| `demo/app.py` | `_DESCRIPTION` 常量 |
| `demo/README.md` | 指标表 + revision 字段 |

此外，三个 README 的「사용/Usage/使用」代码片段中的 `tag` 变量须同步更新:

| 文件 | 行 |
|------|---|
| `README.md` | ≈75：`tag  = "earlystop-v1-ckpt48000"` |
| `README.en.md` | ≈96：`tag  = "earlystop-v1-ckpt48000"` |
| `README.zh-CN.md` | ≈75：`tag  = "earlystop-v1-ckpt48000"` |

## 8. 重新生成能力对比图

更新 `docs/figures/capability_comparison.data.json` 中的 `finetuned.*` 数字,然后重生成图:

```powershell
python scripts/plot_capability_comparison.py
```

产物:`docs/figures/capability_comparison.png`。参见 T1 交付物。

## 9. 更新 model-card 溯源(若语料变更)

若 `data/segments.csv` 发生变更,更新 `docs/product/model-card.md`:

- Run / 检查点 ID(第 4 步的 tag)
- 语料 SHA256(来自 `run_manifest.json`)
- 行数与各拆分大小

## 10. 验证

```powershell
pytest -n auto   # 全部通过(含 drift-guard, publish --tag 检查等)
```

可选冒烟检查:

```powershell
python scripts/serve.py --dry-run          # 配置校验
# docker run ... (serving 冒烟,见 ADR-0035)
# 确认 live demo 已加载新的 revision
```

端到端复现参考:[docs/reproducibility.md](../reproducibility.md)。

---

_参考 ADR:[ADR-0020](../decisions/adr/ADR-0020-formal-training-runs-require-split-artifacts-and-manifests.md) · [ADR-0023](../decisions/adr/ADR-0023-formal-experiments-use-held-out-test-splits.md) · [ADR-0031](../decisions/adr/ADR-0031-formal-training-uses-early-stopping-on-composite-metric.md) · [ADR-0034](../decisions/adr/ADR-0034-serving-contract-synchronous-http-api.md) · [ADR-0035](../decisions/adr/ADR-0035-docker-jenkins-deployment-contract.md) · [ADR-0037](../decisions/adr/ADR-0037-model-distribution-via-public-hf-hub.md) · [ADR-0038](../decisions/adr/ADR-0038-serving-pull-model-from-public-hf.md) · [ADR-0039](../decisions/adr/ADR-0039-packaging-pyproject-remove-syspath.md) · [ADR-0040](../decisions/adr/ADR-0040-public-gradio-demo-space.md) · [ADR-0041](../decisions/adr/ADR-0041-reproducibility-boundary-and-checkpoint-selection.md)_
