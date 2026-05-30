"""Plot training and evaluation loss from a HuggingFace trainer_state.json file."""

import argparse
import json
import sys

import pandas as pd
import matplotlib.pyplot as plt


def _load_loss_df(state_path: str) -> pd.DataFrame:
    with open(state_path, encoding="utf-8") as f:
        data = json.load(f)

    df = pd.DataFrame(data["log_history"])
    df = df.set_index("epoch").groupby(level=0).first().reset_index()
    # Drop the first checkpoint: initial loss is a high-value outlier before the
    # learning rate warms up, which compresses the rest of the curve on the y-axis.
    df = df.iloc[1:]
    return df


def _plot(df: pd.DataFrame, output: str | None) -> None:
    plt.figure(figsize=(10, 5))
    plt.plot(df["epoch"], df["loss"], label="Training Loss")
    plt.plot(df["epoch"], df["eval_loss"], label="Evaluation Loss")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.title("Training and Evaluation Loss")
    plt.legend()
    if output:
        plt.savefig(output, bbox_inches="tight")
        print(f"Saved to {output}")
    else:
        plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "trainer_state",
        help="Path to trainer_state.json produced by a HuggingFace Trainer run",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=None,
        help="Save the plot to this file (e.g. loss.png) instead of displaying it",
    )
    args = parser.parse_args()

    try:
        df = _load_loss_df(args.trainer_state)
    except FileNotFoundError:
        sys.exit(f"File not found: {args.trainer_state}")

    _plot(df, args.output)


if __name__ == "__main__":
    main()
