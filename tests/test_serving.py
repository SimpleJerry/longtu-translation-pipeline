from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.config import load_serving_config  # noqa: E402
from longtu_translation_pipeline.inference import LoadedTranslator  # noqa: E402
from longtu_translation_pipeline.serving import (  # noqa: E402
    _read_provenance,
    create_app,
)
from longtu_translation_pipeline.text_protection import GlossaryTerm  # noqa: E402


def write_serving_config(
    path: Path,
    *,
    markers: bool = True,
    max_items: int = 32,
    max_concurrency: int = 1,
    max_length: int = 400,
    request_timeout_s: float | None = None,
) -> None:
    serving_block: dict = {
        "host": "127.0.0.1",
        "port": 8000,
        "max_items_per_request": max_items,
        "max_concurrency": max_concurrency,
    }
    if request_timeout_s is not None:
        serving_block["request_timeout_s"] = request_timeout_s
    path.write_text(
        json.dumps(
            {
                "model": {
                    "path": "fine-tuned-models/test",
                    "tokenizer_name": "facebook/nllb-200-distilled-600M",
                },
                "language": {"source_code": "zho_Hans", "target_code": "kor_Hang"},
                "glossary": {"path": "data/glossary.csv", "source_terminology_markers": markers},
                "output": {"strip_glossary_markers": True},
                "generation": {
                    "batch_size": 8,
                    "max_length": max_length,
                    "num_beams": 4,
                    "length_penalty": 1.0,
                    "no_repeat_ngram_size": 0,
                },
                "serving": serving_block,
            }
        ),
        encoding="utf-8",
    )


def make_mock_translator(inference_config, *, decoded, token_count=3):
    mock_tensor = MagicMock()
    mock_tensor.to.return_value = mock_tensor
    mock_tokenizer = MagicMock()
    mock_tokenizer.return_value = {"input_ids": mock_tensor, "attention_mask": mock_tensor}
    mock_tokenizer.batch_decode.return_value = decoded
    mock_tokenizer.encode.return_value = list(range(token_count))

    mock_param = MagicMock()
    mock_param.device = "cpu"
    mock_model = MagicMock()
    mock_model.parameters.side_effect = lambda: iter([mock_param])
    mock_model.generate.return_value = MagicMock()

    translator = LoadedTranslator(
        config=inference_config,
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
    return translator, mock_tokenizer, mock_model


class ServingContractTest(unittest.TestCase):
    def _client(
        self,
        *,
        markers=True,
        max_items=32,
        max_concurrency=1,
        max_length=400,
        decoded=("보스 도전",),
        token_count=3,
        terms=(GlossaryTerm(zh_cn="BOSS", ko="보스"),),
        provenance=None,
        request_timeout_s: float | None = None,
    ):
        from fastapi.testclient import TestClient

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config_path = Path(tmp.name) / "serving.json"
        write_serving_config(
            config_path,
            markers=markers,
            max_items=max_items,
            max_concurrency=max_concurrency,
            max_length=max_length,
            request_timeout_s=request_timeout_s,
        )
        config = load_serving_config(config_path)
        translator, mock_tokenizer, mock_model = make_mock_translator(
            config.inference, decoded=list(decoded), token_count=token_count
        )
        app = create_app(config, translator, terms=list(terms), provenance=provenance)
        return TestClient(app), mock_tokenizer, mock_model

    def test_health_does_not_invoke_model(self) -> None:
        client, _, mock_model = self._client()

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        mock_model.generate.assert_not_called()

    def test_info_reports_decoding_and_provenance(self) -> None:
        client, _, _ = self._client(provenance={"corpus_sha256": "ABC123", "seed": 42})

        body = client.get("/info").json()["model"]

        # checkpoint is the resolved model path (matches manifest checkpoint_path convention)
        self.assertEqual(Path(body["checkpoint"]).parts[-2:], ("fine-tuned-models", "test"))
        self.assertEqual(body["language_pair"], "zho_Hans->kor_Hang")
        self.assertEqual(body["decoding"]["num_beams"], 4)
        self.assertEqual(body["decoding"]["max_length"], 400)
        self.assertTrue(body["source_terminology_markers"])
        self.assertTrue(body["strip_glossary_markers"])
        self.assertEqual(body["corpus_sha256"], "ABC123")
        self.assertEqual(body["seed"], 42)

    def test_translate_applies_source_markers_and_returns_schema(self) -> None:
        client, mock_tokenizer, _ = self._client(decoded=("보스 도전",))

        response = client.post("/translate", json={"items": [{"id": "seg-1", "text": "挑战BOSS"}]})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["results"], [{"id": "seg-1", "source": "挑战BOSS", "translation": "보스 도전"}])
        self.assertEqual(body["model"]["language_pair"], "zho_Hans->kor_Hang")
        # source-side markers applied before tokenization (ADR-0028)
        self.assertEqual(mock_tokenizer.call_args.args[0], ["挑战<start>BOSS<end>"])

    def test_translate_without_markers_passes_raw_source(self) -> None:
        client, mock_tokenizer, _ = self._client(markers=False, decoded=("보스 도전",))

        response = client.post("/translate", json={"items": [{"text": "挑战BOSS"}]})

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["results"][0]["id"])
        self.assertEqual(mock_tokenizer.call_args.args[0], ["挑战BOSS"])

    def test_translate_rejects_empty_items(self) -> None:
        client, _, mock_model = self._client()

        response = client.post("/translate", json={"items": []})

        self.assertEqual(response.status_code, 422)
        mock_model.generate.assert_not_called()

    def test_translate_rejects_blank_text(self) -> None:
        client, _, mock_model = self._client()

        response = client.post("/translate", json={"items": [{"text": "   "}]})

        self.assertEqual(response.status_code, 422)
        mock_model.generate.assert_not_called()

    def test_translate_rejects_too_many_items(self) -> None:
        client, _, _ = self._client(max_items=1)

        response = client.post(
            "/translate",
            json={"items": [{"text": "挑战BOSS"}, {"text": "领取奖励"}]},
        )

        self.assertEqual(response.status_code, 422)

    def test_translate_rejects_text_over_max_length(self) -> None:
        client, _, mock_model = self._client(max_length=5, token_count=10)

        response = client.post("/translate", json={"items": [{"text": "挑战BOSS"}]})

        self.assertEqual(response.status_code, 422)
        mock_model.generate.assert_not_called()

    def test_translate_internal_error_returns_safe_500(self) -> None:
        client, _, mock_model = self._client()
        mock_model.generate.side_effect = RuntimeError("gpu exploded")

        response = client.post("/translate", json={"items": [{"text": "挑战BOSS"}]})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "internal translation error"})

    def test_translate_tokenization_error_returns_422(self) -> None:
        client, mock_tokenizer, mock_model = self._client()
        mock_tokenizer.encode.side_effect = ValueError("bad encoding")

        response = client.post("/translate", json={"items": [{"text": "挑战BOSS"}]})

        self.assertEqual(response.status_code, 422)
        self.assertIn("cannot be tokenized", response.json()["detail"])
        mock_model.generate.assert_not_called()

    def test_request_timeout_s_parsed_into_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "serving.json"
            write_serving_config(config_path, request_timeout_s=30.0)
            config = load_serving_config(config_path)
            self.assertEqual(config.runtime.request_timeout_s, 30.0)

    def test_request_timeout_s_defaults_when_absent(self) -> None:
        client, _, _ = self._client()
        from longtu_translation_pipeline.config import load_serving_config as lsc
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "serving.json"
            write_serving_config(config_path)
            config = lsc(config_path)
            self.assertEqual(config.runtime.request_timeout_s, 60.0)

    def test_translate_times_out_returns_504(self) -> None:
        client, _, mock_model = self._client(request_timeout_s=0.01)

        def slow_generate(*args, **kwargs):
            time.sleep(0.5)
            return MagicMock()

        mock_model.generate.side_effect = slow_generate

        response = client.post("/translate", json={"items": [{"text": "挑战BOSS"}]})

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json(), {"detail": "translation timed out"})


