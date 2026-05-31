# ADR-0033：将数据清理 core 提取至 src/(cleanup/ 与 llm/),scripts/ 退化为薄入口

- 状态：已接受
- 日期：2026-05-31

## 背景

`src/longtu_translation_pipeline/` 是项目的 importable core(config / text_protection / training / inference / evaluation,带显式 `__all__`)。但数据清理与 LLM 清理的领域逻辑全部内嵌在 `scripts/` 入口脚本中,从未提取到 core:

| 入口脚本 | 行数(约) | 顶层 def / class |
|----------|----------|------------------|
| `scripts/segments_llm_cleanup_pipeline.py` | 1577 | 57 def + 6 class |
| `scripts/glossary_semantic_pipeline.py` | 1359 | — |
| `scripts/segments_cleaning_pipeline.py` | 1010 | — |
| `scripts/segments_glossary_cross_cleaning_pipeline.py` | 822 | — |
| `scripts/glossary_llm_cleanup_pipeline.py` | 742 | — |

这些脚本把可恢复 Batch API 状态机(`_run_chunked_batch_path` / `_load_state` / `_save_state_atomic`,见 ADR-0030)、改写校验(`validate_rewrite` / `term_preserved` / `has_bad_length_ratio` / `target_is_contaminated`,见 ADR-0026)、prompt 构造、响应解析、I/O 与编排混在单文件里。

它们不 import `src/`,而是通过 `scripts/cleanup_common.py`、`scripts/llm_common.py` 横向互相 import,并用如下双路径 hack 兼容两种运行方式:

```python
try:
    from llm_common import ...          # 直接运行脚本时
except ModuleNotFoundError:             # pragma: no cover
    from scripts.llm_common import ...  # 其它上下文
```

测试侧则各自 `sys.path.insert(0, str(ROOT / "scripts"))` 后按裸模块名导入(对比 src 测试统一 `sys.path.insert(0, str(ROOT / "src"))` 再按包名导入)。

这违反 CLAUDE.md「Architecture Principles / Thin interfaces, pure core —— 核心不得依赖入口脚本」,形成事实上的"两套 core"(`src/` 与 `scripts/`),并造成:复用困难(其它代码/测试只能挂 sys.path 反向导入)、单文件 I/O + HTTP + 编排 + 领域校验耦合、改动牵一发动全身。

ADR-0005 确立的增量提取(已提取 text_protection / training / inference / evaluation)在 ADR-0032 关闭 phase-1 时尚未覆盖清理层。本 ADR 把同一原则延伸到清理层,可视为 phase-2 core 提取。

## 决策

将清理与 LLM 领域逻辑提取到 `src/longtu_translation_pipeline/` 下两个新子包,`scripts/*.py` 退化为只含 argparse + `main()` + wiring 的薄入口:

- `src/longtu_translation_pipeline/llm/` —— LLM 传输与 Batch API(由 `scripts/llm_common.py` 迁入):`ClientConfig` / `resolve_client_config` / `call_chat_completion` / `parse_json_content` 及 Batch API 助手(`build_batch_request_line` / `upload_batch_input_file` / `create_batch` / `get_batch` / `wait_for_batch` / `download_batch_output`)。
- `src/longtu_translation_pipeline/cleanup/` —— 清理领域逻辑:
  - `common.py`(由 `scripts/cleanup_common.py` 迁入:csv / json / regex / term-file IO)。
  - 各清理阶段子模块,**以 `segments_llm` 为样板**:`models.py`(`SegmentRow` / `GlossaryTerm` / `Decision` / `RowOutcome` / `CleanupResult` 等)、`prompts.py`(response schema + `build_request_payload` + `classify_batch`)、`validation.py`(ADR-0026 改写保护)、`response.py`(解析 / 校验 / 截断恢复)、`batch_state.py`(ADR-0030 可恢复状态机)、`review.py`(审计 / 汇总 / CSV 写出)、`pipeline.py`(`run_cleanup` / `run_sync_path` / `run_batch_path` 编排)。
  - 精确模块边界在每个脚本各自的提取增量里敲定。

