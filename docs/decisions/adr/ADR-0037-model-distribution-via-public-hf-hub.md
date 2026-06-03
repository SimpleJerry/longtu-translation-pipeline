# ADR-0037: 模型分发契约——公开 Hugging Face Hub

| 字段 | 值 |
|------|----|
| 状态 | 已接受 |
| 日期 | 2026-06-03 |
| 取代 | [ADR-0036](ADR-0036-model-distribution-via-private-hf-hub.md)（模型分发契约——私有 HF Hub） |
| 关联 ADR | [ADR-0020](ADR-0020-formal-training-runs-require-split-artifacts-and-manifests.md)（run manifest）、[ADR-0034](ADR-0034-serving-contract-synchronous-http-api.md)（serving 契约，收口 Open Q2）、[ADR-0035](ADR-0035-docker-jenkins-deployment-contract.md)（部署契约，收口 Open Q2） |

---

## 背景

ADR-0036 决定将微调权重通过**私有** HF Hub 仓库分发，原始理由是"防止公司专有游戏语料及术语内容随模型一同公开"。
该决策已于 2026-06-03 被有意推翻：仓库 `SimpleJerry/longtu-nllb-zh2ko` **现已设为 PUBLIC**，目的是让他人也能下载并部署该模型。

做出这一改变需要明确回答两个问题：

1. **IP 暴露**：公开分发意味着任何人均可下载模型权重。权重中编码了公司专有游戏术语的翻译风格。本 ADR 经过评估后**明确接受此暴露**——原始语料文本本身未上传至 HF；权重仅体现翻译倾向，不含可还原的原始句对。
2. **许可证**：base 模型 `facebook/nllb-200-distilled-600M` 采用 CC-BY-NC-4.0（创作共用 — 署名 — 非商业性使用）。衍生件（本微调模型）须继承该许可证。发布许可 = **cc-by-nc-4.0**：他人可下载并部署，但不得用于商业目的。

ADR-0034 Open Q2（认证 / 访问控制）与 ADR-0035 Open Q2（TLS / 反向代理）在本 ADR 中给出更新答复，详见 §7。

---

## 决策

### 1. 分发渠道

微调模型**唯一**通过 Hugging Face Hub 的**公开**仓库分发：

```
SimpleJerry/longtu-nllb-zh2ko
```

不使用 Git LFS 直接提交、不使用自建对象存储。
公开仓库无需 `HF_TOKEN` 即可拉取权重；`HF_TOKEN`（write scope）仅在**发布**时使用。

### 2. 发布内容（推理必需文件 + provenance）

与 ADR-0036 保持一致，每次发布**仅上传**以下文件，排除训练态大文件（`optimizer.pt`、`rng_state.pth`、`scheduler.pt`、`trainer_state.json`、`training_args.bin`）：

| 文件 | 说明 |
|------|------|
| `config.json` | 模型架构配置 |
| `generation_config.json` | 解码默认值（num_beams 等） |
| `model.safetensors` | 模型权重（~2.3 GB） |
| `tokenizer.json` | 分词器词表 |
| `tokenizer_config.json` | 分词器配置 |
| `run_manifest.json` | provenance：`segments_sha256`、`split_seed`、训练命令、git commit 等（来自 ADR-0020） |
| `README.md` | model card（任务、base model、语言对、解码默认值、corpus SHA256、seed、license；不含语料/术语样例） |

### 3. 版本约定（tag）——与 ADR-0036 相同

每个已发布的检查点在 HF repo 上打一个 git-style tag，命名规则：

```
{run_name}-ckpt{step}
```

示例：`earlystop-v1-ckpt48000`

- serving 侧**必须**通过 `revision=<tag>` 固定拉取，禁止使用 `main` / 无 revision 拉取（防止静默覆盖）。
- 后续替换检查点时打新 tag，旧 tag 永久保留（可审计）。

### 4. Provenance 随模型走——与 ADR-0036 相同

`run_manifest.json` 一并上传到 HF repo 根目录。serving `/info` 端点从
`model_path` 的兄弟文件 `run_manifest.json` 读取 `corpus_sha256` 和 `seed`。

### 5. 凭证与公开性

