# ADR-0035：部署契约 —— Docker 镜像 + Jenkins 流水线 + 模型挂载协议

- 状态：已接受
- 日期：2026-06-02

> 本 ADR 于 2026-06-02 接受。**接受时已同步**：ADR 状态 + 索引、[`scope.md`](../../product/scope.md)（部署自动化移入范围）、[`invariants.md`](../../architecture/invariants.md)（新增「部署契约」行）。

## 背景

[ADR-0034](ADR-0034-serving-contract-synchronous-http-api.md) 已定义了服务接口契约并实现了
FastAPI serving 层（冒烟全绿）。CLAUDE.md「Mission」要求项目终点是「a **deployable** zh-CN → ko
translation model that **serves inference**」——可部署意味着服务必须能在目标硬件上以可重现的方式
启动并对外提供服务，而不是仅仅在本机开发环境中运行。

当前缺口：

- 无容器化方案：服务启动依赖本机 venv 和本机模型路径，不可跨机复现。
- 无部署自动化：构建、测试、发布、健康检查全部手工，存在人为疏漏风险。
- 无模型发布协议：未明确哪些文件需要挂载、run manifest 如何被容器访问。

[`docs/product/scope.md`](../../product/scope.md) 目前将「自动化部署 / CI-CD 上线流水线」列在
**「不在范围」**——本 ADR 是将部署自动化从「未来 Mission」搬入「当前范围」的开关。

## 决策

定义一个 **Docker 镜像 + Jenkins 声明式 pipeline + 模型只读卷挂载** 的部署契约。

### 1. 目标运行环境

| 层 | 规格 |
|----|------|
| 宿主 OS | Windows 11（或等价的 Linux 宿主） |
| GPU | NVIDIA RTX 4070 Ti SUPER（驱动 595.97，支持 CUDA 13.2） |
| 容器运行时 | Docker Desktop + WSL2 后端 |
| GPU 直通 | `docker run --gpus all`（`nvidia-container-toolkit`，WSL2 下随 Docker Desktop 提供） |
| Python | 3.12（生产经过验证；3.14 在本机 native 栈上不稳，不用于部署镜像） |

### 2. Docker 镜像（不含 CUDA 基础镜像）

**关键技术决策**：`torch==2.12.0+cu132` 的 wheel 自带 CUDA 13.2 runtime，因此**不需要**
`nvidia/cuda` 基础镜像。使用 `python:3.12-slim`，单独通过 PyTorch whl index 安装 cu132 wheel
即可获得完整 GPU 支持。这将镜像构建与 NVIDIA Docker Hub 镜像解耦，复现性更强。

构建策略（Dockerfile 结构）：

1. `FROM python:3.12-slim` — 最小基础镜像
2. 安装 `curl`（用于 HEALTHCHECK）
3. **单独一个 RUN 层**安装 `torch==2.12.0+cu132`（~2 GB wheel；此层单独缓存，
   变更其他依赖时不触发重下载）
4. COPY `requirements-serving.txt`，安装服务运行时依赖（torch 已满足，pip 跳过）
5. COPY 应用代码：`src/`、`scripts/`、`configs/`、`data/glossary.csv`
6. 非 root 用户（uid 1000）
7. EXPOSE 8000
8. HEALTHCHECK（`curl /health`，`--start-period=90s` 容纳 ~30 s 冷启动）
9. CMD 使用 `configs/serving/docker.json`

**模型权重绝不 COPY 进镜像**（可复现性 + gitignore 政策）。

### 3. 依赖分层（requirements-serving.txt）

新增 `requirements-serving.txt`，固化 serving 运行时最小依赖集：

- `torch==2.12.0+cu132`（注明 cu132 wheel 来源）
- `transformers` / `tokenizers` / `safetensors` / `sentencepiece` / `huggingface-hub`
- `accelerate`（模型加载路径）
- `fastapi` / `uvicorn`（HTTP serving，ADR-0034）
- `numpy` / `pandas`（inference core + glossary CSV 读取）

不包含：`scikit-learn`、`sentence-transformers`、`stanza`、`jieba`、`kiwipiepy`、
`wordfreq`（数据清洗依赖，与推理无关），以及 `requirements-training.txt` 中的训练专用包。

### 4. 服务配置（configs/serving/docker.json）

复制 `default.json`，做三处变更：

| 字段 | default.json | docker.json | 原因 |
|------|-------------|-------------|------|
| `model.path` | 本机相对路径 | `/models/checkpoint-48000` | 挂载点 |
| `model.tokenizer_name` | `"facebook/nllb-200-distilled-600M"` | `/models/checkpoint-48000` | **离线启动**：checkpoint 目录已含 tokenizer 文件，指向本地路径可绕过 HuggingFace Hub 网络请求 |
| `serving.host` | `"127.0.0.1"` | `"0.0.0.0"` | 容器内需绑定所有接口以接受外部连接；宿主侧访问控制由 Docker 端口映射承担 |

其余字段（解码参数、marker、并发上限）与 `default.json` 完全相同，保持
ADR-0034 / ADR-0006 兼容性不变。

### 5. 模型卷与 provenance 协议

**宿主侧发布目录布局**（仅含推理所需文件，排除 optimizer.pt 等训练产物）：

```text
<host-publish-dir>/              # -v <host-publish-dir>:/models:ro
├── run_manifest.json            # → /models/run_manifest.json（provenance 读取路径）
└── checkpoint-48000/            # → /models/checkpoint-48000
    ├── config.json
    ├── generation_config.json
    ├── model.safetensors        # 推理权重 (~2.4 GB)
    ├── tokenizer.json
    └── tokenizer_config.json
```

