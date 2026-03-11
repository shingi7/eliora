import pandas as pd


def main() -> None:
    input_path = "data/processed/player_st_analysis_ready.csv"
    output_path = "data/processed/player_st_correlations.csv"
    doc_path = "docs/player_st_relationships.md"

    df = pd.read_csv(input_path)

    metrics = [
        "total_stdev",
        "non_pkxg",
        "non_pkxg_p90",
        "non_penalty_goals_p90",
        "shots_per_90",
        "shots_on_target_pct",
        "shooting_impact",
        "goal_conversion_pct",
        "goal_threat_stdev",
        "goal_threat_percentile",
        "offensive_duels_per_90",
        "offensive_duels_won_pct",
        "offensive_duel_impact",
        "touches_in_box_per_90",
        "key_passes_per_90",
        "passes_to_penalty_area_per_90",
        "accurate_passes_to_penalty_area_pct",
        "penalty_box_passes_impact",
        "xa_per_90",
        "link_play_stdev",
        "link_play_percentile",
    ]

    df["overall_percentile"] = pd.to_numeric(df["overall_percentile"], errors="coerce")
    for col in metrics:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    correlations = []
    for col in metrics:
        corr = df["overall_percentile"].corr(df[col])
        correlations.append({"metric": col, "correlation_with_overall_percentile": corr})

    corr_df = pd.DataFrame(correlations).sort_values(
        by="correlation_with_overall_percentile", ascending=False
    )
    corr_df.to_csv(output_path, index=False)

    print("Correlations with overall_percentile (sorted):")
    print(corr_df.to_string(index=False))

    display_cols = [
        "season",
        "player",
        "team",
        "minutes_played",
        "overall_percentile",
        "total_stdev",
        "goal_threat_percentile",
        "link_play_percentile",
    ]

    top_15 = df.sort_values(by="overall_percentile", ascending=False).head(15)
    bottom_15 = df.sort_values(by="overall_percentile", ascending=True).head(15)

    print("\nTop 15 players by overall_percentile:")
    print(top_15[display_cols].to_string(index=False))

    print("\nBottom 15 players by overall_percentile:")
    print(bottom_15[display_cols].to_string(index=False))

    lines = [
        "# Player ST Relationships",
        "",
        f"- Script: src/check_player_st_relationships.py",
        f"- Input: {input_path}",
        f"- Output: {output_path}",
        "",
        "This is a first sanity check against the current spreadsheet-based ST overall score.",
    ]

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
