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
    FormalTrainingRunResult,
    NllbTrainerSmokeResult,
    RealModelPilotTrainingResult,
    RealModelSmokeResult,
    TorchTrainingDataset,
    TrainingExample,
    TokenizedTrainingExample,
    _build_seq2seq_trainer,
    build_trainer,
    build_training_dry_run,
    build_training_smoke_test,
    checkpoint_step,
    find_latest_checkpoint,
    format_formal_training_run,
    format_nllb_trainer_smoke_test,
    format_real_model_pilot_training,
    format_real_model_smoke_test,
    format_training_dry_run,
    format_training_smoke_test,
    resolve_formal_run_dir,
    resolve_resume_row_limit,
    resolve_resume_checkpoint,
    list_checkpoint_paths,
    prepare_training_examples,
    read_manifest_row_limit,
    run_real_nllb_formal_training,
    shape_text,
    split_examples,
    tokenize_training_examples,
    write_split_artifacts,
)
from longtu_translation_pipeline.training_metrics import make_compute_metrics  # noqa: E402


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
        self.assertEqual(first_plan.train_rows, 3)
        self.assertEqual(first_plan.validation_rows, 1)
        self.assertEqual(first_plan.test_rows, 1)
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

    def test_checkpoint_helpers_ignore_non_numeric_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "checkpoint-2").mkdir()
            (tmp_path / "checkpoint-final").mkdir()
            (tmp_path / "checkpoint-10").mkdir()
            (tmp_path / "other").mkdir()

            checkpoints = list_checkpoint_paths(tmp_path)

            self.assertEqual([checkpoint.name for checkpoint in checkpoints], ["checkpoint-2", "checkpoint-10"])
            self.assertEqual(find_latest_checkpoint(tmp_path).name, "checkpoint-10")

    def test_formal_run_dir_uses_runs_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            segments_path = tmp_path / "segments.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "training.json"
            config_data = build_training_config(segments_path, glossary_path)
            config_data["model"]["output_dir"] = str(tmp_path / "fine-tuned")
            config_path.write_text(json.dumps(config_data, ensure_ascii=False), encoding="utf-8")

            config = load_training_config(config_path)
            run_dir = resolve_formal_run_dir(config, run_name="run-test")

        self.assertEqual(run_dir, tmp_path / "fine-tuned" / "runs" / "run-test")

    def test_formal_training_requires_explicit_max_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            segments_path = tmp_path / "segments.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "training.json"
            config_path.write_text(
                json.dumps(build_training_config(segments_path, glossary_path), ensure_ascii=False),
                encoding="utf-8",
            )

            config = load_training_config(config_path)

        with self.assertRaisesRegex(ValueError, "requires max_steps"):
            run_real_nllb_formal_training(config)

    def test_split_examples_uses_deterministic_8_1_1_three_way_split(self) -> None:
        examples = [
            TrainingExample(str(index), f"zh-{index}", f"ko-{index}")
            for index in range(10)
        ]

        first_train, first_validation, first_test = split_examples(
            examples,
            train_ratio=0.8,
            validation_ratio=0.1,
            test_ratio=0.1,
            seed=42,
        )
        second_train, second_validation, second_test = split_examples(
            examples,
            train_ratio=0.8,
            validation_ratio=0.1,
            test_ratio=0.1,
            seed=42,
        )

        self.assertEqual(len(first_train), 8)
        self.assertEqual(len(first_validation), 1)
        self.assertEqual(len(first_test), 1)
        self.assertEqual(first_validation, second_validation)
        self.assertEqual(first_test, second_test)
        self.assertEqual(first_train, second_train)

    def test_split_artifacts_write_raw_train_validation_and_test_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            train_path, validation_path, test_path = write_split_artifacts(
                output_dir,
                [TrainingExample("1", "打开神秘宝箱", "신비한 보물상자 열기")],
                [TrainingExample("2", "领取奖励", "보상 수령")],
                [TrainingExample("3", "挑战BOSS", "보스 도전")],
                id_column="segment_id",
                source_column="zh-CN",
                target_column="ko",
            )

            train_rows = read_csv_rows(train_path)
            validation_rows = read_csv_rows(validation_path)
            test_rows = read_csv_rows(test_path)

        self.assertEqual(train_rows[0]["segment_id"], "1")
        self.assertEqual(train_rows[0]["zh-CN"], "打开神秘宝箱")
        self.assertEqual(validation_rows[0]["ko"], "보상 수령")
        self.assertEqual(test_rows[0]["segment_id"], "3")

    def test_resolve_resume_checkpoint_accepts_latest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "checkpoint-2").mkdir()
            (tmp_path / "checkpoint-4").mkdir()

            checkpoint = resolve_resume_checkpoint(tmp_path, "latest")

        self.assertEqual(checkpoint.name, "checkpoint-4")

    def test_checkpoint_step_parses_numeric_checkpoint_name(self) -> None:
        self.assertEqual(checkpoint_step(Path("checkpoint-42")), 42)
        self.assertIsNone(checkpoint_step(Path("checkpoint-final")))

    def test_manifest_row_limit_can_be_reused_for_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "run_manifest.json").write_text(
                json.dumps({"data": {"row_limit": 128}}),
                encoding="utf-8",
            )

            row_limit = read_manifest_row_limit(tmp_path)

        self.assertEqual(row_limit, 128)

    def test_resume_row_limit_must_match_manifest_when_explicit(self) -> None:
        self.assertEqual(resolve_resume_row_limit(None, 128), 128)
        self.assertEqual(resolve_resume_row_limit(128, 128), 128)
        with self.assertRaisesRegex(ValueError, "resume row_limit"):
            resolve_resume_row_limit(256, 128)

    def test_formal_training_result_format(self) -> None:
        result = FormalTrainingRunResult(
            config_path=Path("training.json"),
            segments_path=Path("segments.csv"),
            glossary_path=Path("glossary.csv"),
            model_name="facebook/nllb-200-distilled-600M",
            output_dir=Path("fine-tuned-models/model/runs/run-test"),
            manifest_path=Path("fine-tuned-models/model/runs/run-test/run_manifest.json"),
            train_split_path=Path("fine-tuned-models/model/runs/run-test/splits/train.csv"),
            validation_split_path=Path("fine-tuned-models/model/runs/run-test/splits/validation.csv"),
            test_split_path=Path("fine-tuned-models/model/runs/run-test/splits/test.csv"),
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
            cuda_memory_summary="allocated_gb=2.00;reserved_gb=4.00",
            torch_dtype="float32+bf16_trainer",
            max_length=400,
            total_rows=75462,
            row_limit=128,
            segments_sha256="ABCDEF",
            split_seed=42,
            train_ratio=0.8,
            validation_ratio=0.1,
            test_ratio=0.1,
            train_rows=102,
            validation_rows=12,
            test_rows=14,
            tokenized_train_rows=102,
            tokenized_validation_rows=12,
            input_shape="103 x 400",
            label_shape="103 x 400",
            max_steps=4,
            save_steps=2,
            eval_steps=2,
            save_total_limit=2,
            logging_steps=1,
            gradient_accumulation_steps=1,
            learning_rate=0.00002,
            warmup_ratio=0.03,
            weight_decay=0.01,
            max_grad_norm=1.0,
            resume_checkpoint=Path("fine-tuned-models/model/runs/run-test/checkpoint-2"),
            checkpoint_paths=[
                Path("fine-tuned-models/model/runs/run-test/checkpoint-2"),
                Path("fine-tuned-models/model/runs/run-test/checkpoint-4"),
            ],
            train_loss=12.5,
            eval_loss=11.5,
            final_global_step=4,
        )

        formatted = format_formal_training_run(result)

        self.assertIn("Real NLLB formal training run result", formatted)
        self.assertIn("manifest=fine-tuned-models", formatted)
        self.assertIn("train_split=fine-tuned-models", formatted)
        self.assertIn("test_split=fine-tuned-models", formatted)
        self.assertIn("row_limit=128", formatted)
        self.assertIn("split_ratios=0.8:0.1:0.1", formatted)
        self.assertIn("test_rows=14", formatted)
        self.assertIn("eval_steps=2", formatted)
        self.assertIn("learning_rate=2e-05", formatted)
        self.assertIn("eval_loss=11.5", formatted)

    def test_real_model_pilot_training_result_format(self) -> None:
        result = RealModelPilotTrainingResult(
            config_path=Path("training.json"),
            segments_path=Path("segments.csv"),
            glossary_path=Path("glossary.csv"),
            model_name="facebook/nllb-200-distilled-600M",
            output_dir=Path("fine-tuned-models/model/pilot/run-20260525-120000"),
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
            cuda_memory_summary="allocated_gb=2.00;reserved_gb=4.00",
            torch_dtype="float32+bf16_trainer",
            max_length=400,
            prepared_rows=64,
            tokenized_rows=64,
            input_shape="64 x 400",
            label_shape="64 x 400",
            first_stage_steps=2,
            final_max_steps=4,
            save_steps=2,
            resume_checkpoint=Path("fine-tuned-models/model/pilot/run-20260525-120000/checkpoint-2"),
            checkpoint_paths=[
                Path("fine-tuned-models/model/pilot/run-20260525-120000/checkpoint-2"),
                Path("fine-tuned-models/model/pilot/run-20260525-120000/checkpoint-4"),
            ],
            first_stage_loss=14.5,
            final_train_loss=13.75,
            final_global_step=4,
        )

        formatted = format_real_model_pilot_training(result)

        self.assertIn("Real NLLB model pilot training result", formatted)
        self.assertIn("first_stage_steps=2", formatted)
        self.assertIn("final_max_steps=4", formatted)
        self.assertIn("resume_checkpoint=fine-tuned-models", formatted)
        self.assertIn("checkpoint-4", formatted)
        self.assertIn("torch_dtype=float32+bf16_trainer", formatted)
        self.assertIn("final_global_step=4", formatted)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


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
        "split": {
            "train_ratio": 0.6,
            "validation_ratio": 0.2,
            "test_ratio": 0.2,
            "seed": 7,
        },
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


