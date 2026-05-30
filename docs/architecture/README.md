# Architecture Documents

This directory contains system and pipeline architecture documentation.

## Documents

| File | Description |
|------|-------------|
| [invariants.md](invariants.md) | Authoritative catalogue of project invariants (data schema, split contract, marker shape, etc.), each bound to its ADR. Referenced by the constitution's Invariants section. |
| [data-cleaning-pipeline.md](data-cleaning-pipeline.md) | Data-cleaning rule notes with examples: style tags, structured strings, short fragments, target-language contamination, glossary/segment cross cleaning, and the strict gate. |

## Pipeline Overview

For the end-to-end pipeline overview (data cleaning → fine-tuning → evaluation → inference),
see the **Project Status & Results** section in the top-level README files:

- [README.md](../../README.md) (한국어)
- [README.en.md](../../README.en.md) (English)
- [README.zh-CN.md](../../README.zh-CN.md) (中文)