- **拉取（推理 / 验证）**：公开仓库无需任何 token，直接 `from_pretrained(repo, revision=tag)` 即可。
- **发布（write）**：`HF_TOKEN`（write scope）**仅从环境变量** `os.environ["HF_TOKEN"]` 读取，不硬编码、不写入任何文件、不打印到日志。
- `--private False`（即公开）为 `scripts/publish_model.py` 的**默认值**。

运行前须手动注入会话（`.env` 不自动加载）：

```powershell
# PowerShell — 仅发布时需要 HF_TOKEN
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*)\s*$') {
        Set-Item "env:$($matches[1])" $matches[2].Trim()
    }
}
```

### 6. 发布脚本接口

`scripts/publish_model.py` 提供以下 CLI 参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--checkpoint` | `fine-tuned-models/nllb-200-distilled-600M/zh2ko/runs/earlystop-v1/checkpoint-48000` | 本地 checkpoint 目录路径 |
| `--run-manifest` | `<checkpoint>/../run_manifest.json`（自动推断） | run_manifest.json 路径 |
| `--repo` | `SimpleJerry/longtu-nllb-zh2ko` | HF Hub repo ID |
| `--tag` | `earlystop-v1-ckpt48000` | 发布 tag |
| `--private` | `False` | 仓库私有性（默认**公开**；首次建库时生效） |
| `--dry-run` | `False` | 打印拟操作，不实际上传 |

### 7. 收口说明

| 原始 Open Question | 来源 ADR | 本 ADR 答复（取代 ADR-0036 答复） |
|--------------------|----------|----------------------------------|
| Open Q2：认证 / 访问控制是否需要？ | ADR-0034 §8 | 模型拉取：**公开 repo，无需鉴权**。serving 服务本身若对外暴露，认证属部署基础设施范畴，不阻塞本 ADR |
| Open Q2：是否需要 TLS / 反向代理？ | ADR-0035 §9 | 模型拉取通道（HTTPS to HF Hub）由 HF 客户端处理，无需额外 token；服务暴露的 TLS 属部署基础设施，不阻塞本 ADR |

### 8. IP 暴露声明（明确接受）

本 ADR 经过评估后**明确接受**以下暴露：

- 模型权重中编码了公司专有游戏语料的翻译风格与术语偏好。
- 任何人均可下载权重，从而间接推断部分术语的翻译惯例。
- 原始语料文本（`data/segments.csv`、`data/glossary.csv`）**不**上传至 HF，仅存于本仓库（私有或受版本控制）。
- 接受此暴露的理由：模型的公开可用性具有正面价值（可复现性、社区可用性），且权重本身无法还原原始句对。

### 9. 许可证

```
cc-by-nc-4.0
```

继承自 base 模型 `facebook/nllb-200-distilled-600M`（CC-BY-NC-4.0）。
使用方：可自由下载、部署、修改，但**不得用于商业目的**；须保留署名。

---

## 备选方案

| 方案 | 排除原因 |
|------|---------|
| 保持私有 HF Hub 仓库（ADR-0036） | 与现实状态（repo 已公开）矛盾；限制了可复现性和社区价值 |
| Git LFS 直接提交模型 | 2.3 GB 权重超出 Git 工作流的合理边界；无 tag / revision 机制 |
| 自建对象存储（OSS / S3） | 需要额外基础设施；HF Hub 已支持 `revision=` 精确拉取 |
| 本地卷挂载（仅 ADR-0035） | 无法跨机器分发；无版本 / tag 管理 |

---

## 后果

- 任何人可无需 token 通过 `from_pretrained("SimpleJerry/longtu-nllb-zh2ko", revision="<tag>")` 拉取推理必需文件。
- `HF_TOKEN` 仅在执行 `publish_model.py` 时（write scope）需要；serving 容器、CI pull 无需注入 token。
- `optimizer.pt` 等训练态文件不入 HF repo，节省带宽并避免混淆。
- `run_manifest.json` 同步上传，provenance 可在任何部署环境中查询。
- 未来替换检查点时按命名规则打新 tag，旧版本永久可寻址。
- 模型 IP（术语翻译风格）对外可见；已按 §8 明确接受此暴露。
- 衍生使用须遵循 CC-BY-NC-4.0，使用方不得商用。
