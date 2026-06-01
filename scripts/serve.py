from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from longtu_translation_pipeline.config import load_serving_config  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synchronous translation serving entry point (ADR-0034).")
    parser.add_argument("--config", default=str(ROOT / "configs" / "serving" / "default.json"))
    parser.add_argument("--host", default=None, help="Override serving.host.")
    parser.add_argument("--port", type=int, default=None, help="Override serving.port.")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the serving config and exit without loading the model.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    serving_config = load_serving_config(args.config, base_dir=ROOT)
    runtime = serving_config.runtime
    inference = serving_config.inference
    host = args.host or runtime.host
    port = args.port or runtime.port

    if args.dry_run:
        print(
            "Serving config OK\n"
            f"model={inference.model.path}\n"
            f"tokenizer={inference.model.tokenizer_name}\n"
            f"language_pair={inference.language.source_code}->{inference.language.target_code}\n"
            f"host={host} port={port}\n"
            f"max_items_per_request={runtime.max_items_per_request} "
            f"max_concurrency={runtime.max_concurrency}\n"
            f"source_terminology_markers={inference.glossary.source_terminology_markers} "
            f"strip_glossary_markers={inference.output.strip_glossary_markers}"
        )
        return 0

    import uvicorn

    from longtu_translation_pipeline.serving import build_runtime_app

    app = build_runtime_app(serving_config, device=args.device)
    uvicorn.run(app, host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
