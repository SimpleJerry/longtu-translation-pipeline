# 产品范围

本文档描述 longtu-translation-pipeline 的产品与业务范围。

## 业务背景

本项目由作者在 LONGTU KOREA Inc.（龙图韩国，㈜룽투코리아，现已更名为 STACO LINK Co., Ltd. / ㈜스타코링크）任职系统工程师期间开发。该公司在韩国市场运营手机游戏，每年需承担大量中文→韩文游戏本地化翻译的外包成本。本项目的目标是在公司自有平行语料上微调 NLLB 模型，辅以轻量级人工审校，以实现翻译工作流的自动化并降低外包支出。

## 语言对

- **源语言：** 简体中文（`zh-CN`，NLLB 代码 `zho_Hans`）
- **目标语言：** 韩语（`ko`，NLLB 代码 `kor_Hang`）
- **方向：** 仅 zh-CN → ko（单向微调）

## 领域

游戏本地化：UI 文本、技能描述、道具名称、NPC 对话及手机 RPG / 动作游戏的系统文本。术语表（`data/glossary.csv`）涵盖公司特有游戏术语、角色名称及产品专用词汇。

## 数据政策

- 仅将最终训练语料和词汇表数据提交至版本库。
- 敏感原始 Excel/CSV 输入（原始本地化导出文件）不提交。
- 已提交的语料为严格的双语格式：语段使用 `segment_id`、`zh-CN`、`ko` 字段；词汇表使用 `term_id`、`zh-CN`、`ko` 字段。

## 模型

基础模型：`facebook/nllb-200-distilled-600M`（在清洗后的平行语料上微调）。

更大的 NLLB 变体（1.3B、3.3B）目前未针对本微调任务进行测试。成本效益分析请参阅 README 的"更大模型"章节。

## 范围边界

**在范围内：**
- 中文→韩文游戏词汇表清理的本地语义pipeline。
- 在游戏本地化数据上微调 `facebook/nllb-200-*`。
- 翻译中使用单一 `<start>...<end>` 特殊标记保护术语。
- 在保留测试集上进行 BLEU + chrF + 词汇表保留率评估。
- 用于将新中文文本翻译为韩文的批量推理 CLI。
- 同步 HTTP/JSON 翻译服务（zh-CN → ko 单向），契约见 [ADR-0034](../decisions/adr/ADR-0034-serving-contract-synchronous-http-api.md)。
- Docker 容器化 + Jenkins CI/CD 部署自动化（含模型只读卷挂载协议与健康检查），见 [ADR-0035](../decisions/adr/ADR-0035-docker-jenkins-deployment-contract.md)。
- 微调权重通过**公开** Hugging Face Hub 仓库（`SimpleJerry/longtu-nllb-zh2ko`）版本化分发；仅推理必需文件 + `run_manifest.json` + model card 上传；git-style tag 固定 revision；拉取无需 token；license=cc-by-nc-4.0，见 [ADR-0037](../decisions/adr/ADR-0037-model-distribution-via-public-hf-hub.md)。

**不在范围内（当前主线）：**
- T&N+R（`<middle>`）和 `<code_id=N>` 代码/标签保护——仅保留为历史实验记录。
- 韩文 → 中文反向翻译。
- zh-CN 与 ko 以外的其他语言。

## 参考

- [README.en.md](../../README.en.md) — 英文项目概述
- [README.zh-CN.md](../../README.zh-CN.md) — 中文项目概述
- [README.md](../../README.md) — 韩文项目概述
- [docs/architecture/data-cleaning-pipeline.md](../architecture/data-cleaning-pipeline.md) — 数据清理规则
