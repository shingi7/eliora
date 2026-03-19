import pandas as pd


def main() -> None:
    input_path = "data/raw/USL C 2022+ Positional Data V7.xlsx"
    output_path = "data/processed/player_st_first_build.csv"
    sheet_name = "ST"

    column_map = {
        "Season": "season",
        "Player 900+ mins": "player_900_plus_mins",
        "Team": "team",
        "Possession": "possession",
        "Total STDEV": "total_stdev",
        "Overall Rank": "overall_rank",
        "Minutes played": "minutes_played",
        "xG": "xg",
        "Penalties taken": "penalties_taken",
        "Non PKxG": "non_pkxg",
        "Non PKxG P90": "non_pkxg_p90",
        "Non-penalty goals p90": "non_penalty_goals_p90",
        "Shots per 90": "shots_per_90",
        "Shots on target, %": "shots_on_target_pct",
        "Shooting Impact": "shooting_impact",
        "Goal conversion %": "goal_conversion_pct",
        "Goal Threat Stdev": "goal_threat_stdev",
        "Goal Threat Rank": "goal_threat_rank",
        "Def Duel Impact": "defensive_duel_impact",
        "Aerial Duel impact": "aerial_duel_impact",
        "Offensive duels per 90": "offensive_duels_per_90",
        "Offensive duels won, %": "offensive_duels_won_pct",
        "Offensive Duel Impact": "offensive_duel_impact",
        "Progressive runs per 90": "progressive_runs_per_90",
        "Accelerations per 90": "accelerations_per_90",
        "Dribble Impact": "dribble_impact",
        "Received passes per 90": "received_passes_per_90",
        "Touches in box per 90": "touches_in_box_per_90",
        "Key passes per 90": "key_passes_per_90",
        "Passes to penalty area per 90": "passes_to_penalty_area_per_90",
        "Accurate passes to penalty area, %": "accurate_passes_to_penalty_area_pct",
        "Penalty box passes Impact": "penalty_box_passes_impact",
        "xA per 90": "xa_per_90",
        "Link Play Stdev": "link_play_stdev",
        "Link Play Rank": "link_play_rank",
    }

    df = pd.read_excel(input_path, sheet_name=sheet_name, usecols=list(column_map.keys()))
    missing = [col for col in column_map if col not in df.columns]
    if missing:
        raise ValueError(f"Missing expected columns in {sheet_name} sheet: {missing}")

    df = df.rename(columns=column_map)
    df.to_csv(output_path, index=False)


if __name__ == "__main__":
    main()
