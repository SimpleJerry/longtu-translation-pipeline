# 模型卡片 — zh-CN → ko 翻译

longtu-translation-pipeline 项目当前已发布的模型。
本卡片是核心指标与模型溯源的持久存储位置；
宪法（[CLAUDE.md](../../CLAUDE.md)）和 README 均链接至此，而非在各处重复那些会随时间漂移的数字。

以下所有指标均绑定到特定的训练语料指纹。
`data/segments.csv` 的任何变更都会使这些指标失效，并需要重新评估
（参见 [ADR-0023](../decisions/adr/ADR-0023-formal-experiments-use-held-out-test-splits.md)）。

## 模型

| 字段 | 值 |
|------|-----|
| 任务 | 简体中文（`zh-CN`）→ 韩语（`ko`），游戏本地化 |
| 基础模型 | `facebook/nllb-200-distilled-600M` |
| 微调运行 | `run-full-earlystop-v1`，`checkpoint-48000` |
| 训练语料 | `data/segments.csv`，SHA256 `30D5C299828C10235AEE357E9333740913E55C291C5B07A45C0739E41818EA97` |
| 拆分 | 确定性 8:1:1，seed 42；测试集 = 6,626 保留行 |
| 术语标记 | 推理时将 `<start>...<end>` 应用于源端 |

## 训练方法

- 在验证子集上以复合指标（`0.5 · BLEU + 0.5 · glossary-preservation-nospace`）做早停；训练在第 49000 步（约 3.7 epoch）停止。参见 [ADR-0031](../decisions/adr/ADR-0031-formal-training-uses-early-stopping-on-composite-metric.md)。
- 已发布的检查点通过在**完整**验证集上对保留检查点重新排序选出，而非使用训练器循环内的自动最优检查点；最终选定 `checkpoint-48000`。

## 推理默认参数

通过仅在验证集上进行的参数扫描选定解码配置
（[ADR-0006](../decisions/adr/ADR-0006-preserve-public-compatibility-by-default.md) 约束对这些默认值的变更）：

| 参数 | 值 |
|------|-----|
| `num_beams` | 4 |
| `length_penalty` | 1.0 |
| `no_repeat_ngram_size` | 0 |
| `max_length` | 400 |

## 保留测试集结果

在保留测试集（6,626 行，seed 42）上的单次评估，
使用生产默认解码参数（束搜索）：

| 指标 | 分数 |
|------|------|
| BLEU（按空格分词） | 0.325 |
| chrF（max_n=6，β=2） | 0.590 |
| 词汇表保留率（无空格） | 0.954 |
| 词汇表保留率（精确） | 0.950 |
| 空输出行数 | 0 |

贪婪解码（`num_beams=1`）在同一测试集上得分 BLEU ≈ 0.319；束搜索提供了余下的小幅提升。

## 参考基准

- **训练中期诊断（非基准线）：** 一次早期 10k 步运行在 BLEU ≈ 0.198 时欠拟合，仅用于确认欠拟合方向，不作为衡量微调价值的基准线。
- **基础模型基准（RF-007-P5，完成于 2026-05-30）：** 未微调的 `facebook/nllb-200-distilled-600M` 在同一保留测试集上，以 `num_beams=4` 解码时得分 BLEU **0.009**、chrF **0.226**、词汇表保留率（无空格）**0.323**。因此微调 + 数据清理的净收益为 **+0.316 BLEU（约 34 倍）**，词汇表保留率 **+0.63**（≈32% → ≈95%）。基础模型能生成听起来流利的韩语，但完全无法正确处理游戏专有术语和角色名称；微调与清洗语料共同弥合了全部差距。

## 可复现性

运行清单（运行目录内的 `run_manifest.json`）记录了语料 SHA256、拆分 seed 与比例、行数及检查点路径。
运行目录、检查点和评估报告均被 Git 忽略
（[ADR-0004](../decisions/adr/ADR-0004-csv-in-git-raw-xlsx-outside-git-tracking.md)、
[ADR-0017](../decisions/adr/ADR-0017-generation-evaluation-reports-are-local-artifacts.md)）；
仅最终语料和配置文件被提交。