class EarlyStoppingConfigTest(unittest.TestCase):
    def _make_earlystop_config(self, tmp_path: Path) -> Path:
        segments_path = tmp_path / "segments.csv"
        glossary_path = tmp_path / "glossary.csv"
        config_path = tmp_path / "training.json"
        write_csv(
            segments_path,
            ["segment_id", "zh-CN", "ko"],
            [{"segment_id": "1", "zh-CN": "打开神秘宝箱", "ko": "신비한 보물상자 열기"}],
        )
        write_csv(glossary_path, ["term_id", "zh-CN", "ko"], [])
        config_data = build_training_config(segments_path, glossary_path)
        config_data["training"]["load_best_model_at_end"] = True
        config_data["training"]["metric_for_best_model"] = "eval_composite"
        config_data["training"]["greater_is_better"] = True
        config_data["training"]["early_stopping_patience"] = 5
        config_data["training"]["early_stopping_threshold"] = 0.0
        config_data["training"]["lr_scheduler_type"] = "cosine"
        config_path.write_text(json.dumps(config_data, ensure_ascii=False), encoding="utf-8")
        return config_path

    def test_training_args_config_parses_early_stopping_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self._make_earlystop_config(Path(tmp))
            config = load_training_config(config_path)

        self.assertTrue(config.training.load_best_model_at_end)
        self.assertEqual(config.training.metric_for_best_model, "eval_composite")
        self.assertTrue(config.training.greater_is_better)
        self.assertEqual(config.training.early_stopping_patience, 5)
        self.assertEqual(config.training.early_stopping_threshold, 0.0)
        self.assertEqual(config.training.lr_scheduler_type, "cosine")

    def test_training_args_config_parses_metrics_subsection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            segments_path = tmp_path / "segments.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "training.json"
            write_csv(segments_path, ["segment_id", "zh-CN", "ko"], [{"segment_id": "1", "zh-CN": "x", "ko": "y"}])
            write_csv(glossary_path, ["term_id", "zh-CN", "ko"], [])
            config_data = build_training_config(segments_path, glossary_path)
            config_data["metrics"] = {
                "enabled": True,
                "composite_weight_bleu": 0.6,
                "composite_weight_preservation_nospace": 0.4,
                "predict_with_generate": True,
                "generation_max_length": 200,
                "generation_num_beams": 2,
            }
            config_path.write_text(json.dumps(config_data, ensure_ascii=False), encoding="utf-8")
            config = load_training_config(config_path)

        self.assertIsNotNone(config.metrics)
        self.assertTrue(config.metrics.enabled)
        self.assertAlmostEqual(config.metrics.composite_weight_bleu, 0.6)
        self.assertAlmostEqual(config.metrics.composite_weight_preservation_nospace, 0.4)
        self.assertTrue(config.metrics.predict_with_generate)
        self.assertEqual(config.metrics.generation_max_length, 200)
        self.assertEqual(config.metrics.generation_num_beams, 2)

    def test_training_config_without_metrics_section_has_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            segments_path = tmp_path / "segments.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "training.json"
            write_csv(segments_path, ["segment_id", "zh-CN", "ko"], [{"segment_id": "1", "zh-CN": "x", "ko": "y"}])
            write_csv(glossary_path, ["term_id", "zh-CN", "ko"], [])
            config_path.write_text(
                json.dumps(build_training_config(segments_path, glossary_path), ensure_ascii=False),
                encoding="utf-8",
            )
            config = load_training_config(config_path)

        self.assertIsNone(config.metrics)


