"""compute_metrics factory for Seq2SeqTrainer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import numpy as np

from .evaluation import (
    GlossaryTerm,
    TranslationRow,
    compute_corpus_bleu,
    compute_glossary_preservation,
)
from .text_protection import strip_glossary_markers

if TYPE_CHECKING:
    pass


def make_compute_metrics(
    tokenizer,
    glossary_terms: list[GlossaryTerm],
    weight_bleu: float,
    weight_preservation_nospace: float,
    bleu_tokenization: str = "whitespace",
    bleu_max_order: int = 4,
    bleu_smooth_value: float = 0.1,
    validation_sources: list[str] | None = None,
) -> Callable:
    """Return a compute_metrics callable for Seq2SeqTrainer.

    glossary_terms must use evaluation.GlossaryTerm (fields: source, target).
    validation_sources is the list of original source texts in eval dataset order;
    required for accurate glossary preservation — if omitted, preservation is 0.
    """

    def compute_metrics(eval_pred) -> dict[str, float]:
        predictions, label_ids = eval_pred

        # Replace -100 padding sentinel with pad_token_id before decoding.
        # Seq2SeqTrainer pads both predictions and label_ids with -100 when
        # predict_with_generate=True and sequences have unequal lengths.
        pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else 0
        safe_preds = np.where(predictions == -100, pad_id, predictions)
        safe_labels = np.where(label_ids == -100, pad_id, label_ids)

        decoded_preds = tokenizer.batch_decode(safe_preds, skip_special_tokens=True)
        decoded_labels = tokenizer.batch_decode(safe_labels, skip_special_tokens=True)

        candidates = [strip_glossary_markers(p.strip()) for p in decoded_preds]
        references = [strip_glossary_markers(l.strip()) for l in decoded_labels]

        bleu_result = compute_corpus_bleu(
            references,
            candidates,
            tokenization=bleu_tokenization,
            max_order=bleu_max_order,
            smooth_value=bleu_smooth_value,
        )
        bleu_score = bleu_result.score

        if validation_sources is not None and glossary_terms:
            rows = [
                TranslationRow(
                    row_number=i + 1,
                    segment_id="",
                    source=validation_sources[i] if i < len(validation_sources) else "",
                    reference=references[i],
                    candidate=candidates[i],
                )
                for i in range(len(candidates))
            ]
            pres_result = compute_glossary_preservation(rows, glossary_terms)
            pres_exact = pres_result.preservation_rate_exact
            pres_nospace = pres_result.preservation_rate_nospace
        else:
            pres_exact = 0.0
            pres_nospace = 0.0

        composite = weight_bleu * bleu_score + weight_preservation_nospace * pres_nospace

        return {
            "bleu": bleu_score,
            "glossary_preservation_exact": pres_exact,
            "glossary_preservation_nospace": pres_nospace,
            "composite": composite,
        }

    return compute_metrics