class ProvenanceLocalTest(unittest.TestCase):
    def test_local_manifest_next_to_checkpoint_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ckpt_dir = Path(tmp) / "checkpoint-48000"
            ckpt_dir.mkdir()
            manifest = Path(tmp) / "run_manifest.json"
            manifest.write_text(
                json.dumps({"data": {"segments_sha256": "ABCD1234", "split_seed": 42}}),
                encoding="utf-8",
            )
            result = _read_provenance(ckpt_dir)

        self.assertIsNotNone(result)
        self.assertEqual(result["corpus_sha256"], "ABCD1234")
        self.assertEqual(result["seed"], 42)

    def test_local_missing_manifest_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = _read_provenance(Path(tmp) / "checkpoint-48000")

        self.assertIsNone(result)


class ProvenanceHFTest(unittest.TestCase):
    def _make_manifest(self, tmp_dir: str) -> str:
        p = Path(tmp_dir) / "run_manifest.json"
        p.write_text(
            json.dumps({"data": {"segments_sha256": "HF_SHA256", "split_seed": 99}}),
            encoding="utf-8",
        )
        return str(p)

    def test_hf_branch_parses_manifest_from_hub(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = self._make_manifest(tmp)
            with patch(
                "longtu_translation_pipeline.serving._hf_download_manifest",
                return_value=local_path,
            ) as mock_dl:
                result = _read_provenance(
                    "SimpleJerry/longtu-nllb-zh2ko",
                    from_hub=True,
                    revision="earlystop-v1-ckpt48000",
                )
                mock_dl.assert_called_once_with(
                    "SimpleJerry/longtu-nllb-zh2ko",
                    "earlystop-v1-ckpt48000",
                )

        self.assertIsNotNone(result)
        self.assertEqual(result["corpus_sha256"], "HF_SHA256")
        self.assertEqual(result["seed"], 99)

    def test_hf_branch_download_error_returns_none(self) -> None:
        with patch(
            "longtu_translation_pipeline.serving._hf_download_manifest",
            side_effect=OSError("network error"),
        ):
            result = _read_provenance(
                "SimpleJerry/longtu-nllb-zh2ko",
                from_hub=True,
                revision="earlystop-v1-ckpt48000",
            )

        self.assertIsNone(result)

    def test_hf_branch_malformed_manifest_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "run_manifest.json"
            p.write_text("not json", encoding="utf-8")
            with patch(
                "longtu_translation_pipeline.serving._hf_download_manifest",
                return_value=str(p),
            ):
                result = _read_provenance(
                    "SimpleJerry/longtu-nllb-zh2ko",
                    from_hub=True,
                    revision="earlystop-v1-ckpt48000",
                )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
