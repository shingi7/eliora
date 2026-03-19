# Player ST Comparison Features

- Script: src/build_player_st_comparison_features.py
- Input: data/processed/player_st_analysis_ready.csv
- Output: data/processed/player_st_comparison_features.csv

## Identity columns
- season
- player
- team
- position
- minutes_played

## Comparison metrics
- overall_percentile
- goal_threat_percentile
- link_play_percentile
- total_stdev
- goal_threat_stdev
- link_play_stdev
- defensive_duel_impact
- aerial_duel_impact
- non_pkxg_p90
- non_penalty_goals_p90
- shots_per_90
- shots_on_target_pct
- offensive_duels_won_pct
- progressive_runs_per_90
- accelerations_per_90
- dribble_impact
- received_passes_per_90
- touches_in_box_per_90
- key_passes_per_90
- xa_per_90
- xg
- non_pkxg
- goal_conversion_pct
- offensive_duels_per_90
- offensive_duel_impact
- passes_to_penalty_area_per_90
- accurate_passes_to_penalty_area_pct
- penalties_taken
- possession
- shooting_impact
- penalty_box_passes_impact

Note: z-score columns were added to support future similarity calculations.