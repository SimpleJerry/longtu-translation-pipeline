# ADR-0040: 发布公开 Gradio Demo Space（复用公开模型 + 可安装包）

| 字段 | 值 |
|------|----|
| 状态 | 已接受 |
| 日期 | 2026-06-03 |
| 关联 ADR | [ADR-0037](ADR-0037-model-distribution-via-public-hf-hub.md)（公开模型 HF Hub 分发）、[ADR-0039](ADR-0039-packaging-pyproject-remove-syspath.md)（可安装包）、[ADR-0028](ADR-0028-single-start-end-marker-pair.md)（`<start>...<end>` marker 逻辑） |

---

## 背景

ADR-0037 将微调权重公开发布到 HF Hub（`SimpleJerry/longtu-nllb-zh2ko`，revision `earlystop-v1-ckpt48000`），拉取无需 token。
ADR-0039 将本项目打包为可 `pip install` 的 Python 包，暴露 `config.load_serving_config`、`inference.load_translator`、`inference.translate_texts`、`text_protection.load_glossary_terms` 等公开 API。

目前尚无面向最终用户的在线试用入口。为作品集展示和外部验证，需要一个公开的交互式 Demo，让任何人无需搭建本地环境即可体验 zh-CN → ko 游戏本地化翻译效果。

---

## 决策

在 Hugging Face Spaces 上创建并维护一个公开 Gradio Space（`SimpleJerry/longtu-nllb-zh2ko-demo`），作为**纯下游消费者**：

- 不复制或重实现推理逻辑；通过 `pip install git+...@main` 直接复用 ADR-0039 的可安装包。
- 不重新托管模型权重；通过 ADR-0037 的 HF Hub 公开 revision 在运行时拉取。
- 在 Space 内自包含 `glossary.csv`（从 `data/glossary.csv` 拷贝），主 repo 不提交重复文件。
- 运行在 HF 免费 CPU tier；无 GPU 依赖，无需任何 token 即可访问。

### 实现范围（`demo/` 目录，独立分支 `feat/gradio-space`）

| 文件 | 用途 |
|------|------|
| `demo/app.py` | Gradio Blocks 应用；模块级加载一次；`translate()` 函数调用 `translate_texts` |
| `demo/space.json` | serving 配置（`from_hub=true`，`glossary.path="glossary.csv"`，`device=cpu`） |
| `demo/requirements.txt` | CPU 运行时依赖（不含 `transformers` 以外的训练依赖） |
| `demo/README.md` | HF Space card（YAML front-matter + 指标 + 链接） |

---

## 理由

- **增量、非破坏性**：不触及 `src/` 业务逻辑、serving/部署/分发契约；Demo 仅消费既有公开资产。
- **复用 ADR 成果**：ADR-0037 的公开模型 + ADR-0039 的可安装包 + ADR-0028 的 marker 注入/剥离，一行 pip install 全部获得。
- **作品集价值**：公开交互式演示可向外部验证 BLEU 0.325 / chrF 0.590 / 术语保留 0.954 的实际翻译效果。
- **成本为零**：HF 免费 CPU Space，闲时自动 sleep，无持续费用。

---

## 约束

- HF_TOKEN（write 权限）仅在部署时从环境变量读取，绝不入库或打印。
- Space 为公开（public）；访问无需 token。
- `glossary.csv` 在 Space 内自包含；主 repo 不提交 `demo/glossary.csv`（部署脚本运行时拷贝 `data/glossary.csv` → Space 根目录）。
- 若 Space 因 HF 平台变更不可用，不影响主 repo 的任何契约。

---

## 后续

- Space URL：`https://huggingface.co/spaces/SimpleJerry/longtu-nllb-zh2ko-demo`
- 三语 README 与 `docs/product/scope.md` 均已新增 Live Demo 链接。
- 如将来 API 发生 breaking change（ADR-0034 相关），需同步更新 `demo/app.py`。
