import os

import pandas as pd


def main() -> None:
    input_path = "data/processed/player_st_leaderboard_1200mins.csv"
    output_path = "outputs/player_st_top15_2025.png"
    doc_path = "docs/player_st_top15_chart.md"

    os.makedirs("outputs", exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", "outputs/.matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = pd.read_csv(input_path)
    df_2025 = df[df["season"] == 2025].copy()
    df_2025 = df_2025.sort_values(by="overall_percentile", ascending=False).head(15)

    labels = df_2025.apply(
        lambda row: f"{row['player']} ({row['team']})", axis=1
    )

    plt.figure(figsize=(10, 7))
    plt.barh(labels, df_2025["overall_percentile"])
    plt.xlabel("Overall Percentile")
    plt.title("Top 15 ST Overall Percentile — 2025 (1200+ mins)")
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

    lines = [
        "# Player ST Top 15 Chart",
        "",
        f"- Script: src/plot_player_st_top15.py",
        f"- Input: {input_path}",
        f"- Output image: {output_path}",
        "",
        "Note: chart uses the 1200-minute filtered leaderboard and 2025 season only.",
    ]

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
