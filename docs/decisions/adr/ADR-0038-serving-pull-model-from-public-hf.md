# ADR-0038: Serving 支持从公开 HF Hub 拉取模型

| 字段 | 值 |
|------|----|
| 状态 | 已接受 |
| 日期 | 2026-06-03 |
| 关联 ADR | [ADR-0034](ADR-0034-serving-contract-synchronous-http-api.md)（serving 契约）、[ADR-0035](ADR-0035-docker-jenkins-deployment-contract.md)（部署契约，扩展）、[ADR-0037](ADR-0037-model-distribution-via-public-hf-hub.md)（模型分发契约，落实 §3 revision 固定要求） |

---

## 背景

[ADR-0037](ADR-0037-model-distribution-via-public-hf-hub.md) §3 规定 serving 侧**必须**通过
`revision=<tag>` 固定拉取模型，禁止使用 `main` / 无 revision 拉取。但 ADR-0035 实现的
`docker.json` 使用本地卷挂载路径 `/models/checkpoint-48000`，需要在宿主机预先布置模型文件。

当前缺口：
- 发布镜像的使用者（含 Jenkins 自动部署）必须手动准备宿主机 `/models` 目录，部署摩擦较高。
- ADR-0037 §3 的 revision 固定要求在 serving 配置层没有配套实现（`InferenceModelConfig`
  无 `from_hub` / `revision` 字段）。

本 ADR 通过扩展配置 schema 和 provenance 读取逻辑，让 serving 能直接从公开 HF Hub
`SimpleJerry/longtu-nllb-zh2ko` 拉取模型权重，同时保留本地挂载路径作为开发/离线备选。

---

## 决策

### 1. Config Schema 扩展（向后兼容）

`InferenceModelConfig` 新增两个可选字段：

| 字段 | 类型 | 默认值 | 含义 |
|------|------|--------|------|
| `from_hub` | `bool` | `false` | `true` = HF Hub 拉取；`false` = 本地路径（ADR-0035 行为不变） |
| `revision` | `str \| null` | `null` | HF tag（如 `earlystop-v1-ckpt48000`）；`from_hub=true` 时**必填** |

约束：
- `from_hub=true` 时，`path` 保持 verbatim repo ID 字符串，**不**调用 `resolve_config_path`。
- `from_hub=true` 且 `revision` 缺失 → 启动时 `ValueError`，阻断 fail-fast（ADR-0034 sec 7）。
- `from_hub=false`（默认）时，行为与 ADR-0035 完全一致：`path` 经 `resolve_config_path` 解析。
- `tokenizer_name` 语义不变：HF-pull 时填 repo ID，本地时填本地路径，均为字符串。

### 2. revision 透传到 from_pretrained（inference.py）

`load_translator` 的两处 `from_pretrained` 调用均加 `revision=config.model.revision`：
- 本地 / 离线路径：`revision=None`，transformers 忽略该参数，行为零变化。
- HF-pull 路径：`revision="earlystop-v1-ckpt48000"` 固定拉取，满足 ADR-0037 §3。

### 3. Provenance 读取适配 HF（serving.py）

`_read_provenance` 支持 HF 分支：

```python
from huggingface_hub import hf_hub_download
local = hf_hub_download(repo_id=path, filename="run_manifest.json", revision=revision)
```

- token-free（公开 repo，无需 `HF_TOKEN`，ADR-0037 §5）。
- 网络/文件缺失等任何异常 → 返回 `None`（`/info` 容忍 `corpus_sha256=null`）。
- 本地分支行为不变。

### 4. 双配置策略

| 配置文件 | 用途 | model.from_hub |
|----------|------|----------------|
| `configs/serving/docker.json` | 发布镜像默认（CI/CD） | `true`；`revision="earlystop-v1-ckpt48000"` |
| `configs/serving/docker-localmount.json` | 开发/离线/B4 验证 | 省略（`false`）；本地挂载 `/models/checkpoint-48000` |

两个配置的 `language` / `glossary` / `output` / `generation` / `serving` 字段完全一致，
保持 ADR-0034 / ADR-0006 解码默认值不变。

### 5. Docker 与 Jenkins 适配

- **Dockerfile**：`HEALTHCHECK --start-period=600s` 容纳首次 ~2.3 GB HF 拉取（warm cache 后约 35 s）。
- **Jenkinsfile Deploy**：去掉 `-v MODEL_DIR:/models:ro`，改为持久化 HF 缓存卷
  `-v longtu_hf_cache:/home/appuser/.cache/huggingface`；HealthCheck 轮询上限放宽到 600 s。

### 6. 不变量

本 ADR **不**修改任何 ADR-0034 / ADR-0006 不变量：
- `/translate` / `/health` / `/info` schema 不变。
- 解码默认值不变（`num_beams=4`、`length_penalty=1.0`、`no_repeat_ngram_size=0`、`max_length=400`）。
- marker 策略不变。
- 模型权重绝不烘焙进镜像。
- 本地挂载路径保留（`docker-localmount.json`）。
- 拉取免 token；`HF_TOKEN` 仅发布时使用，不注入 serving 容器。

---

## 备选方案

| 方案 | 排除原因 |
|------|---------|
| 始终本地挂载（ADR-0035） | 部署摩擦高；使用者需手动准备 `/models`；与 ADR-0037 §3 revision 固定要求的 serving 侧配套实现方向相悖 |
| 在镜像构建时 bake 模型 | 违反 ADR-0035 §2「权重绝不烘焙进镜像」不变量；ADR-0037 §3 tag 管理与 Docker image tag 耦合 |
| 启动脚本手动 `huggingface-hub` CLI 下载 | 增加 entrypoint 复杂度；`from_pretrained(..., revision=...)` 原生已支持 HF 拉取 + cache |

---

## 后果

- 发布镜像可无卷挂载启动：首次从公开 HF 拉取 ~2.3 GB（几分钟），之后命中缓存约 35 s。
- Jenkins Deploy 阶段不再需要在宿主机预置 `/models` 目录；HF 缓存卷持久化，重建镜像不重复下载。
- `/info` 的 `corpus_sha256` / `seed` 由 `hf_hub_download("run_manifest.json")` 提供，网络异常时回落 `null`。
- 本地挂载方案（`docker-localmount.json`）完整保留，开发环境 / B4 验证 / 离线场景无需变更。
- 离线 CSV 推理路径（`from_hub` 默认 `false`）行为零变化。

---

## 实现结果 / 验证

**验证日期：** 待填写（容器内 HF-pull 冒烟后更新）

| Gate | 结果 |
|------|------|
| `pytest`（280 tests）全绿 | 待验证 |
| config 解析：`from_hub=true` + 无 `revision` → `ValueError` | 待验证 |
| config 解析：`from_hub=true` + `revision` → `path` 为 repo ID 字符串 | 待验证 |
| `_read_provenance` HF 分支：monkeypatch → 解析 `corpus_sha256` / `seed` | 待验证 |
| `_read_provenance` HF 分支：下载抛错 → 返回 `None` | 待验证 |
| `docker build` 成功 | 待验证 |
| `docker run`（无 `-v` 模型卷）首次 HF 拉取 → `GET /health` 200 | 待验证 |
| `/info` `corpus_sha256` / `seed` 非 null（来自 HF `run_manifest.json`） | 待验证 |
| `POST /translate` 返回韩文 | 待验证 |
| `torch.cuda.is_available() == True` | 待验证 |

完整报告：`data/review/deploy_smoke/REPORT_hfpull.md`（gitignored）
