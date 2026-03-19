import pandas as pd


def main() -> None:
    input_path = "data/processed/player_st_analysis_ready.csv"
    output_path = "data/processed/player_st_comparison_features.csv"
    doc_path = "docs/player_st_comparison_features.md"

    identity_cols = [
        "season",
        "player",
        "team",
        "position",
        "minutes_played",
    ]

    metric_cols = [
        "overall_percentile",
        "goal_threat_percentile",
        "link_play_percentile",
        "total_stdev",
        "goal_threat_stdev",
        "link_play_stdev",
        "defensive_duel_impact",
        "aerial_duel_impact",
        "non_pkxg_p90",
        "non_penalty_goals_p90",
        "shots_per_90",
        "shots_on_target_pct",
        "offensive_duels_won_pct",
        "progressive_runs_per_90",
        "accelerations_per_90",
        "dribble_impact",
        "received_passes_per_90",
        "touches_in_box_per_90",
        "key_passes_per_90",
        "xa_per_90",
        "xg",
        "non_pkxg",
        "goal_conversion_pct",
        "offensive_duels_per_90",
        "offensive_duel_impact",
        "passes_to_penalty_area_per_90",
        "accurate_passes_to_penalty_area_pct",
        "penalties_taken",
        "possession",
        "shooting_impact",
        "penalty_box_passes_impact",
    ]

    df = pd.read_csv(input_path)
    df = df[identity_cols + metric_cols].copy()

    for col in metric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in metric_cols:
        mean = df[col].mean()
        std = df[col].std(ddof=0)
        z_col = f"{col}_z"
        if std == 0 or pd.isna(std):
            df[z_col] = pd.NA
        else:
            df[z_col] = (df[col] - mean) / std

    df.to_csv(output_path, index=False)

    lines = [
        "# Player ST Comparison Features",
        "",
        f"- Script: src/build_player_st_comparison_features.py",
        f"- Input: {input_path}",
        f"- Output: {output_path}",
        "",
        "## Identity columns",
    ]

    for col in identity_cols:
        lines.append(f"- {col}")

    lines.extend(["", "## Comparison metrics"])
    for col in metric_cols:
        lines.append(f"- {col}")

    lines.extend(
        [
            "",
            "Note: z-score columns were added to support future similarity calculations.",
        ]
    )

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
