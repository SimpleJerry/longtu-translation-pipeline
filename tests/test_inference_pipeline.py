from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.config import load_inference_config  # noqa: E402
from longtu_translation_pipeline.inference import (  # noqa: E402
    GeneratedTranslationRow,
    InferenceGenerationResult,
    TestGenerationResult,
    build_inference_dry_run,
    default_test_output_path,
    default_validation_output_path,
    format_inference_generation,
    format_test_generation,
    format_validation_generation,
    read_run_manifest,
    read_test_records,
    read_validation_records,
    resolve_latest_run_checkpoint,
    resolve_manifest_path,
    require_manifest_string,
    ValidationGenerationResult,
    write_generation_csv,
    write_validation_generation_manifest,
)


class InferencePipelineTest(unittest.TestCase):
    def test_dry_run_reads_inputs_and_plans_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "segments.csv"
            output_path = tmp_path / "translation_result.csv"
            config_path = tmp_path / "inference.json"

            with input_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["segment_id", "zh-CN", "ko"])
                writer.writeheader()
                writer.writerow({"segment_id": "1", "zh-CN": "勇士竞技", "ko": "용맹의 결투장"})
                writer.writerow({"segment_id": "2", "zh-CN": "挑战次数:{0}", "ko": "도전 횟수: {0}"})

            config_path.write_text(
                json.dumps(
                    {
                        "input": {
                        "path": str(input_path),
                        "text_column": "zh-CN",
                        "reference_column": "ko",
                        "id_column": "segment_id",
                    },
                    "language": {"source_code": "zho_Hans", "target_code": "kor_Hang"},
                    "model": {
                        "path": "fine-tuned-models/test",
                        "tokenizer_name": "facebook/nllb-200-distilled-600M",
                    },
                        "output": {"path": str(output_path), "strip_glossary_markers": True},
                        "generation": {"batch_size": 4, "max_length": 64},
                        "dry_run": {"preview_rows": 1},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            plan = build_inference_dry_run(load_inference_config(config_path))

        self.assertEqual(plan.total_rows, 2)
        self.assertEqual(plan.output_path, output_path)
        self.assertEqual(plan.batch_size, 4)
        self.assertEqual(plan.preview_records[0].record_id, "1")
        self.assertEqual(plan.preview_records[0].text, "勇士竞技")
        self.assertEqual(plan.preview_records[0].reference, "용맹의 결투장")

    def test_empty_inference_csv_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "segments.csv"
            config_path = tmp_path / "inference.json"

            with input_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["segment_id", "zh-CN", "ko"])
                writer.writeheader()

            config_path.write_text(
                json.dumps(
                    {
                        "input": {
                        "path": str(input_path),
                        "text_column": "zh-CN",
                        "reference_column": "ko",
                        "id_column": "segment_id",
                    },
                    "language": {"source_code": "zho_Hans", "target_code": "kor_Hang"},
                    "model": {
                        "path": "fine-tuned-models/test",
                        "tokenizer_name": "facebook/nllb-200-distilled-600M",
                    },
                        "output": {"path": "translation_result.csv", "strip_glossary_markers": True},
                        "generation": {"batch_size": 4, "max_length": 64},
                        "dry_run": {"preview_rows": 1},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "No inference records found"):
                build_inference_dry_run(load_inference_config(config_path))

    def test_generation_csv_schema_matches_evaluation_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "generated.csv"
            write_generation_csv(
                output_path,
                [
                    GeneratedTranslationRow(
                        record_id="1",
                        source="挑战BOSS",
                        reference="보스 도전",
                        candidate="보스 도전",
                    )
                ],
            )

            with output_path.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

        self.assertEqual(reader.fieldnames, ["segment_id", "source", "references", "candidates"])
        self.assertEqual(rows[0]["segment_id"], "1")
        self.assertEqual(rows[0]["source"], "挑战BOSS")
        self.assertEqual(rows[0]["references"], "보스 도전")
        self.assertEqual(rows[0]["candidates"], "보스 도전")

    def test_generation_result_format_reports_model_and_schema(self) -> None:
        result = InferenceGenerationResult(
            config_path=Path("inference.json"),
            input_path=Path("segments.csv"),
            output_path=Path("data/review/inference/generated_samples.csv"),
            model_path=Path("fine-tuned-models/checkpoint-4"),
            tokenizer_name="facebook/nllb-200-distilled-600M",
            source_code="zho_Hans",
            target_code="kor_Hang",
            forced_bos_token_id=256098,
            special_tokens_added=2,
            tokenizer_vocab_size=256206,
            embedding_size_before=256204,
            embedding_size_after=256206,
            device="cuda",
            cuda_device_name="NVIDIA Test GPU",
            cuda_memory_summary="allocated_gb=1.00;reserved_gb=2.00",
            batch_size=8,
            max_length=400,
            strip_glossary_markers=True,
            input_rows=1,
            generated_rows=1,
            output_columns=["segment_id", "source", "references", "candidates"],
            preview_rows=[
                GeneratedTranslationRow(
                    record_id="1",
                    source="挑战BOSS",
                    reference="보스 도전",
                    candidate="보스 도전",
                )
            ],
        )

        formatted = format_inference_generation(result)

        self.assertIn("Inference generation result", formatted)
        self.assertIn("model_path=fine-tuned-models", formatted)
        self.assertIn("tokenizer_name=facebook/nllb-200-distilled-600M", formatted)
        self.assertIn("language_pair=zho_Hans->kor_Hang", formatted)
        self.assertIn("forced_bos_token_id=256098", formatted)
        self.assertIn("output_columns=segment_id,source,references,candidates", formatted)

    def test_validation_split_can_be_read_from_run_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "fine-tuned-models" / "model" / "runs" / "run-test"
            split_path = run_dir / "splits" / "validation.csv"
            split_path.parent.mkdir(parents=True)
            write_csv(
                split_path,
                ["segment_id", "zh-CN", "ko"],
                [{"segment_id": "7", "zh-CN": "挑战BOSS", "ko": "보스 도전"}],
            )
            manifest_path = run_dir / "run_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "data": {
                            "validation_split_path": str(split_path.relative_to(root))
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manifest = read_run_manifest(manifest_path)
            raw_path = require_manifest_string(manifest, ["data", "validation_split_path"], manifest_path)
            resolved = resolve_manifest_path(raw_path, run_dir=run_dir, repo_root=root)
            records = read_validation_records(resolved)

        self.assertEqual(resolved, split_path)
        self.assertEqual(records[0].record_id, "7")
        self.assertEqual(records[0].text, "挑战BOSS")
        self.assertEqual(records[0].reference, "보스 도전")

    def test_test_split_can_be_read_from_run_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "fine-tuned-models" / "model" / "runs" / "run-test"
            split_path = run_dir / "splits" / "test.csv"
            split_path.parent.mkdir(parents=True)
            write_csv(
                split_path,
                ["segment_id", "zh-CN", "ko"],
                [{"segment_id": "9", "zh-CN": "领取奖励", "ko": "보상 수령"}],
            )
            manifest_path = run_dir / "run_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {"data": {"test_split_path": str(split_path.relative_to(root))}},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manifest = read_run_manifest(manifest_path)
            raw_path = require_manifest_string(manifest, ["data", "test_split_path"], manifest_path)
            resolved = resolve_manifest_path(raw_path, run_dir=run_dir, repo_root=root)
            records = read_test_records(resolved)

        self.assertEqual(resolved, split_path)
        self.assertEqual(records[0].record_id, "9")
        self.assertEqual(records[0].text, "领取奖励")
        self.assertEqual(records[0].reference, "보상 수령")

    def test_latest_run_checkpoint_uses_numeric_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "checkpoint-2").mkdir()
            (run_dir / "checkpoint-final").mkdir()
            (run_dir / "checkpoint-10").mkdir()

            checkpoint = resolve_latest_run_checkpoint(run_dir)

        self.assertEqual(checkpoint.name, "checkpoint-10")

    def test_missing_validation_manifest_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "run_manifest.json"

            with self.assertRaisesRegex(ValueError, "Run manifest"):
                read_run_manifest(manifest_path)

    def test_default_validation_output_path_contains_run_name(self) -> None:
        root = Path("repo")
        run_dir = Path("fine-tuned-models/model/runs/run-test")

        output_path = default_validation_output_path(root, run_dir)

        self.assertEqual(
            output_path,
            Path("repo/data/review/inference/validation/run-test/validation_generated.csv"),
        )

    def test_default_test_output_path_contains_run_name(self) -> None:
        root = Path("repo")
        run_dir = Path("fine-tuned-models/model/runs/run-test")

        output_path = default_test_output_path(root, run_dir)

        self.assertEqual(
            output_path,
            Path("repo/data/review/inference/test/run-test/test_generated.csv"),
        )

    def test_validation_generation_manifest_records_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "validation_generation_manifest.json"
            generation = build_generation_result(tmp_path / "validation_generated.csv")

            write_validation_generation_manifest(
                manifest_path,
                generation,
                run_dir=tmp_path / "run-test",
                training_manifest_path=tmp_path / "run-test" / "run_manifest.json",
                validation_split_path=tmp_path / "run-test" / "splits" / "validation.csv",
            )
            data = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(data["row_count"], 1)
        self.assertEqual(Path(data["checkpoint_path"]), Path("fine-tuned-models/checkpoint-4"))
        self.assertEqual(data["output_csv"], str(generation.output_path))

    def test_validation_generation_format_reports_manifest_and_schema(self) -> None:
        result = ValidationGenerationResult(
            generation=build_generation_result(Path("data/review/inference/validation/run-test/validation_generated.csv")),
            run_dir=Path("fine-tuned-models/model/runs/run-test"),
            training_manifest_path=Path("fine-tuned-models/model/runs/run-test/run_manifest.json"),
            validation_split_path=Path("fine-tuned-models/model/runs/run-test/splits/validation.csv"),
            generation_manifest_path=Path("data/review/inference/validation/run-test/validation_generation_manifest.json"),
        )

        formatted = format_validation_generation(result)

        self.assertIn("Validation generation result", formatted)
        self.assertIn("validation_split=fine-tuned-models", formatted)
        self.assertIn("generation_manifest=data", formatted)
        self.assertIn("output_columns=segment_id,source,references,candidates", formatted)

    def test_test_generation_format_reports_manifest_and_schema(self) -> None:
        result = TestGenerationResult(
            generation=build_generation_result(Path("data/review/inference/test/run-test/test_generated.csv")),
            run_dir=Path("fine-tuned-models/model/runs/run-test"),
            training_manifest_path=Path("fine-tuned-models/model/runs/run-test/run_manifest.json"),
            test_split_path=Path("fine-tuned-models/model/runs/run-test/splits/test.csv"),
            generation_manifest_path=Path("data/review/inference/test/run-test/test_generation_manifest.json"),
        )

        formatted = format_test_generation(result)

        self.assertIn("Test generation result", formatted)
        self.assertIn("test_split=fine-tuned-models", formatted)
        self.assertIn("generation_manifest=data", formatted)
        self.assertIn("output_columns=segment_id,source,references,candidates", formatted)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_generation_result(output_path: Path) -> InferenceGenerationResult:
    return InferenceGenerationResult(
        config_path=Path("inference.json"),
        input_path=Path("splits/validation.csv"),
        output_path=output_path,
        model_path=Path("fine-tuned-models/checkpoint-4"),
        tokenizer_name="facebook/nllb-200-distilled-600M",
        source_code="zho_Hans",
        target_code="kor_Hang",
        forced_bos_token_id=256098,
        special_tokens_added=2,
        tokenizer_vocab_size=256206,
        embedding_size_before=256204,
        embedding_size_after=256206,
        device="cuda",
        cuda_device_name="NVIDIA Test GPU",
        cuda_memory_summary="allocated_gb=1.00;reserved_gb=2.00",
        batch_size=8,
        max_length=400,
        strip_glossary_markers=True,
        input_rows=1,
        generated_rows=1,
        output_columns=["segment_id", "source", "references", "candidates"],
        preview_rows=[
            GeneratedTranslationRow(
                record_id="1",
                source="挑战BOSS",
                reference="보스 도전",
                candidate="보스 도전",
            )
        ],
    )


if __name__ == "__main__":
    unittest.main()
