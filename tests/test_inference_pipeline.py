from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from longtu_translation_pipeline.config import load_inference_config
from longtu_translation_pipeline.inference import (
    GeneratedTranslationRow,
    InferenceGenerationResult,
    LoadedTranslator,
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
    InferenceRecord,
    PreparedInferenceRecord,
    prepare_inference_records,
    resolve_latest_run_checkpoint,
    resolve_manifest_path,
    require_manifest_string,
    run_generation_batches,
    translate_texts,
    ValidationGenerationResult,
    write_generation_csv,
    write_validation_generation_manifest,
)
from longtu_translation_pipeline.text_protection import GlossaryTerm  # noqa: E402


class InferencePipelineTest(unittest.TestCase):
    def test_dry_run_reads_inputs_and_plans_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "segments.csv"
            output_path = tmp_path / "translation_result.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "inference.json"

            with input_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["segment_id", "zh-CN", "ko"])
                writer.writeheader()
                writer.writerow({"segment_id": "1", "zh-CN": "勇士竞技", "ko": "용맹의 결투장"})
                writer.writerow({"segment_id": "2", "zh-CN": "挑战次数:{0}", "ko": "도전 횟수: {0}"})
            write_csv(
                glossary_path,
                ["term_id", "zh-CN", "ko"],
                [{"term_id": "1", "zh-CN": "勇士竞技", "ko": "용맹의 결투장"}],
            )

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
                        "glossary": {
                            "path": str(glossary_path),
                            "source_terminology_markers": True,
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
        self.assertTrue(plan.source_terminology_markers)
        self.assertEqual(plan.marked_source_rows, 1)
        self.assertEqual(plan.source_terms_marked, 1)
        self.assertEqual(plan.preview_records[0].record_id, "1")
        self.assertEqual(plan.preview_records[0].text, "勇士竞技")
        self.assertEqual(plan.preview_records[0].reference, "용맹의 결투장")

    def test_empty_inference_csv_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "segments.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "inference.json"

            with input_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["segment_id", "zh-CN", "ko"])
                writer.writeheader()
            write_csv(glossary_path, ["term_id", "zh-CN", "ko"], [])

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
                        "glossary": {
                            "path": str(glossary_path),
                            "source_terminology_markers": True,
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

    def test_prepare_records_marks_source_but_keeps_raw_output_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "segments.csv"
            output_path = tmp_path / "generated.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "inference.json"
            write_csv(input_path, ["segment_id", "zh-CN", "ko"], [])
            write_csv(
                glossary_path,
                ["term_id", "zh-CN", "ko"],
                [{"term_id": "1", "zh-CN": "BOSS", "ko": "보스"}],
            )
            write_inference_config(config_path, input_path, output_path, glossary_path, True)

            config = load_inference_config(config_path)
            prepared = prepare_inference_records(
                config,
                [InferenceRecord(record_id="1", text="挑战BOSS", reference="보스 도전")],
            )
            write_generation_csv(
                output_path,
                [
                    GeneratedTranslationRow(
                        record_id=prepared[0].record.record_id,
                        source=prepared[0].record.text,
                        reference=prepared[0].record.reference,
                        candidate="보스 도전",
                    )
                ],
            )
            rows = read_csv(output_path)

        self.assertEqual(prepared[0].generation_text, "挑战<start>BOSS<end>")
        self.assertEqual(prepared[0].source_terms_marked, 1)
        self.assertEqual(rows[0]["source"], "挑战BOSS")

    def test_prepare_records_can_disable_source_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "segments.csv"
            output_path = tmp_path / "generated.csv"
            glossary_path = tmp_path / "glossary.csv"
            config_path = tmp_path / "inference.json"
            write_csv(input_path, ["segment_id", "zh-CN", "ko"], [])
            write_csv(
                glossary_path,
                ["term_id", "zh-CN", "ko"],
                [{"term_id": "1", "zh-CN": "BOSS", "ko": "보스"}],
            )
            write_inference_config(config_path, input_path, output_path, glossary_path, False)

            prepared = prepare_inference_records(
                load_inference_config(config_path),
                [InferenceRecord(record_id="1", text="挑战BOSS", reference="보스 도전")],
            )

        self.assertEqual(prepared[0].generation_text, "挑战BOSS")
        self.assertEqual(prepared[0].source_terms_marked, 0)

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
            source_terminology_markers=True,
            marked_source_rows=1,
            source_terms_marked=1,
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
        self.assertIn("source_terminology_markers=True", formatted)
        self.assertIn("marked_source_rows=1", formatted)
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


    def test_decode_params_default_to_greedy_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "s.csv"
            output_path = tmp_path / "out.csv"
            glossary_path = tmp_path / "g.csv"
            config_path = tmp_path / "inference.json"
            write_csv(input_path, ["segment_id", "zh-CN", "ko"], [])
            write_csv(glossary_path, ["term_id", "zh-CN", "ko"], [])
            config_path.write_text(
                json.dumps({
                    "input": {"path": str(input_path), "text_column": "zh-CN", "reference_column": "ko", "id_column": "segment_id"},
                    "language": {"source_code": "zho_Hans", "target_code": "kor_Hang"},
                    "model": {"path": "fine-tuned-models/test", "tokenizer_name": "facebook/nllb-200-distilled-600M"},
                    "glossary": {"path": str(glossary_path), "source_terminology_markers": False},
                    "output": {"path": str(output_path), "strip_glossary_markers": True},
                    "generation": {"batch_size": 4, "max_length": 64},
                    "dry_run": {"preview_rows": 1},
                }),
                encoding="utf-8",
            )
            config = load_inference_config(config_path)

        self.assertEqual(config.generation.num_beams, 1)
        self.assertEqual(config.generation.length_penalty, 1.0)
        self.assertEqual(config.generation.no_repeat_ngram_size, 0)

    def test_decode_params_loaded_from_generation_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "s.csv"
            output_path = tmp_path / "out.csv"
            glossary_path = tmp_path / "g.csv"
            config_path = tmp_path / "inference.json"
            write_csv(input_path, ["segment_id", "zh-CN", "ko"], [])
            write_csv(glossary_path, ["term_id", "zh-CN", "ko"], [])
            config_path.write_text(
                json.dumps({
                    "input": {"path": str(input_path), "text_column": "zh-CN", "reference_column": "ko", "id_column": "segment_id"},
                    "language": {"source_code": "zho_Hans", "target_code": "kor_Hang"},
                    "model": {"path": "fine-tuned-models/test", "tokenizer_name": "facebook/nllb-200-distilled-600M"},
                    "glossary": {"path": str(glossary_path), "source_terminology_markers": False},
                    "output": {"path": str(output_path), "strip_glossary_markers": True},
                    "generation": {"batch_size": 4, "max_length": 64, "num_beams": 5, "length_penalty": 1.2, "no_repeat_ngram_size": 3},
                    "dry_run": {"preview_rows": 1},
                }),
                encoding="utf-8",
            )
            config = load_inference_config(config_path)

        self.assertEqual(config.generation.num_beams, 5)
        self.assertAlmostEqual(config.generation.length_penalty, 1.2)
        self.assertEqual(config.generation.no_repeat_ngram_size, 3)

    def test_decode_params_passed_to_model_generate(self) -> None:
        from unittest.mock import MagicMock

        mock_tensor = MagicMock()
        mock_tensor.to.return_value = mock_tensor
        encoded = {"input_ids": mock_tensor, "attention_mask": mock_tensor}

        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = encoded
        mock_tokenizer.batch_decode.return_value = ["번역 결과"]

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])
        mock_model.generate.return_value = MagicMock()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "s.csv"
            output_path = tmp_path / "out.csv"
            glossary_path = tmp_path / "g.csv"
            config_path = tmp_path / "inference.json"
            write_csv(input_path, ["segment_id", "zh-CN", "ko"], [])
            write_csv(glossary_path, ["term_id", "zh-CN", "ko"], [])
            config_path.write_text(
                json.dumps({
                    "input": {"path": str(input_path), "text_column": "zh-CN", "reference_column": "ko", "id_column": "segment_id"},
                    "language": {"source_code": "zho_Hans", "target_code": "kor_Hang"},
                    "model": {"path": "fine-tuned-models/test", "tokenizer_name": "facebook/nllb-200-distilled-600M"},
                    "glossary": {"path": str(glossary_path), "source_terminology_markers": False},
                    "output": {"path": str(output_path), "strip_glossary_markers": True},
                    "generation": {"batch_size": 4, "max_length": 64, "num_beams": 4, "length_penalty": 1.1, "no_repeat_ngram_size": 3},
                    "dry_run": {"preview_rows": 1},
                }),
                encoding="utf-8",
            )
            config = load_inference_config(config_path)

        records = [PreparedInferenceRecord(
            record=InferenceRecord(record_id="1", text="挑战BOSS", reference="보스 도전"),
            generation_text="挑战BOSS",
            source_terms_marked=0,
        )]
        run_generation_batches(config, mock_tokenizer, mock_model, records, 256098)

        mock_model.generate.assert_called_once()
        _, kwargs = mock_model.generate.call_args
        self.assertEqual(kwargs["num_beams"], 4)
        self.assertAlmostEqual(kwargs["length_penalty"], 1.1)
        self.assertEqual(kwargs["no_repeat_ngram_size"], 3)
        self.assertEqual(kwargs["forced_bos_token_id"], 256098)

    def test_translate_texts_marks_source_and_returns_candidates(self) -> None:
        from unittest.mock import MagicMock

        mock_tensor = MagicMock()
        mock_tensor.to.return_value = mock_tensor
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {"input_ids": mock_tensor, "attention_mask": mock_tensor}
        mock_tokenizer.batch_decode.return_value = ["보스 도전"]

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])
        mock_model.generate.return_value = MagicMock()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "s.csv"
            output_path = tmp_path / "out.csv"
            glossary_path = tmp_path / "g.csv"
            config_path = tmp_path / "inference.json"
            write_csv(input_path, ["segment_id", "zh-CN", "ko"], [])
            write_csv(glossary_path, ["term_id", "zh-CN", "ko"], [])
            write_inference_config(config_path, input_path, output_path, glossary_path, True)
            config = load_inference_config(config_path)

        translator = LoadedTranslator(
            config=config,
            tokenizer=mock_tokenizer,
            model=mock_model,
            forced_bos_token_id=256098,
            device="cpu",
            special_tokens_added=2,
            tokenizer_vocab_size=10,
            embedding_size_before=10,
            embedding_size_after=10,
            cuda_device_name="",
            cuda_memory_summary="",
        )

        candidates = translate_texts(
            translator,
            ["挑战BOSS"],
            terms=[GlossaryTerm(zh_cn="BOSS", ko="보스")],
        )

        self.assertEqual(candidates, ["보스 도전"])
        # source-side markers applied before tokenization (ADR-0028)
        marked_texts = mock_tokenizer.call_args.args[0]
        self.assertEqual(marked_texts, ["挑战<start>BOSS<end>"])
        # decoding params + forced bos come from config (ADR-0006 / model-card)
        _, kwargs = mock_model.generate.call_args
        self.assertEqual(kwargs["forced_bos_token_id"], 256098)
        self.assertEqual(kwargs["num_beams"], config.generation.num_beams)

    def test_translate_texts_without_markers_passes_raw_source(self) -> None:
        from unittest.mock import MagicMock

        mock_tensor = MagicMock()
        mock_tensor.to.return_value = mock_tensor
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {"input_ids": mock_tensor, "attention_mask": mock_tensor}
        mock_tokenizer.batch_decode.return_value = ["보스 도전"]

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])
        mock_model.generate.return_value = MagicMock()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "s.csv"
            output_path = tmp_path / "out.csv"
            glossary_path = tmp_path / "g.csv"
            config_path = tmp_path / "inference.json"
            write_csv(input_path, ["segment_id", "zh-CN", "ko"], [])
            write_csv(glossary_path, ["term_id", "zh-CN", "ko"], [])
            write_inference_config(config_path, input_path, output_path, glossary_path, False)
            config = load_inference_config(config_path)

        translator = LoadedTranslator(
            config=config,
            tokenizer=mock_tokenizer,
            model=mock_model,
            forced_bos_token_id=256098,
            device="cpu",
            special_tokens_added=2,
            tokenizer_vocab_size=10,
            embedding_size_before=10,
            embedding_size_after=10,
            cuda_device_name="",
            cuda_memory_summary="",
        )

        candidates = translate_texts(
            translator,
            ["挑战BOSS"],
            terms=[GlossaryTerm(zh_cn="BOSS", ko="보스")],
        )

        self.assertEqual(candidates, ["보스 도전"])
        marked_texts = mock_tokenizer.call_args.args[0]
        self.assertEqual(marked_texts, ["挑战BOSS"])  # markers disabled -> raw source

    def test_run_generation_batches_pairs_records_with_candidates(self) -> None:
        from unittest.mock import MagicMock

        mock_tensor = MagicMock()
        mock_tensor.to.return_value = mock_tensor
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {"input_ids": mock_tensor, "attention_mask": mock_tensor}
        mock_tokenizer.batch_decode.return_value = ["보스 도전"]

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])
        mock_model.generate.return_value = MagicMock()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "s.csv"
            output_path = tmp_path / "out.csv"
            glossary_path = tmp_path / "g.csv"
            config_path = tmp_path / "inference.json"
            write_csv(input_path, ["segment_id", "zh-CN", "ko"], [])
            write_csv(glossary_path, ["term_id", "zh-CN", "ko"], [])
            write_inference_config(config_path, input_path, output_path, glossary_path, False)
            config = load_inference_config(config_path)

        records = [
            PreparedInferenceRecord(
                record=InferenceRecord(record_id="1", text="挑战BOSS", reference="보스 도전"),
                generation_text="挑战BOSS",
                source_terms_marked=0,
            )
        ]
        rows = run_generation_batches(config, mock_tokenizer, mock_model, records, 256098)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].record_id, "1")
        self.assertEqual(rows[0].source, "挑战BOSS")
        self.assertEqual(rows[0].reference, "보스 도전")
        self.assertEqual(rows[0].candidate, "보스 도전")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_inference_config(
    path: Path,
    input_path: Path,
    output_path: Path,
    glossary_path: Path,
    source_terminology_markers: bool,
) -> None:
    path.write_text(
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
                "glossary": {
                    "path": str(glossary_path),
                    "source_terminology_markers": source_terminology_markers,
                },
                "output": {"path": str(output_path), "strip_glossary_markers": True},
                "generation": {"batch_size": 4, "max_length": 64},
                "dry_run": {"preview_rows": 1},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


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
        source_terminology_markers=True,
        marked_source_rows=1,
        source_terms_marked=1,
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
