# ADR-0036: 模型分发契约——私有 Hugging Face Hub

| 字段 | 值 |
|------|----|
| 状态 | **已被 [ADR-0037](ADR-0037-model-distribution-via-public-hf-hub.md) 取代** |
| 日期 | 2026-06-02 |
| 取代者 | [ADR-0037](ADR-0037-model-distribution-via-public-hf-hub.md)（模型分发契约——公开 HF Hub，2026-06-03） |
| 关联 ADR | [ADR-0020](ADR-0020-formal-training-runs-require-split-artifacts-and-manifests.md)（run manifest）、[ADR-0034](ADR-0034-serving-contract-synchronous-http-api.md)（serving 契约，收口 Open Q1）、[ADR-0035](ADR-0035-docker-jenkins-deployment-contract.md)（部署契约，收口 Open Q2） |

---

## 背景

训练好的 NLLB-200-distilled-600M 微调检查点（最大 ~2.3 GB safetensors）需要一个可寻址的存储与分发渠道，使 serving 容器（ADR-0035）和未来的自动化部署能够按版本精确拉取权重，同时：

- 防止语料及术语内容随模型一同公开（公司专有数据）；
- 与 serving 侧的 `revision=` 固定拉取机制对齐；
- 使 provenance（语料 SHA256 / split seed）在非本地环境下仍然可查。

ADR-0034 Open Q1（目标运行环境尚未确定——影响 §6 并发模型与硬 SLA）与模型分发无关，保持开放；
ADR-0034 Open Q2（认证/访问控制）和 ADR-0035 Open Q2（TLS / 反向代理）均在本 ADR 的凭证与私有性章节中给出明确答案。

---

## 决策

### 1. 分发渠道

微调模型**唯一**通过 Hugging Face Hub 的**私有**仓库分发：

```
SimpleJerry/longtu-nllb-zh2ko
```

不使用公有仓库、不使用 Git LFS 直接提交、不使用自建对象存储。私有性保护公司专有游戏语料及术语，满足 ADR-0035 Open Q2（访问控制由 HF 私有 repo + HF_TOKEN 保障）。

### 2. 发布内容（推理必需文件 + provenance）

每次发布**仅上传**以下文件，排除训练态大文件（`optimizer.pt`、`rng_state.pth`、`scheduler.pt`、`trainer_state.json`、`training_args.bin`）：

| 文件 | 说明 |
|------|------|
| `config.json` | 模型架构配置 |
| `generation_config.json` | 解码默认值（num_beams 等） |
| `model.safetensors` | 模型权重（~2.3 GB） |
| `tokenizer.json` | 分词器词表 |
| `tokenizer_config.json` | 分词器配置 |
| `run_manifest.json` | provenance：`segments_sha256`、`split_seed`、训练命令、git commit 等（来自 ADR-0020） |
| `README.md` | 最小 model card（任务、base model、语言对、解码默认值、corpus SHA256、seed；不含语料/术语样例） |

### 3. 版本约定（tag）

每个已发布的检查点在 HF repo 上打一个 git-style tag，命名规则：

```
{run_name}-ckpt{step}
```

示例：`earlystop-v1-ckpt48000`

- serving 侧**必须**通过 `revision=<tag>` 固定拉取，禁止使用 `main` / 无 revision 拉取（防止静默覆盖）。
- 后续替换检查点时打新 tag，旧 tag 永久保留（可审计）。

### 4. Provenance 随模型走

`run_manifest.json` 一并上传到 HF repo 根目录。serving `/info` 端点从
`model_path` 的兄弟文件 `run_manifest.json` 读取 `corpus_sha256` 和 `seed`。

**后续任务（E1，不属于本 ADR 实现范围）**：修改 `serve.py` 使其在 HF Hub 拉取场景下也能正确定位 `run_manifest.json`（当前实现依赖本地挂载路径，ADR-0035 挂载协议已兼容，E1 仅需适配 HF cache 路径）。

### 5. 凭证与私有性

- `HF_TOKEN` **仅从环境变量** `os.environ["HF_TOKEN"]` 读取，不硬编码、不写入任何文件、不打印到日志。
- 运行前须手动注入会话（`.env` 不自动加载）：

  ```powershell
  # PowerShell
  Get-Content .env | ForEach-Object {
      if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*)\s*$') {
          Set-Item "env:$($matches[1])" $matches[2]
      }
  }
  ```

- 私有仓库 + HF_TOKEN 联合保障：未经授权无法拉取权重，满足 ADR-0035 Open Q2 所提认证/访问控制需求。

### 6. 发布脚本接口

`scripts/publish_model.py` 提供以下 CLI 参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--checkpoint` | `fine-tuned-models/nllb-200-distilled-600M/zh2ko/runs/earlystop-v1/checkpoint-48000` | 本地 checkpoint 目录路径 |
| `--run-manifest` | `<checkpoint>/../run_manifest.json`（自动推断） | run_manifest.json 路径 |
| `--repo` | `SimpleJerry/longtu-nllb-zh2ko` | HF Hub repo ID |
| `--tag` | `earlystop-v1-ckpt48000` | 发布 tag |
| `--private` | `True` | 仓库私有性（首次建库时生效） |
| `--dry-run` | `False` | 打印拟操作，不实际上传 |

### 7. 收口说明

| 原始 Open Question | 来源 ADR | 本 ADR 答复 |
|--------------------|----------|-------------|
| Open Q2：认证/访问控制是否需要？ | ADR-0034 §8 | 是：HF 私有 repo + `HF_TOKEN` 环境注入；服务内部网络可不另设认证层，外部暴露时另议 |
| Open Q2：是否需要 TLS/反向代理？ | ADR-0035 §9 | 模型拉取通道（HTTPS to HF Hub）已由 HF 客户端处理；服务暴露的 TLS 属部署基础设施，不阻塞本 ADR |

---

## 备选方案

| 方案 | 排除原因 |
|------|---------|
| 公有 HF Hub 仓库 | 会公开公司专有语料内容及术语风险 |
| Git LFS 直接提交模型 | 2.3 GB 权重超出 Git 工作流的合理边界；无 tag / revision 机制 |
| 自建对象存储（OSS / S3） | 需要额外基础设施；HF Hub 已支持 `revision=` 精确拉取 |
| 本地卷挂载（仅 ADR-0035） | 无法跨机器分发；无版本/tag 管理 |

---

## 后果

- serving 及 CI 可通过 `revision=<tag>` 从 HF Hub 拉取推理必需文件，权重不再依赖本机路径。
- `optimizer.pt` 等训练态文件不入 HF repo，节省带宽并避免混淆。
- `run_manifest.json` 同步上传，provenance 可在任何部署环境中查询（E1 之前，`/info` 在 HF 部署场景需手动配置挂载路径）。
- 未来替换检查点时按命名规则打新 tag，旧版本永久可寻址。