class Seq2SeqTrainerWiringTest(unittest.TestCase):
    def _make_tiny_model_and_tokenizer(self):
        from transformers import M2M100Config, M2M100ForConditionalGeneration

        class TinyTokenizer:
            vocab_size = 64
            pad_token_id = 1
            bos_token_id = 0
            eos_token_id = 2

            def __len__(self):
                return self.vocab_size

            def batch_decode(self, token_ids, skip_special_tokens=True):
                return ["" for _ in token_ids]

        tokenizer = TinyTokenizer()
        model_config = M2M100Config(
            vocab_size=tokenizer.vocab_size,
            decoder_start_token_id=3,
            bos_token_id=0,
            eos_token_id=2,
            pad_token_id=1,
            d_model=16,
            encoder_layers=1,
            decoder_layers=1,
            encoder_attention_heads=1,
            decoder_attention_heads=1,
            encoder_ffn_dim=32,
            decoder_ffn_dim=32,
            max_position_embeddings=32,
        )
        model = M2M100ForConditionalGeneration(model_config)
        return model, tokenizer

    def _make_tiny_dataset(self):
        examples = [
            TokenizedTrainingExample(
                segment_id="1",
                input_ids=[0, 1, 2],
                attention_mask=[1, 1, 1],
                labels=[3, 1, 2],
            )
        ]
        return TorchTrainingDataset(examples)

    def _make_metrics_config_obj(self):
        from longtu_translation_pipeline.config import MetricsConfig

        return MetricsConfig(
            enabled=True,
            composite_weight_bleu=0.5,
            composite_weight_preservation_nospace=0.5,
            predict_with_generate=True,
            generation_max_length=32,
            generation_num_beams=1,
        )

    def _make_training_config_with_early_stop(self, tmp_path: Path):
        segments_path = tmp_path / "segments.csv"
        glossary_path = tmp_path / "glossary.csv"
        config_path = tmp_path / "training.json"
        write_csv(
            segments_path,
            ["segment_id", "zh-CN", "ko"],
            [{"segment_id": "1", "zh-CN": "打开神秘宝箱", "ko": "신비한 보물상자 열기"}],
        )
        write_csv(glossary_path, ["term_id", "zh-CN", "ko"], [])
        config_data = build_training_config(segments_path, glossary_path)
        config_data["training"]["load_best_model_at_end"] = True
        config_data["training"]["metric_for_best_model"] = "eval_composite"
        config_data["training"]["greater_is_better"] = True
        config_data["training"]["early_stopping_patience"] = 3
        config_data["training"]["early_stopping_threshold"] = 0.0
        config_data["metrics"] = {
            "enabled": True,
            "composite_weight_bleu": 0.5,
            "composite_weight_preservation_nospace": 0.5,
            "predict_with_generate": True,
            "generation_max_length": 32,
            "generation_num_beams": 1,
        }
        config_path.write_text(json.dumps(config_data, ensure_ascii=False), encoding="utf-8")
        return load_training_config(config_path)

    def test_seq2seq_trainer_attaches_early_stopping_callback_when_configured(self) -> None:
        from transformers import EarlyStoppingCallback

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            model, tokenizer = self._make_tiny_model_and_tokenizer()
            dataset = self._make_tiny_dataset()
            config = self._make_training_config_with_early_stop(tmp_path)
            output_dir = tmp_path / "out"
            output_dir.mkdir()

            trainer = _build_seq2seq_trainer(
                model=model,
                tokenizer=tokenizer,
                train_dataset=dataset,
                eval_dataset=dataset,
                output_dir=output_dir,
                config=config,
                metrics_config=config.metrics,
                validation_examples=[TrainingExample("1", "打开神秘宝箱", "신비한 보물상자 열기")],
                resolved_max_steps=None,
                resolved_save_steps=10,
                resolved_eval_steps=10,
                resolved_save_total_limit=1,
                resolved_logging_steps=1,
                resolved_gradient_accumulation_steps=1,
                resolved_learning_rate=2e-5,
                resolved_warmup_ratio=0.0,
                resolved_weight_decay=0.0,
                resolved_max_grad_norm=None,
                use_cpu=True,
                fp16=False,
                bf16=False,
            )

        callback_types = [type(cb) for cb in trainer.callback_handler.callbacks]
        self.assertIn(EarlyStoppingCallback, callback_types)

    def test_seq2seq_trainer_load_best_model_plumbed_through(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            model, tokenizer = self._make_tiny_model_and_tokenizer()
            dataset = self._make_tiny_dataset()
            config = self._make_training_config_with_early_stop(tmp_path)
            output_dir = tmp_path / "out"
            output_dir.mkdir()

            trainer = _build_seq2seq_trainer(
                model=model,
                tokenizer=tokenizer,
                train_dataset=dataset,
                eval_dataset=dataset,
                output_dir=output_dir,
                config=config,
                metrics_config=config.metrics,
                validation_examples=[TrainingExample("1", "打开神秘宝箱", "신비한 보물상자 열기")],
                resolved_max_steps=None,
                resolved_save_steps=10,
                resolved_eval_steps=10,
                resolved_save_total_limit=1,
                resolved_logging_steps=1,
                resolved_gradient_accumulation_steps=1,
                resolved_learning_rate=2e-5,
                resolved_warmup_ratio=0.0,
                resolved_weight_decay=0.0,
                resolved_max_grad_norm=None,
                use_cpu=True,
                fp16=False,
                bf16=False,
            )

        self.assertTrue(trainer.args.load_best_model_at_end)

    def test_formal_training_falls_back_to_trainer_when_metrics_disabled(self) -> None:
        from transformers import Trainer, Seq2SeqTrainer

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            model, tokenizer = self._make_tiny_model_and_tokenizer()
            dataset = self._make_tiny_dataset()
            output_dir = tmp_path / "out"
            output_dir.mkdir()

            trainer = build_trainer(
                model=model,
                dataset=dataset,
                output_dir=output_dir,
                max_steps=1,
                use_cpu=True,
                fp16=False,
            )

        self.assertIsInstance(trainer, Trainer)
        self.assertNotIsInstance(trainer, Seq2SeqTrainer)


class ComputeMetricsTest(unittest.TestCase):
    def _make_tokenizer(self, decode_map: dict[int, str]):
        class FixedTokenizer:
            pad_token_id = 0

            def __len__(self):
                return 10

            def batch_decode(self, token_ids_list, skip_special_tokens=True):
                results = []
                for token_ids in token_ids_list:
                    results.append(decode_map.get(tuple(token_ids), ""))
                return results

        return FixedTokenizer()

    def test_compute_metrics_returns_composite_dict(self) -> None:
        import numpy as np
        from longtu_translation_pipeline.evaluation import GlossaryTerm

        # predictions: token IDs for "안녕하세요" (decoded via map)
        # labels: same (perfect match → BLEU near 1.0)
        decode_map = {
            (10, 11, 12): "안녕하세요",
            (10, 11, 12, 0): "안녕하세요",
        }
        tokenizer = self._make_tokenizer(decode_map)
        glossary_terms = [GlossaryTerm(source="안녕", target="hello")]
        predictions = np.array([[10, 11, 12]])
        label_ids = np.array([[10, 11, 12]])

        compute_metrics = make_compute_metrics(
            tokenizer=tokenizer,
            glossary_terms=glossary_terms,
            weight_bleu=0.5,
            weight_preservation_nospace=0.5,
            validation_sources=["source text"],
        )
        result = compute_metrics((predictions, label_ids))

        self.assertIn("bleu", result)
        self.assertIn("glossary_preservation_exact", result)
        self.assertIn("glossary_preservation_nospace", result)
        self.assertIn("composite", result)
        # composite = 0.5 * bleu + 0.5 * preservation_nospace
        expected_composite = 0.5 * result["bleu"] + 0.5 * result["glossary_preservation_nospace"]
        self.assertAlmostEqual(result["composite"], expected_composite, places=6)

    def test_compute_metrics_handles_minus_100_labels(self) -> None:
        import numpy as np

        # Tokenizer always returns "안녕" regardless of tokens — simulates skip_special_tokens behavior
        class AlwaysDecodeTokenizer:
            pad_token_id = 0

            def __len__(self):
                return 10

            def batch_decode(self, token_ids_list, skip_special_tokens=True):
                return ["안녕" for _ in token_ids_list]

        tokenizer = AlwaysDecodeTokenizer()
        predictions = np.array([[5, 6]])
        # Labels with -100 padding that gets replaced by pad_token_id=0 before decode
        label_ids = np.array([[5, 6, -100, -100]])

        compute_metrics = make_compute_metrics(
            tokenizer=tokenizer,
            glossary_terms=[],
            weight_bleu=1.0,
            weight_preservation_nospace=0.0,
            validation_sources=["source"],
        )
        # Should not raise; -100 is replaced with pad_token_id before decoding
        result = compute_metrics((predictions, label_ids))
        self.assertIn("bleu", result)


if __name__ == "__main__":
    unittest.main()
