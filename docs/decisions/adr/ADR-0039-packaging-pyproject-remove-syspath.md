# ADR-0039: 打包为可安装包（pyproject + src-layout）并移除 sys.path 注入

| 字段 | 值 |
|------|----|
| 状态 | 已接受 |
| 日期 | 2026-06-03 |
| 关联 ADR | [ADR-0006](ADR-0006-preserve-public-compatibility-by-default.md)（公开兼容性契约，CLI 不变）、[ADR-0033](ADR-0033-extract-data-cleaning-core-into-src.md)（src-layout 基础）、[ADR-0035](ADR-0035-docker-jenkins-deployment-contract.md)（部署契约，Dockerfile 扩展）、[ADR-0038](ADR-0038-serving-pull-model-from-public-hf.md)（serving 入口） |

---

## 背景

ADR-0033 将全部可复用逻辑迁入 `src/longtu_translation_pipeline/`，确立了 src-layout 结构。
然而项目缺少打包元数据（无 `pyproject.toml` / `setup.py`），导致 `scripts/*.py` 与 `tests/*.py`
通过 `sys.path.insert(0, str(ROOT / "src"))` 手工注入来 import 本包。

此模式带来以下问题：

1. **脆弱性**：路径注入依赖 `__file__` 解析，不适用于 editable 安装或 zipimport 场景。
2. **可维护性**：每个文件都重复相同的 boilerplate；新增文件容易忘记注入。
3. **工具链兼容性**：IDE、类型检查器、`pytest` 插件均期望通过 Python 打包机制发现包，而非依赖路径黑魔法。
4. **部署一致性**：Docker 镜像当前以 `COPY src/ /app/src/` + 路径注入方式工作，而非安装包。

---

## 决策

### 1. 新增 `pyproject.toml`（打包元数据）

使用 setuptools src-layout 标准：

```toml
[build-system]
requires = ["setuptools>=70"]
build-backend = "setuptools.build_meta"

[project]
name = "longtu-translation-pipeline"
version = "0.1.0"
requires-python = ">=3.12"

[tool.setuptools.packages.find]
where = ["src"]
```

**关键约束**：
- `[project]` **不声明 `dependencies`**：运行时依赖仍以 `requirements*.txt` 为权威，由
  `pip install -r ...` 单独安装，避免 pyproject 重新解析依赖时覆盖 cu132 torch wheel。
- Editable 安装一律使用 `pip install -e . --no-deps`（只注册本包，不触碰已安装依赖）。
- `[project.scripts]` 暂不声明：CLI 仍通过 `python scripts/X.py <参数>` 调用（ADR-0006 不变）。

### 2. 移除 `sys.path.insert` 注入

**操作规则**：
- 每个 `sys.path.insert(0, str(ROOT / "src"))` 行删除。
- 若 `ROOT = Path(__file__).resolve().parents[1]` 仅为 sys.path 服务（脚本/测试体内不使用 ROOT），
  则同时删除该行及冗余的 `import sys` / `from pathlib import Path`。
- 若 ROOT 还用于其他目的（如 `--config` 默认值、`base_dir` 参数、`resolve_cli_path`），则
  **保留 ROOT**，只删除 sys.path.insert 行。
- `conftest.py` 不动（无 sys.path 注入；eager torch import 保留）。
- `scripts/publish_model.py`、`scripts/verify_hf_publish.py` 不 import 本包，无需处理。
- 删除 sys.path.insert 后，包 import 行的 `# noqa: E402` 注释随之删除（不再需要）。

**涉及文件（共 23 处注入）**：
- scripts/：evaluate_translation.py、glossary_llm_cleanup_pipeline.py、
  glossary_semantic_pipeline.py、run_inference.py、segments_cleaning_pipeline.py、
  segments_glossary_cross_cleaning_pipeline.py、segments_llm_cleanup_pipeline.py、
  serve.py、sweep_inference_params.py、train_model.py（10 个）
- tests/：test_cleanup_common.py、test_config.py、test_evaluation.py、
  test_glossary_llm_cleanup_pipeline.py、test_glossary_semantic_pipeline.py、
  test_inference_pipeline.py、test_llm_common.py、test_segments_cleaning_pipeline.py、
  test_segments_glossary_cross_cleaning.py、test_segments_llm_cleanup_pipeline.py、
  test_serving.py、test_text_protection.py、test_training_pipeline.py（13 个）

### 3. 安装步骤同步

**前提条件**：所有运行/测试前须先执行 `pip install -e . --no-deps` 安装本包。
`--no-deps` 保证不触碰 requirements*.txt 已安装的 cu132 torch 等依赖。

| 上下文 | 变更 |
|--------|------|
| GitHub Actions CI (`ci.yml`) | 在 `pip install -r requirements.txt -r requirements-dev.txt` 之后加 `pip install -e . --no-deps` |
| Jenkins Test 阶段 (`Jenkinsfile`) | 在同等 pip install 之后加 `pip install -e . --no-deps` |
| Dockerfile | `COPY pyproject.toml /app/`；在 `pip install -r requirements-serving.txt` 之后加 `RUN pip install --no-deps .` |
| 开发环境 / README | 在 requirements 安装之后加 `pip install -e .` 说明 |

### 4. CLI 不变（ADR-0006）

脚本仍以 `python scripts/X.py <参数>` 方式调用，参数/默认值/输出完全不变。
本 ADR 授权在 ADR-0006 "默认保留公开兼容性" 框架下增加一项前置步骤：运行或测试前需先
`pip install -e . --no-deps`（此为工具链要求，而非接口变更）。

---

## 备选方案

| 方案 | 放弃理由 |
|------|----------|
| 继续使用 sys.path 注入 | 脆弱、重复、工具链不兼容 |
| 在 pyproject 声明完整依赖 | cu132 torch 无法在 pyproject 中干净表达 extra-index；会与现有 requirements 冲突 |
| 使用 `setup.py` | setuptools 推荐 pyproject.toml；`setup.py` 已不推荐 |
| 在 pyproject 中声明 `[project.scripts]` | 可与 `python scripts/X.py` 共存，但为减少变更范围、确保 ADR-0006 不受影响，本 ADR 暂不声明 |

---

## 影响

- **src/longtu_translation_pipeline/**：零变动（业务逻辑不受影响）。
- **scripts/**：每个文件删除 sys.path.insert（及 ROOT/sys/Path 若仅供 sys.path 使用）。
- **tests/**：同上。
- **pyproject.toml**：新增。
- **Dockerfile**：新增 COPY pyproject.toml + RUN pip install --no-deps .。
- **ci.yml**：新增 pip install -e . --no-deps 步骤。
- **Jenkinsfile**：Test 阶段新增 pip install -e . --no-deps。
- **README×3**：setup 段新增 pip install -e . 说明。

---

## 验证

### 功能验证

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| 包可安装 | `pip install -e . --no-deps` | 无报错 |
| 全量测试 | `pytest` | 289 passed（数量与改前一致） |
| sys.path 残留 | `grep -rn "sys.path.insert" scripts/ tests/` | 无结果 |
| serve dry-run | `python scripts/serve.py --config configs/serving/default.json --dry-run` | 打印 serving config OK |
| train dry-run | `python scripts/train_model.py --config configs/training/default.json --dry-run` | 打印 training config OK |

### Docker 冒烟

| 检查项 | 结果 |
|--------|------|
| `docker build` | 成功 |
| `/health` | HTTP 200 |
| `/translate {"items":[{"id":"smoke","text":"攻击力增加50%"}]}` | 返回韩文非空翻译 |

冒烟详细记录见 `data/review/adr0039_docker_smoke.json`（gitignored）。
