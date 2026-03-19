# Player ST Analysis-Ready Export

- Script: src/prepare_player_st_analysis_ready.py
- Input: data/processed/player_st_first_build_resolved.csv
- Output: data/processed/player_st_analysis_ready.csv

## Rename mapping
- player_900_plus_mins -> player
- overall_rank -> overall_percentile
- goal_threat_rank -> goal_threat_percentile
- link_play_rank -> link_play_percentile

## Added column
- position = ST