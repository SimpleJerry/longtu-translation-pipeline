# Product Scope

This document describes the product and business scope of the longtu-translation-pipeline.

## Business Context

This project was developed during the author's tenure as a systems engineer at
LONGTU KOREA Inc. (龙图韩国, ㈜룽투코리아, now renamed STACO LINK Co., Ltd. / ㈜스타코링크).
The company operates mobile games in the Korean market and faced a substantial annual cost
for outsourcing Chinese-to-Korean game localization translation. The project goal is to
fine-tune an NLLB model on the company's proprietary parallel corpus, supplemented by
light human review, to automate the translation workflow and reduce outsourcing costs.

## Language Pair

- **Source language:** Simplified Chinese (`zh-CN`, NLLB code `zho_Hans`)
- **Target language:** Korean (`ko`, NLLB code `kor_Hang`)
- **Direction:** zh-CN → ko only (unidirectional fine-tuning)

## Domain

Game localization: UI strings, skill descriptions, item names, NPC dialogue, and game system
text for mobile RPG / action games. The terminology table (`data/glossary.csv`) covers
company-specific game terms, character names, and product-specific vocabulary.

## Data Policy

- Only final training corpora and glossary data are committed to the repository.
- Sensitive raw Excel/CSV inputs (original localization exports) are not committed.
- The committed corpus is strictly bilingual: `segment_id`, `zh-CN`, `ko` for segments;
  `term_id`, `zh-CN`, `ko` for glossary.

## Model

Base model: `facebook/nllb-200-distilled-600M` (fine-tuned on the cleaned parallel corpus).

Larger NLLB variants (1.3B, 3.3B) are not currently tested on this fine-tuned task.
See the README "Larger Models" section for cost/benefit discussion.

## Scope Boundaries

**In scope:**
- Local semantic pipeline for Chinese-Korean game glossary cleaning.
- Fine-tuning `facebook/nllb-200-*` on game localization data.
- Single `<start>...<end>` special-token terminology markers in translation.
- BLEU + chrF + glossary preservation evaluation on a held-out test split.
- Batch inference CLI for translating new Chinese text to Korean.

**Out of scope (current mainline):**
- T&N+R (`<middle>`) and `<code_id=N>` code/tag protection — preserved as historical
  experiments only.
- Korean → Chinese back-translation or reverse direction.
- Automatic deployment or production serving.
- Languages other than zh-CN and ko.

## References

- [README.en.md](../../README.en.md) — English project overview
- [README.zh-CN.md](../../README.zh-CN.md) — Chinese project overview
- [README.md](../../README.md) — Korean project overview
- [docs/architecture/data-cleaning-pipeline.md](../architecture/data-cleaning-pipeline.md) — data cleaning rules
