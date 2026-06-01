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

## 实现结果(2026-05-31 完成)

提取按以下提交分步落地(分支 `refactor/adr-0033-cleanup-core`,均一步一提交、每步全套测试 green):

| 步 | 内容 | 拆分粒度 | 验证 |
|----|------|----------|------|
| 1a | `llm_common.py` → `llm/client.py` + 包 re-export | git mv | 测试 import 改 src,patch 路径改 client 模块 |
| 1b | `cleanup_common.py` → `cleanup/common.py` | git mv | 5 脚本 + 测试改 import |
| 2 | `segments_llm` → 9 模块子包 | **细拆** | 测试全量迁 src import,patch 指向 `pipeline` |
| 3a | 为 `glossary_semantic`(原零测试)补 20 个 characterization 测试 | — | 纯函数 + score 不变量 + `enforce_strict_pairs` |
| 3b | `glossary_semantic` → `pipeline.py` | git mv 整搬 | 3a 测试改 src import |
| 4 | `glossary_llm` → 7 模块子包 | **细拆** | AST 逐字校验 0 differs |
| 5 | `segments_cleaning` → `pipeline.py` | git mv 整搬 | AST 0 differs + 现有测试 |
| 6 | `segments_glossary_cross` → `pipeline.py` | git mv 整搬 | AST 0 differs + 现有测试 |
| 7 | `segments_glossary_cross` 整搬版 → models/io/matching/scoring/classify/review + pipeline | **细拆** | AST 50/50 0 differs(基准=step6 整搬版 `62100cd`)+ 现有 8 测试 |
| 8a | 为 `segments_cleaning` 重路径补 16 个 characterization 测试 | — | mock stanza/jieba/kiwipiepy/embedding；不下载模型；249 tests pass |
| 8b | `segments_cleaning` 整搬版 → io/normalize/nlp/scoring/classify + 薄 pipeline | **细拆** | AST 40/40 0 differs(基准=step5 整搬版)；patch 目标改为 `classify` 模块；249 tests pass |
| 9a | 为 `glossary_semantic` 重路径补 15 个 characterization 测试 | — | mock stanza/jieba/kiwi/embedding；`write_outputs` 用 tempdir；264 tests pass |
| 9b | `glossary_semantic` 整搬版 → config/io/nlp/scoring/classify/review + 薄 pipeline | **细拆** | AST 42/42 0 differs(基准=step3b 整搬版)；RULES/PATTERNS/LEXICONS 通过 accessor fn 跨模块访问；264 tests pass |

**全部 5 个 pipeline 均已细拆为聚焦模块**:
- `segments_llm` / `glossary_llm`：models/prompts/response/validation/batch_state/io/review/pipeline
- `segments_glossary_cross`：models/io/matching/scoring/classify/review + pipeline(step 7)
- `segments_cleaning`：io/normalize/nlp/scoring/classify + 薄 pipeline(step 8b)
- `glossary_semantic`：config/io/nlp/scoring/classify/review + 薄 pipeline(step 9b)

**实现完成**:ADR-0033 所有 5 个 pipeline 的提取工作均已完成。

**实际偏差与纠正**:step 4(`glossary_llm`)初次实现一度凭印象重写而非逐字搬移,引入 4 处静默行为偏差(产物文件名、audit `keep` 大小写、`max_tokens` cap、prompt payload 缺键),既有测试未捕获。此后引入 **AST 逐字校验**(对比基准版本与拆分后全部顶层符号的 `ast.dump`,要求 0 missing / 0 differing / 0 重复冲突)作为细拆与整搬的统一 gate,并据此纠正 step 4、把关 step 5/6/7。

## 后续调整(Follow-up，ADR-0033 完成后)

**step 7 卫星合并**:`segments_glossary_cross/matching.py`(52 行)与 `scoring.py`(59 行)是各自 <60 行且唯一调用者均为 `classify.py` 的卫星模块,并入 `classify.py`(≈360 行)。AST-dump 逐字等价校验 0 differs(全部 16 个顶层函数一字不改,仅新增 `import re`、两段 section 注释),264 tests pass。

**batch_state 去重**:`segments_llm/batch_state.py` 与 `glossary_llm/batch_state.py` AST 完全等价(去 docstring 后 0 differs),抽取为 `cleanup/_batch_state.py` 共享。两个 `pipeline.py` 的 import 改为 `from .._batch_state import ...`。这是去重而非合并——并入各自 pipeline 会让重复固化。264 tests pass(含导入级冒烟验证)。

## 参考

- 相关:[ADR-0005](ADR-0005-gradual-engineering-refactor-approach.md)(渐进式重构原则)、[ADR-0006](ADR-0006-preserve-public-compatibility-by-default.md)(公开兼容性)、[ADR-0026](ADR-0026-cloud-llm-segment-cleanup-may-rewrite-korean-with-local-guards.md) / [ADR-0030](ADR-0030-llm-cleanup-defaults-to-batch-api-with-strict-json-schema.md)(被保护的清理行为)、[ADR-0032](ADR-0032-retire-phase-1-refactor-scaffolding.md)(phase-1 关闭,持久性结构决策走 ADR 系统)
- 驱动原则:CLAUDE.md「Architecture Principles / Thin interfaces, pure core」
- 相关代码:`scripts/segments_llm_cleanup_pipeline.py`、`scripts/glossary_*`、`scripts/segments_*`、`scripts/llm_common.py`、`scripts/cleanup_common.py`
- 相关文档:`docs/architecture/data-cleaning-pipeline.md`
