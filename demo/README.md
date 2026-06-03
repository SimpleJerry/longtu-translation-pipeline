---
title: Longtu zh-CN to ko Game Localization
emoji: 🎮
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.15.2
app_file: app.py
pinned: false
license: cc-by-nc-4.0
---

# Longtu zh-CN → ko Game Localization Demo

Fine-tuned **NLLB-200-distilled-600M** for Simplified Chinese → Korean game localization, trained on a proprietary parallel corpus from LONGTU KOREA Inc.

| Metric | Score |
|--------|-------|
| BLEU (whitespace) | 0.325 |
| chrF (max_n=6, β=2) | 0.590 |
| Glossary preservation (no-space) | 0.954 |

- Model: [`SimpleJerry/longtu-nllb-zh2ko`](https://huggingface.co/SimpleJerry/longtu-nllb-zh2ko) · revision `earlystop-v1-ckpt48000`
- Base: `facebook/nllb-200-distilled-600M` · beam=4 decoding
- GitHub: [SimpleJerry/longtu-translation-pipeline](https://github.com/SimpleJerry/longtu-translation-pipeline)
- License: CC-BY-NC-4.0

> Trained on proprietary game corpus; for research and portfolio use only (CC-BY-NC-4.0). The Space runs on free CPU hardware — first inference after wake-up may take up to a minute.
