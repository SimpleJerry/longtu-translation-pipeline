# Republish Checklist — New Checkpoint

Checklist for publishing a new trained checkpoint to replace or supplement
the current production model (`earlystop-v1-ckpt48000`).

---

## 1. Train

```powershell
python scripts/train_model.py \
  --config configs/training/earlystop.json \
  --train \
  --run-name <new-run>
```

Produces: run directory with checkpoints + `run_manifest.json`
(corpus SHA256, split seed/ratio, row counts, checkpoint path).

## 2. Evaluate

Run inference on the held-out test split, then compute metrics:

```powershell
python scripts/run_inference.py \
  --config configs/inference/default.json \
  --generate-test \
  --run-dir <run-dir>

python scripts/evaluate_translation.py \
  --config configs/evaluation/generation_report.json \
  --input <generated-csv>
```

Record new BLEU / chrF / glossary-preservation (no-space & exact).
Per [ADR-0023](../decisions/adr/ADR-0023-formal-experiments-use-held-out-test-splits.md):
test split is used **once** per model and never for checkpoint selection.

## 3. Publish to HF Hub

```powershell
python scripts/publish_model.py \
  --checkpoint <path-to-checkpoint-dir> \
  --tag <new-run>-ckpt<N>
```

Uploads curated inference files + `run_manifest.json`, refreshes the
model card, sets visibility to public. Requires `HF_TOKEN` (write scope).
See [ADR-0037](../decisions/adr/ADR-0037-model-distribution-via-public-hf-hub.md).

## 4. Pin the revision in serving configs (mandatory — ADR-0038)

Update `revision` field in **both** files:

| File | Field |
|------|-------|
| `configs/serving/docker.json` | `model.revision` |
| `demo/space.json` | `model.revision` |

New value: `<new-run>-ckpt<N>` (the tag from step 3).

## 5. Sync the Gradio Demo Space

Re-upload `demo/space.json` to HF Spaces (or push the updated file
and trigger a Space sync). See [ADR-0040](../decisions/adr/ADR-0040-public-gradio-demo-space.md).

## 6. Update metrics in the five canonical locations

All five must show the same numbers (or a consistent pointer to the model card):

| File | Section |
|------|---------|
| `README.md` (ko) | 프로젝트 현황 및 결과 |
| `README.en.md` | Project Status & Results |
| `README.zh-CN.md` | 项目状态与成果 |
| `docs/product/model-card.md` | 保留测试集结果 |
| `demo/app.py` | `_DESCRIPTION` constant |

## 7. Update model-card provenance (if corpus changed)

If `data/segments.csv` changed, update `docs/product/model-card.md`:

- Run/checkpoint ID (step 1 tag)
- Corpus SHA256 (from `run_manifest.json`)
- Row counts and split sizes

## 8. Verify

```powershell
pytest -n auto   # must stay green (currently 289 passed)
```

Optional smoke checks:
```powershell
python scripts/serve.py --dry-run          # config validation
# docker run ... (serving smoke, see ADR-0035)
# check live demo loads the new revision
```

---

_Reference ADRs: [ADR-0020](../decisions/adr/ADR-0020-formal-training-runs-require-split-artifacts-and-manifests.md) · [ADR-0023](../decisions/adr/ADR-0023-formal-experiments-use-held-out-test-splits.md) · [ADR-0031](../decisions/adr/ADR-0031-formal-training-uses-early-stopping-on-composite-metric.md) · [ADR-0034](../decisions/adr/ADR-0034-serving-contract-synchronous-http-api.md) · [ADR-0035](../decisions/adr/ADR-0035-docker-jenkins-deployment-contract.md) · [ADR-0037](../decisions/adr/ADR-0037-model-distribution-via-public-hf-hub.md) · [ADR-0038](../decisions/adr/ADR-0038-serving-pull-model-from-public-hf.md) · [ADR-0039](../decisions/adr/ADR-0039-packaging-pyproject-remove-syspath.md) · [ADR-0040](../decisions/adr/ADR-0040-public-gradio-demo-space.md)_
