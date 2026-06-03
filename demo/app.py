"""Gradio Space entry point for the Longtu zh-CN → ko game localization demo."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import gradio as gr

from longtu_translation_pipeline.config import load_serving_config
from longtu_translation_pipeline.inference import load_translator, translate_texts
from longtu_translation_pipeline.text_protection import load_glossary_terms

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger(__name__)

_SPACE_DIR = Path(__file__).parent

cfg = load_serving_config(_SPACE_DIR / "space.json", base_dir=str(_SPACE_DIR))
_inf = cfg.inference

_log.info("Loading translator from HF Hub (this may take a few minutes on CPU)…")
_translator = load_translator(_inf, _inf.model.path, device="cpu")
_log.info("Translator loaded.")

_terms = (
    load_glossary_terms(_inf.glossary.path)
    if _inf.glossary.source_terminology_markers
    else []
)
_log.info("Loaded %d glossary terms.", len(_terms))


def translate(zh: str) -> tuple[str, str]:
    zh = zh.strip()
    if not zh:
        return "", ""
    try:
        result = translate_texts(_translator, [zh], _terms)[0]
    except Exception as exc:
        _log.exception("Translation failed: %s", exc)
        return "번역 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", ""

    matched_terms = [t.zh_cn for t in _terms if t.zh_cn and t.zh_cn in zh]
    terms_str = "、".join(matched_terms) if matched_terms else "—"
    return result, terms_str


_TITLE = "Longtu zh-CN → ko Game Localization Demo"

_DESCRIPTION = """
**Fine-tuned NLLB-200-distilled-600M** for Simplified Chinese → Korean game localization.

| Metric | Score |
|--------|-------|
| BLEU (whitespace) | **0.325** |
| chrF (max_n=6, β=2) | **0.590** |
| Glossary preservation (no-space) | **0.954** |

Model: [`SimpleJerry/longtu-nllb-zh2ko`](https://huggingface.co/SimpleJerry/longtu-nllb-zh2ko) · revision `earlystop-v1-ckpt48000` · beam=4 · base: `facebook/nllb-200-distilled-600M`

License: [CC-BY-NC-4.0](https://creativecommons.org/licenses/by-nc/4.0/) · [GitHub](https://github.com/SimpleJerry/longtu-translation-pipeline) · [Model Card](https://huggingface.co/SimpleJerry/longtu-nllb-zh2ko)

> ⏳ **CPU 환경이므로 첫 번역(및 슬립 후 웨이크업 시)에 수십 초가 소요됩니다. / CPU 环境，首次翻译（唤醒后）需要较长加载时间，请稍候。**
"""

_EXAMPLES = [
    ["攻击力增加50%"],
    ["打败BOSS-乱界之主可以获得稀有装备"],
    ["恭喜你完成了任务"],
    ["请前往地图选择下一个挑战"],
    ["使用技能会消耗法力值"],
]

with gr.Blocks(title=_TITLE) as demo:
    gr.Markdown(f"# {_TITLE}\n\n{_DESCRIPTION}")

    with gr.Row():
        with gr.Column():
            zh_input = gr.Textbox(
                label="中文输入 (zh-CN)",
                placeholder="请输入中文游戏文本，例如：攻击力增加50%",
                lines=3,
            )
            translate_btn = gr.Button("Translate", variant="primary")

        with gr.Column():
            ko_output = gr.Textbox(label="한국어 출력 (ko)", lines=3, interactive=False)
            terms_output = gr.Textbox(
                label="检测到的游戏术语 / 감지된 게임 용어",
                lines=1,
                interactive=False,
            )

    translate_btn.click(fn=translate, inputs=zh_input, outputs=[ko_output, terms_output])
    zh_input.submit(fn=translate, inputs=zh_input, outputs=[ko_output, terms_output])

    gr.Examples(examples=_EXAMPLES, inputs=zh_input, label="示例 / 예시")

if __name__ == "__main__":
    demo.launch()
