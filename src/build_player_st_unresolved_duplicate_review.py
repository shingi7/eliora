import pandas as pd


def main() -> None:
    input_path = "data/processed/player_st_first_build_unresolved_duplicates.csv"
    output_path = "data/processed/player_st_unresolved_duplicate_review.csv"
    doc_path = "docs/player_st_unresolved_duplicate_review.md"

    key_cols = ["season", "player_900_plus_mins", "team"]
    review_cols = [
        "season",
        "player_900_plus_mins",
        "team",
        "minutes_played",
        "total_stdev",
        "overall_rank",
        "xg",
        "non_pkxg",
        "non_pkxg_p90",
        "non_penalty_goals_p90",
        "shots_per_90",
        "shots_on_target_pct",
        "shooting_impact",
        "goal_conversion_pct",
        "goal_threat_rank",
        "offensive_duels_per_90",
        "offensive_duels_won_pct",
        "offensive_duel_impact",
        "touches_in_box_per_90",
        "key_passes_per_90",
        "passes_to_penalty_area_per_90",
        "accurate_passes_to_penalty_area_pct",
        "penalty_box_passes_impact",
        "xa_per_90",
        "link_play_rank",
    ]

    df = pd.read_csv(input_path)
    review_df = df[review_cols].copy()
    review_df.to_csv(output_path, index=False)

    unresolved_keys = (
        df[key_cols]
        .drop_duplicates()
        .sort_values(by=key_cols, ascending=True)
        .values.tolist()
    )

    lines = [
        "# Player ST Unresolved Duplicate Review",
        "",
        f"- Script: src/build_player_st_unresolved_duplicate_review.py",
        f"- Source: {input_path}",
        f"- Output: {output_path}",
        "",
        "## Unresolved duplicate keys reviewed",
    ]

    if unresolved_keys:
        for season, player, team in unresolved_keys:
            lines.append(f"- {season}, {player}, {team}")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Note",
            "- No automatic resolution was applied.",
        ]
    )

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
