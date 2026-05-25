from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.config import load_training_config  # noqa: E402
from longtu_translation_pipeline.training import (  # noqa: E402
    NllbTrainerSmokeResult,
    RealModelSmokeResult,
    TorchTrainingDataset,
    TokenizedTrainingExample,
    build_training_dry_run,
    build_training_smoke_test,
    format_nllb_trainer_smoke_test,
    format_real_model_smoke_test,
    format_training_dry_run,
    format_training_smoke_test,
    prepare_training_examples,
    shape_text,
    tokenize_training_examples,
)


class TrainingPipelineTest(unittest.TestCase):
    def test_dry_run_builds_deterministic_split_and_marks_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            segments_path = tmp_path / "segments.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "training.json"

            write_csv(
                segments_path,
                ["segment_id", "zh-CN", "ko"],
                [
                    {"segment_id": "1", "zh-CN": "打开神秘宝箱", "ko": "신비한 보물상자 열기"},
                    {"segment_id": "2", "zh-CN": "挑战次数:{0}", "ko": "도전 횟수: {0}"},
                    {"segment_id": "3", "zh-CN": "勇士竞技", "ko": "용맹의 결투장"},
                    {"segment_id": "4", "zh-CN": "领取奖励", "ko": "보상 수령"},
                    {"segment_id": "5", "zh-CN": "进入副本", "ko": "던전 입장"},
                ],
            )
            write_csv(
                glossary_path,
                ["term_id", "zh-CN", "ko"],
                [{"term_id": "1", "zh-CN": "神秘宝箱", "ko": "신비한 보물상자"}],
            )
            config_path.write_text(
                json.dumps(build_training_config(segments_path, glossary_path), ensure_ascii=False),
                encoding="utf-8",
            )

            config = load_training_config(config_path)
            first_plan = build_training_dry_run(config)
            second_plan = build_training_dry_run(config)

        self.assertEqual(first_plan.total_rows, 5)
        self.assertEqual(first_plan.validation_rows, 2)
        self.assertEqual(first_plan.train_rows, 3)
        self.assertEqual(first_plan.terminology_marker_scope, "preview_only")
        self.assertEqual(first_plan.preview_examples, second_plan.preview_examples)
        self.assertIn("terminology_marker_scope=preview_only", format_training_dry_run(first_plan))
        self.assertEqual(first_plan.preview_examples[0].source_text, "打开<start>神秘宝箱<end>")
        self.assertEqual(first_plan.preview_examples[0].target_text, "<start>신비한 보물상자<end> 열기")

    def test_terminology_marker_can_be_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            segments_path = tmp_path / "segments.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "training.json"

            write_csv(
                segments_path,
                ["segment_id", "zh-CN", "ko"],
                [{"segment_id": "1", "zh-CN": "打开神秘宝箱", "ko": "신비한 보물상자 열기"}],
            )
            write_csv(
                glossary_path,
                ["term_id", "zh-CN", "ko"],
                [{"term_id": "1", "zh-CN": "神秘宝箱", "ko": "신비한 보물상자"}],
            )
            config_data = build_training_config(segments_path, glossary_path)
            config_data["tokenization"]["terminology_markers"] = False
            config_path.write_text(json.dumps(config_data, ensure_ascii=False), encoding="utf-8")

            plan = build_training_dry_run(load_training_config(config_path))

        self.assertEqual(plan.preview_examples[0].source_text, "打开神秘宝箱")
        self.assertEqual(plan.preview_examples[0].target_text, "신비한 보물상자 열기")
        self.assertEqual(plan.terminology_marker_scope, "disabled")

    def test_empty_training_csv_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            segments_path = tmp_path / "segments.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "training.json"

            write_csv(segments_path, ["segment_id", "zh-CN", "ko"], [])
            write_csv(
                glossary_path,
                ["term_id", "zh-CN", "ko"],
                [{"term_id": "1", "zh-CN": "神秘宝箱", "ko": "신비한 보물상자"}],
            )
            config_path.write_text(
                json.dumps(build_training_config(segments_path, glossary_path), ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "No training examples found"):
                build_training_dry_run(load_training_config(config_path))

    def test_prepare_training_examples_marks_all_returned_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            segments_path = tmp_path / "segments.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "training.json"

            write_csv(
                segments_path,
                ["segment_id", "zh-CN", "ko"],
                [
                    {"segment_id": "1", "zh-CN": "普通文本", "ko": "일반 텍스트"},
                    {"segment_id": "2", "zh-CN": "打开神秘宝箱", "ko": "신비한 보물상자 열기"},
                ],
            )
            write_csv(
                glossary_path,
                ["term_id", "zh-CN", "ko"],
                [{"term_id": "1", "zh-CN": "神秘宝箱", "ko": "신비한 보물상자"}],
            )
            config_data = build_training_config(segments_path, glossary_path)
            config_data["dry_run"]["preview_rows"] = 1
            config_path.write_text(json.dumps(config_data, ensure_ascii=False), encoding="utf-8")

            examples = prepare_training_examples(load_training_config(config_path))

        self.assertEqual(examples[1].source_text, "打开<start>神秘宝箱<end>")
        self.assertEqual(examples[1].target_text, "<start>신비한 보물상자<end> 열기")

    def test_tokenization_uses_config_and_creates_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            segments_path = tmp_path / "segments.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "training.json"

            write_csv(
                segments_path,
                ["segment_id", "zh-CN", "ko"],
                [{"segment_id": "1", "zh-CN": "打开神秘宝箱", "ko": "신비한 보물상자 열기"}],
            )
            write_csv(
                glossary_path,
                ["term_id", "zh-CN", "ko"],
                [{"term_id": "1", "zh-CN": "神秘宝箱", "ko": "신비한 보물상자"}],
            )
            config_path.write_text(
                json.dumps(build_training_config(segments_path, glossary_path), ensure_ascii=False),
                encoding="utf-8",
            )

            config = load_training_config(config_path)
            tokenizer = RecordingTokenizer()
            examples = prepare_training_examples(config)
            tokenized = tokenize_training_examples(config, tokenizer, examples)

        self.assertEqual(len(tokenized), 1)
        self.assertEqual(tokenized[0].segment_id, "1")
        self.assertEqual(tokenized[0].input_ids, [18, 0, 0])
        self.assertEqual(tokenized[0].attention_mask, [1, 0, 0])
        self.assertEqual(tokenized[0].labels, [23, 0, 0])
        self.assertEqual(tokenizer.calls[0]["max_length"], 32)
        self.assertEqual(tokenizer.calls[0]["padding"], "max_length")
        self.assertTrue(tokenizer.calls[0]["truncation"])
        self.assertIn("<start>神秘宝箱<end>", tokenizer.calls[0]["texts"][0])
        self.assertIn("<start>신비한 보물상자<end>", tokenizer.calls[1]["texts"][0])

    def test_tokenization_prefers_text_target_labels_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            segments_path = tmp_path / "segments.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "training.json"

            write_csv(
                segments_path,
                ["segment_id", "zh-CN", "ko"],
                [{"segment_id": "1", "zh-CN": "领取奖励", "ko": "보상 수령"}],
            )
            write_csv(glossary_path, ["term_id", "zh-CN", "ko"], [])
            config_path.write_text(
                json.dumps(build_training_config(segments_path, glossary_path), ensure_ascii=False),
                encoding="utf-8",
            )

            tokenizer = TextTargetTokenizer()
            examples = prepare_training_examples(load_training_config(config_path))
            tokenized = tokenize_training_examples(
                load_training_config(config_path),
                tokenizer,
                examples,
            )

        self.assertEqual(tokenized[0].input_ids, [101, 0])
        self.assertEqual(tokenized[0].labels, [202, 0])
        self.assertEqual(tokenizer.source_texts, ["领取奖励"])
        self.assertEqual(tokenizer.target_texts, ["보상 수령"])

    def test_smoke_test_plan_records_language_codes_and_token_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            segments_path = tmp_path / "segments.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "training.json"

            write_csv(
                segments_path,
                ["segment_id", "zh-CN", "ko"],
                [
                    {"segment_id": "1", "zh-CN": "打开神秘宝箱", "ko": "신비한 보물상자 열기"},
                    {"segment_id": "2", "zh-CN": "领取奖励", "ko": "보상 수령"},
                ],
            )
            write_csv(
                glossary_path,
                ["term_id", "zh-CN", "ko"],
                [{"term_id": "1", "zh-CN": "神秘宝箱", "ko": "신비한 보물상자"}],
            )
            config_path.write_text(
                json.dumps(build_training_config(segments_path, glossary_path), ensure_ascii=False),
                encoding="utf-8",
            )

            tokenizer = RecordingTokenizer()
            plan = build_training_smoke_test(
                load_training_config(config_path),
                tokenizer,
                tokenizer_name="recording-tokenizer",
                sample_rows=2,
            )
            formatted = format_training_smoke_test(plan)

        self.assertEqual(plan.prepared_rows, 2)
        self.assertEqual(plan.tokenized_rows, 2)
        self.assertEqual(plan.terminology_marker_scope, "prepared_examples")
        self.assertEqual(tokenizer.src_lang, "zho_Hans")
        self.assertEqual(tokenizer.tgt_lang, "kor_Hang")
        self.assertIn("tokenizer=recording-tokenizer", formatted)
        self.assertIn("language_pair=zho_Hans->kor_Hang", formatted)
        self.assertIn("language_code_assignments=src_lang=zho_Hans;tgt_lang=kor_Hang", formatted)

    def test_torch_training_dataset_returns_tensor_batch(self) -> None:
        dataset = TorchTrainingDataset(
            [
                TokenizedTrainingExample(
                    segment_id="1",
                    input_ids=[1, 2, 0],
                    attention_mask=[1, 1, 0],
                    labels=[3, 4, 0],
                )
            ]
        )

        item = dataset[0]

        self.assertEqual(len(dataset), 1)
        self.assertEqual(item["input_ids"].tolist(), [1, 2, 0])
        self.assertEqual(item["attention_mask"].tolist(), [1, 1, 0])
        self.assertEqual(item["labels"].tolist(), [3, 4, 0])
        self.assertEqual(shape_text([[1, 2, 3], [4, 5, 6]]), "2 x 3")

    def test_nllb_trainer_smoke_result_format(self) -> None:
        result = NllbTrainerSmokeResult(
            config_path=Path("training.json"),
            segments_path=Path("segments.csv"),
            glossary_path=Path("glossary.csv"),
            tokenizer_name="facebook/nllb-200-distilled-600M",
            output_dir=Path("data/review/training_smoke"),
            source_code="zho_Hans",
            target_code="kor_Hang",
            target_language_token_id=256001,
            special_tokens_added=2,
            tokenizer_vocab_size=256204,
            max_length=32,
            prepared_rows=2,
            tokenized_rows=2,
            input_shape="2 x 32",
            label_shape="2 x 32",
            trainer_max_steps=1,
            train_loss=1.23,
        )

        formatted = format_nllb_trainer_smoke_test(result)

        self.assertIn("NLLB tokenizer / Trainer smoke-test result", formatted)
        self.assertIn("tokenizer=facebook/nllb-200-distilled-600M", formatted)
        self.assertIn("language_pair=zho_Hans->kor_Hang", formatted)
        self.assertIn("input_shape=2 x 32", formatted)
        self.assertIn("trainer_max_steps=1", formatted)

    def test_real_model_smoke_result_format(self) -> None:
        result = RealModelSmokeResult(
            config_path=Path("training.json"),
            segments_path=Path("segments.csv"),
            glossary_path=Path("glossary.csv"),
            model_name="facebook/nllb-200-distilled-600M",
            output_dir=Path("data/review/training_smoke/real_model"),
            source_code="zho_Hans",
            target_code="kor_Hang",
            target_language_token_id=256098,
            special_tokens_added=2,
            tokenizer_vocab_size=256206,
            embedding_size_before=256204,
            embedding_size_after=256206,
            parameter_count=615000000,
            device="cuda",
            cuda_device_name="NVIDIA Test GPU",
            cuda_memory_summary="allocated_gb=1.00;reserved_gb=2.00",
            torch_dtype="float16",
            max_length=400,
            prepared_rows=2,
            tokenized_rows=2,
            input_shape="2 x 400",
            label_shape="2 x 400",
            trainer_max_steps=1,
            train_loss=2.34,
        )

        formatted = format_real_model_smoke_test(result)

        self.assertIn("Real NLLB model Trainer smoke-test result", formatted)
        self.assertIn("model=facebook/nllb-200-distilled-600M", formatted)
        self.assertIn("embedding_size_before=256204", formatted)
        self.assertIn("embedding_size_after=256206", formatted)
        self.assertIn("device=cuda", formatted)
        self.assertIn("cuda_device_name=NVIDIA Test GPU", formatted)
        self.assertIn("torch_dtype=float16", formatted)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_training_config(segments_path: Path, glossary_path: Path) -> dict[str, object]:
    return {
        "data": {
            "segments_path": str(segments_path),
            "glossary_path": str(glossary_path),
            "source_column": "zh-CN",
            "target_column": "ko",
            "id_column": "segment_id",
        },
        "language": {"source_code": "zho_Hans", "target_code": "kor_Hang"},
        "model": {"base_model": "test-model", "output_dir": "out"},
        "split": {"validation_ratio": 0.4, "seed": 7},
        "tokenization": {
            "max_length": 32,
            "padding": "max_length",
            "truncation": True,
            "terminology_markers": True,
        },
        "training": {
            "num_train_epochs": 1,
            "per_device_train_batch_size": 1,
            "per_device_eval_batch_size": 1,
        },
        "dry_run": {"preview_rows": 2},
    }


class RecordingTokenizer:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        texts: list[str],
        max_length: int,
        padding: str,
        truncation: bool,
    ) -> dict[str, list[list[int]]]:
        self.calls.append(
            {
                "texts": texts,
                "max_length": max_length,
                "padding": padding,
                "truncation": truncation,
            }
        )
        return {
            "input_ids": [[len(text), 0, 0] for text in texts],
            "attention_mask": [[1, 0, 0] for _ in texts],
        }


class TextTargetTokenizer:
    def __init__(self) -> None:
        self.source_texts: list[str] = []
        self.target_texts: list[str] = []

    def __call__(
        self,
        texts: list[str],
        text_target: list[str],
        max_length: int,
        padding: str,
        truncation: bool,
    ) -> dict[str, list[list[int]]]:
        self.source_texts = texts
        self.target_texts = text_target
        return {
            "input_ids": [[101, 0] for _ in texts],
            "attention_mask": [[1, 0] for _ in texts],
            "labels": [[202, 0] for _ in text_target],
        }


if __name__ == "__main__":
    unittest.main()
