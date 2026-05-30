# ADR-0001：README 与 AGENTS 不承载长期任务池

- 状态：已接受
- 日期：2026-05-17

## 背景

README 文件开始积累长期重构 TODO 列表和任务规划内容。AGENTS.md 也面临类似风险，有可能演变为工作规则与任务池的混合文件。这些文件是人类读者和 AI Agent 的主要入口；用任务跟踪内容填塞它们会降低信噪比，使其难以维护。

## 决策

README 文件（`README.md`、`README.en.md`、`README.zh-CN.md`）专注于项目介绍、安装、基本使用和导航链接。`AGENTS.md` 专注于 AI/Codex 工作规则。这两类文件均不承载长期重构 TODO 或任务池。

指向 `docs/decisions/adr/` 和模型卡片的简短导航链接可以保留；嵌入式任务列表则不可以。

## 后果

- 所有长期重构 TODO 在专用重构 backlog中追踪（现已退役；参见 ADR-0032）。
- README 文件保持可用的用户文档状态，不受内部规划内容干扰。
- 新的重构工作项必须添加至 backlog，而非写入 README 或 AGENTS。

## 参考

- 原始条目：第一阶段重构决策日志（已归档；参见 ADR-0032 及 git 标签 `phase-1-refactor-archive`）
- 相关待办条目：RF-009