**行为保持(硬约束)**:本工作为纯行为保持搬迁,不夹带任何逻辑改动。

- 每个 `scripts/*.py` 的 CLI surface、参数、默认值与输出逐字不变(ADR-0006 公开兼容性)。
- `batch_state.json` 的阶段集合 `{init, input_written, uploaded, submitted, completed, downloaded}` 与原子写语义不变(ADR-0030)。
- 改写校验与删除 / 保留 / 审校判定逻辑不变(ADR-0026 及 invariants.md「LLM 清理政策」行)。
- 不新增第三方依赖(保留 urllib-only 审计面)。
- 唯一对外可见变化:删除 `try/except ModuleNotFoundError` 双导入 hack;测试 import 从 `sys.path.insert(ROOT/"scripts"); import X` 迁移到 `sys.path.insert(ROOT/"src"); from longtu_translation_pipeline.cleanup... import X`(与现有 src 测试一致)。`scripts.X` 内部 import 路径不属于 ADR-0006 所指"已记录公开 surface",故不触发破坏性变更流程。

**增量顺序(每次一个可审查提交,仓库每步保持 green)**:

1. `llm_common.py` → `llm/`、`cleanup_common.py` → `cleanup/common.py`;改写两个 LLM 脚本及其测试的 import,删除双导入 hack。(最小爆破半径,确立模式)
2. 拆 `segments_llm_cleanup_pipeline.py`(最大,~1577 行)为上述 cleanup 子模块,脚本只留薄入口。
3. 依次:`glossary_semantic_pipeline.py` → `segments_cleaning_pipeline.py` → `segments_glossary_cross_cleaning_pipeline.py` → `glossary_llm_cleanup_pipeline.py`。

**每步验证 gate**:对应 `tests/test_*.py` 现有 characterization 测试(行为基线)在 import 路径更新后全绿,加完整测试套件全绿。这些测试为纯 Python,无需私有数据或模型下载,符合 CLAUDE.md 数据-pipeline 测试规则。

## 后果

- `src/` 成为唯一 core;`scripts/` 退化为薄入口;消除"两套 core"与反向导入。
- 清理逻辑可被其它代码 / 测试直接 `import`,无需 sys.path hack。
- `docs/architecture/data-cleaning-pipeline.md` 中的命令仍有效(CLI 不变),仅需补一句"core 现位于 `src/.../cleanup/`"。
- 不触及任何不变量(本 ADR 不超越任何既有 ADR);ADR-0026 / ADR-0030 的行为契约由上述 gate 保护。
- 本 ADR 接受后:更新 ADR 索引 README;实现各增量时在提交信息引用本 ADR。

## 参考

- 相关:[ADR-0005](ADR-0005-gradual-engineering-refactor-approach.md)(渐进式重构原则)、[ADR-0006](ADR-0006-preserve-public-compatibility-by-default.md)(公开兼容性)、[ADR-0026](ADR-0026-cloud-llm-segment-cleanup-may-rewrite-korean-with-local-guards.md) / [ADR-0030](ADR-0030-llm-cleanup-defaults-to-batch-api-with-strict-json-schema.md)(被保护的清理行为)、[ADR-0032](ADR-0032-retire-phase-1-refactor-scaffolding.md)(phase-1 关闭,持久性结构决策走 ADR 系统)
- 驱动原则:CLAUDE.md「Architecture Principles / Thin interfaces, pure core」
- 相关代码:`scripts/segments_llm_cleanup_pipeline.py`、`scripts/glossary_*`、`scripts/segments_*`、`scripts/llm_common.py`、`scripts/cleanup_common.py`
- 相关文档:`docs/architecture/data-cleaning-pipeline.md`