`run_manifest.json` 放在 `checkpoint-48000` 的**父目录**（即 `/models/run_manifest.json`），
这与 `serving._read_provenance` 的查找路径（`model_path.parent / "run_manifest.json"`）一致，
保证 `/info` 的 `corpus_sha256` 与 `seed` 非 null（可审计性，ADR-0034 sec 5）。

`run_manifest.json` 来源：`fine-tuned-models/.../earlystop-v1/run_manifest.json`（已随
checkpoint 一同生成，ADR-0020）。

**docker run 命令**：

```bash
docker run -d \
    --name longtu-translation \
    --gpus all \
    -v <host-publish-dir>:/models:ro \
    -p 8000:8000 \
    --restart unless-stopped \
    longtu-translation-service:<tag>
```

### 6. Jenkins 声明式 Pipeline（Jenkinsfile）

五阶段：

| 阶段 | 内容 |
|------|------|
| **Checkout** | `checkout scm` |
| **Test** | CPU-only torch（与 `ci.yml` 相同）+ `requirements.txt` + `requirements-dev.txt`；`pytest --timeout=120`（`OMP_NUM_THREADS=1` / `TOKENIZERS_PARALLELISM=false`） |
| **Build** | `docker build -t <image>:<BUILD_NUMBER> .` |
| **Deploy** | 优雅停止旧容器 → `docker run --gpus all -v /models:ro -p 8000:8000 --restart unless-stopped` |
| **HealthCheck** | 轮询 GET `/health` 最多 24×5 s = 120 s；通过后 POST `/translate` 单条含术语冒烟；失败则停新容器（回滚） |

Test 阶段使用 CPU-only torch 是因为 Jenkins runner 可能不需要 GPU（与 CI 保持一致），且
训练全量测试套件不需要 GPU。

### 7. 不变量

本 ADR 不修改任何 ADR-0034 不变量：

- `/translate` / `/health` / `/info` schema 不变（ADR-0034 sec 2）
- 解码默认值不变（ADR-0006 / ADR-0034 sec 4）
- marker 策略不变（ADR-0010 / ADR-0028）
- 模型权重不进镜像、不提交 git（ADR-0015 / gitignore）

新增不变量（见 [`invariants.md`](../../architecture/invariants.md)）：
Docker 镜像使用 `python:3.12-slim`；模型通过只读卷挂载（绝不烘焙进镜像）；
provenance 挂载协议：`run_manifest.json` 位于 `/models/run_manifest.json`。

## 后果

**本 ADR 接受后须同步（各为独立的一次逻辑提交）：**

- [`docs/product/scope.md`](../../product/scope.md)：移除「自动化部署 / CI-CD 上线流水线」
  从「不在范围内」，在「在范围内」新增「Docker + Jenkins 部署自动化」并引用本 ADR。
- [`docs/architecture/invariants.md`](../../architecture/invariants.md)：新增「部署契约」行，
  绑定本 ADR（python:3.12-slim、只读卷、provenance 挂载协议）。
- 三语 README：在「基本流程」或「运行环境」节补充 Docker 部署简述（引用本 ADR，不复制易漂移数字）。

**实现产物（本次一次性交付）：**

| 文件 | 说明 |
|------|------|
| `Dockerfile` | 容器镜像构建规则 |
| `.dockerignore` | 排除模型权重、venv、测试、数据审查等大文件 |
| `configs/serving/docker.json` | 容器专用 serving 配置 |
| `requirements-serving.txt` | serving 运行时最小依赖集 |
| `Jenkinsfile` | 声明式 pipeline（5 阶段） |

**验证 gate（本机必须通过）：**

- `docker build` 成功；镜像不含模型权重（大小 ≈ 依赖体积）
- `docker run --gpus all` + 挂载模型卷：`/health` 200、`/info.corpus_sha256` 非 null、
  `/translate` 返回合格韩文
- 容器内 `torch.cuda.is_available() == True`
- Jenkins pipeline 全绿，HealthCheck 阶段通过

**Open Questions：**

1. 是否需要 TLS / 反向代理（Nginx / Caddy）在宿主侧暴露端口？当前契约仅至 HTTP 8000，
   加密层属部署基础设施范畴，不阻塞本 ADR。
2. 镜像仓库（registry）策略尚未定义（可选：本地 `docker save`、私有 registry 或 Docker Hub 私有仓库）。

## 参考

- 上游契约：[ADR-0034](ADR-0034-serving-contract-synchronous-http-api.md)（HTTP/JSON 服务契约）
- 绑定不变量：[ADR-0006](ADR-0006-preserve-public-compatibility-by-default.md)（解码默认值）、
  [ADR-0010](ADR-0010-text-protection-uses-single-segment-term-markers.md)（marker）、
  [ADR-0020](ADR-0020-formal-training-runs-require-split-artifacts-and-manifests.md)（run manifest）、
  [ADR-0028](ADR-0028-inference-uses-source-terminology-markers.md)（源端打 marker）
- 相关文件：[`Dockerfile`](../../../Dockerfile)、[`Jenkinsfile`](../../../Jenkinsfile)、
  [`configs/serving/docker.json`](../../../configs/serving/docker.json)、
  [`requirements-serving.txt`](../../../requirements-serving.txt)
