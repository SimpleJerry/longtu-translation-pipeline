# 数据清理说明

本文档说明最终训练文件背后的清理规则：

- `data/segments.csv`
- `data/glossary.csv`

原始 Excel/CSV 输入及本地审校 CSV 不提交版本库。审校产物生成于 `data/review/` 目录下，被 Git 忽略。

## 标记与样式标签

表现层标签会向模型引入类英文的人工 token，模型可能学习复制或翻译这些内容。

示例：

```text
zh-CN: <c=green>2%</c>\n<c=purple>攻击</c>
ko:    <c=green>2%</c>\n<c=purple>공격</c>
```

清理行为：

- 删除 `<c=green>`、`</c>`、`<hlgreen>` 等样式标签。
- 保留被包裹的文本，如 `2%`、`攻击`、`공격`。
- 保留机器占位符，如 `{0}` 和 `<key1>`，除非特定规则另有说明。

## 结构化字符串

部分行包含元组式 UI 字符串，而非单条对齐句子。

示例：

```text
zh-CN: {"标题","正文"}
ko:    {"제목","본문"}
```

清理行为：

- 若双侧均可解析且字段数相同，将其拆分为对齐的子行。
- 若仅一侧可解析、解析失败或字段数不一致，则删除源行并导出至本地审校。

这样可避免用实际包含多个不相关 UI 字段的行进行训练。

## 非语段片段

`segments.csv` 是 seq2seq 训练语料，应包含句子级或短语级翻译单元，而非无法作为训练样本的孤立片段。

示例：

```text
zh-CN: 艮
ko:    간
```

清理行为：

- 纯单字 CJK 片段以 `AUTO_REMOVE_NON_SEGMENT_FRAGMENT` 标记删除。
- 历史混合语料中的纯双字或三字 CJK 片段经过一次性迁移处理：从 `segments.csv` 中删除，仅将无冲突的可强制执行词对添加至 `glossary.csv`。
- 双字/三字迁移不是永久性流水线规则，仅为针对历史词条/语段混合问题的一次性修复。

## 目标语言污染

韩语目标端必须是韩语。目标端仍含中文或不含韩文字符的行不是可靠的 seq2seq 训练样本。

示例：

```text
zh-CN: 六壬秘境85级
ko:    六壬秘境85级
```

清理行为：

- 删除 `ko` 字段含 CJK 字符的行。
- 删除 `ko` 字段非空但不含韩文字符的行。
- 对当前语料采用有意为之的严格策略；不使用占位符、ID 或版本号白名单。

## 词汇表/语段交叉清理

词汇表与语段清理相互关联。实际语段翻译中无法强制执行的词汇表条目，不应删除有价值的句子数据；而强可执行术语也不应被训练行所矛盾。

清理行为：

- 以最长优先、不重叠的中文词汇表匹配方式扫描 `segments.csv`。
- 以精确匹配和无空格精确匹配方式检查韩语保留情况。
- 删除在当前语料中无法强制执行的词汇表条目。
- 删除仍缺失保留可执行词汇表术语的语段行。
- 永不自动改写韩语翻译。

在正式训练或最终保留测试集报告之前，运行：

```powershell
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check
```

预期的训练前门控结果为：

```text
strict_current_mismatch_rows=0
```

## LLM 词汇表清理

本地词汇表清理流水线是首选，因为它可复现且不会将公司术语发送至本地机器以外。若本地规则已无力处理剩余的语义噪声，可将可选的 LLM 清理步骤用作激进的仅删除操作。

候选示例：

```text
KEEP:   暴击 -> 치명타
REMOVE: 月亮 -> 달
REMOVE: 感谢有你 -> 함께해 주셔서 감사합니다
```

清理行为：

- 仅将 `term_id`、`zh-CN`、`ko` 词汇表行发送至兼容 OpenAI 的 Chat Completions API。
- 仅保留模型返回 `KEEP_GAME_TERM` 的行。
- 删除被分类为常用词、短语/句子内容、片段、错误词对或非公司游戏术语的行。
- 永不允许模型改写韩语翻译、添加条目或合并条目。
- 在 Git 忽略的 `data/review/llm_glossary_cleanup/` 下写入完整审计文件和原始批量请求信封。

所需环境：

```powershell
$env:OPENAI_API_KEY="<your-key>"
$env:LLM_MODEL="<your-model>"
# 可选：$env:OPENAI_BASE_URL="https://api.openai.com/v1"
venv\Scripts\python.exe scripts\glossary_llm_cleanup_pipeline.py --apply
```

LLM 清理后，在训练前重新运行严格词汇表/语段门控：

```powershell
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check
```

## LLM 语段清理

语段 LLM 清理步骤适用于本地规则已不足以区分可用训练对与语义噪声的全语料审校场景。它可以删除行，也可接受韩语改写，但仅在通过本地验证后方可执行。

候选示例：

```text
KEEP:   zh-CN: 挑战次数:{0}/{1}
        ko:    도전 횟수: {0}/{1}

REMOVE: zh-CN: 艮
        ko:    간

REWRITE zh-CN: 技能升级
        ko:    기술 강화
        corrected_ko: 스킬 강화
```

清理行为：

- 仅将 `segment_id`、`zh-CN`、`ko`、检测到的占位符及匹配的词汇表术语发送至兼容 OpenAI 的 Chat Completions API。
- 不向模型发送本地预判字段，如目标污染标志、结构化字符串提示、长度比标志或重复输出标志；这些检查仅在模型响应后执行。
- 要求模型以语义合理性独立审查每行，并给出行级具体原因，而非批量规则标签。
- 允许模型选择保留、删除、审校或韩语改写操作。
- 永不允许模型修改中文源文本、添加行、拆分行、合并行或编辑词汇表。
- 仅当改写非空、含韩文字符、不含中文 CJK、保留占位符、以精确或无空格匹配方式保留匹配词汇表术语，且通过基本长度/重复检查时，才应用韩语改写。
- 若改写未通过验证，则保留原行待审校，除非原韩语目标端已被污染；污染行直接删除。
- 在 `data/review/llm_segments_cleanup/` 下记录操作分布、重复原因警告、表面特征操作警告、改写接受/拒绝率及均衡样本审校。

命令：

```powershell
$env:OPENAI_API_KEY="<your-key>"
$env:LLM_MODEL="<your-model>"
venv\Scripts\python.exe scripts\segments_llm_cleanup_pipeline.py --dry-run
```

审查 `data/review/llm_segments_cleanup/` 后再使用 `--apply`。完整的语段 LLM 清理会使现有的 train/validation/test 拆分产物和模型报告失效。

不要将 ChatGPT 网页界面作为权威的全文件清理路径。它可能使用文件分析工具和类代码预处理，难以证明每行都经过了语义审查。若需使用网页界面，仅用于约 50–100 行的小型手动样本粘贴，并要求其不使用工具；仍应将结果视为审校证据，而非可直接覆盖语料的文件。
