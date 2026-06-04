"""Regenerate docs/figures/capability_comparison.png from the single data source.

Usage:
    python scripts/plot_capability_comparison.py [--out PATH]

Data source: docs/figures/capability_comparison.data.json
Output:      docs/figures/capability_comparison.png (default)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "figures" / "capability_comparison.data.json"
DEFAULT_OUT = ROOT / "docs" / "figures" / "capability_comparison.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render capability comparison bar chart.")
    parser.add_argument(
        "--data",
        default=str(DATA_PATH),
        help="Path to capability_comparison.data.json.",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help="Output PNG path.",
    )
    return parser.parse_args()


def plot(data_path: Path, out_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    with data_path.open(encoding="utf-8") as f:
        data = json.load(f)

    metrics = data["metrics"]
    keys = list(metrics.keys())
    labels = [metrics[k]["label"] for k in keys]
    base_scores = [metrics[k]["base"] for k in keys]
    ft_scores = [metrics[k]["finetuned"] for k in keys]

    x = np.arange(len(keys))
    bar_width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    bars_base = ax.bar(x - bar_width / 2, base_scores, bar_width,
                       label="Base (NLLB-200-distilled-600M)", color="#9fc5e8", edgecolor="white")
    bars_ft = ax.bar(x + bar_width / 2, ft_scores, bar_width,
                     label="Fine-tuned (earlystop-v1-ckpt48000)", color="#3d85c8", edgecolor="white")

    for bar in bars_base:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.01, f"{h:.3f}",
                ha="center", va="bottom", fontsize=9, color="#555")
    for bar in bars_ft:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.01, f"{h:.3f}",
                ha="center", va="bottom", fontsize=9, color="#1a4f7a")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylabel("Score", fontsize=11)
    ax.set_ylim(0, 1.12)
    ax.set_title("zh-CN → ko Translation Quality\nBase vs. Fine-tuned (game localization)", fontsize=12)
    ax.legend(fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[OK] Saved: {out_path}")


def main() -> None:
    args = parse_args()
    plot(Path(args.data), Path(args.out))


if __name__ == "__main__":
    main()
