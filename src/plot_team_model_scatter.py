from pathlib import Path
import os

mpl_dir = Path("outputs/.matplotlib")
mpl_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(mpl_dir))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def main() -> None:
    df = pd.read_csv("data/processed/team_model_first_build.csv")

    x = df["composite_team_score"]
    y = df["points"]

    plt.figure(figsize=(10, 7))
    plt.scatter(x, y)
    plt.xlabel("Composite Team Score")
    plt.ylabel("Points")
    plt.title("Points vs Composite Team Score")

    # Compute order columns for selective labeling
    n_rows = len(df)
    points_order = (
        df.sort_values(by="points", ascending=False, kind="mergesort")
        .reset_index()
        .assign(points_order=range(1, n_rows + 1))
        .set_index("index")["points_order"]
    )
    composite_order = (
        df.sort_values(by="composite_team_score", ascending=False, kind="mergesort")
        .reset_index()
        .assign(composite_order=range(1, n_rows + 1))
        .set_index("index")["composite_order"]
    )
    df["points_order"] = points_order
    df["composite_order"] = composite_order
    df["underlying_minus_results_order"] = df["composite_order"] - df["points_order"]

    # Select rows to label
    label_indices = set()
    label_indices.update(
        df.sort_values(by="points", ascending=False).head(8).index.tolist()
    )
    label_indices.update(
        df.sort_values(by="composite_team_score", ascending=False).head(8).index.tolist()
    )
    label_indices.update(
        df.sort_values(by="underlying_minus_results_order", ascending=True)
        .head(8)
        .index.tolist()
    )
    label_indices.update(
        df.sort_values(by="underlying_minus_results_order", ascending=False)
        .head(8)
        .index.tolist()
    )

    # Add team labels (year + team) for selected points only
    for idx, row in df.iterrows():
        if idx not in label_indices:
            continue
        label = f"{int(row['year'])} {row['team']}"
        plt.annotate(
            label,
            (row["composite_team_score"], row["points"]),
            fontsize=6,
            alpha=0.7,
        )

    output_dir = Path("outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "team_points_vs_composite_score_labeled.png"
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


if __name__ == "__main__":
    main()
