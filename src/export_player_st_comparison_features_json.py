import json
from pathlib import Path

import pandas as pd


def main() -> None:
    input_path = "data/processed/player_st_comparison_features.csv"
    output_path = "site/data/player_st_comparison_features.json"

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
        "non_pkxg_p90",
        "non_penalty_goals_p90",
        "shots_per_90",
        "shots_on_target_pct",
        "offensive_duels_won_pct",
        "touches_in_box_per_90",
        "key_passes_per_90",
        "xa_per_90",
        "xg",
        "non_pkxg",
        "goal_conversion_pct",
        "offensive_duels_per_90",
        "passes_to_penalty_area_per_90",
        "accurate_passes_to_penalty_area_pct",
        "penalties_taken",
        "possession",
        "shooting_impact",
        "penalty_box_passes_impact",
    ]

    z_cols = [
        "overall_percentile_z",
        "goal_threat_percentile_z",
        "link_play_percentile_z",
        "non_pkxg_p90_z",
        "non_penalty_goals_p90_z",
        "shots_per_90_z",
        "shots_on_target_pct_z",
        "offensive_duels_won_pct_z",
        "touches_in_box_per_90_z",
        "key_passes_per_90_z",
        "xa_per_90_z",
        "xg_z",
        "non_pkxg_z",
        "goal_conversion_pct_z",
        "offensive_duels_per_90_z",
        "passes_to_penalty_area_per_90_z",
        "accurate_passes_to_penalty_area_pct_z",
        "penalties_taken_z",
        "possession_z",
        "shooting_impact_z",
        "penalty_box_passes_impact_z",
    ]

    df = pd.read_csv(input_path)
    df = df[identity_cols + metric_cols + z_cols].copy()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, ensure_ascii=True)


if __name__ == "__main__":
    main()
