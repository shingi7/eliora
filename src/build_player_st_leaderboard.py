import pandas as pd


def main() -> None:
    input_path = "data/processed/player_st_analysis_ready.csv"
    output_path = "data/processed/player_st_leaderboard.csv"
    output_1200_path = "data/processed/player_st_leaderboard_1200mins.csv"
    doc_path = "docs/player_st_leaderboard.md"

    keep_cols = [
        "season",
        "player",
        "team",
        "position",
        "minutes_played",
        "overall_percentile",
        "total_stdev",
        "goal_threat_percentile",
        "link_play_percentile",
        "non_pkxg_p90",
        "non_penalty_goals_p90",
        "shots_per_90",
        "shots_on_target_pct",
        "offensive_duels_won_pct",
        "touches_in_box_per_90",
        "key_passes_per_90",
        "xa_per_90",
    ]

    df = pd.read_csv(input_path)
    df = df[keep_cols].copy()
    df = df.sort_values(by=["season", "overall_percentile"], ascending=[True, False])
    df.to_csv(output_path, index=False)

    df_1200 = df[df["minutes_played"] >= 1200].copy()
    df_1200 = df_1200.sort_values(
        by=["season", "overall_percentile"], ascending=[True, False]
    )
    df_1200.to_csv(output_1200_path, index=False)

    lines = [
        "# Player ST Leaderboard",
        "",
        f"- Script: src/build_player_st_leaderboard.py",
        f"- Input: {input_path}",
        f"- Output: {output_path}",
        f"- Output (1200 mins): {output_1200_path}",
        "",
        "Note: the second file applies a 1200-minute filter.",
    ]

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
