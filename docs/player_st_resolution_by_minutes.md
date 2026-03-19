# Player ST Resolution by Minutes Played

- Script: src/resolve_player_st_duplicates_by_minutes.py
- Source: data/processed/player_st_first_build_cleaned.csv
- Resolved output: data/processed/player_st_first_build_resolved.csv
- Rows removed output: data/processed/player_st_rows_removed_by_minutes_rule.csv
- Unresolved output: data/processed/player_st_unresolved_after_minutes_rule.csv
- Duplicate key: season, player_900_plus_mins, team
- Resolution rule: keep highest minutes_played; ties remain unresolved
- Row count before resolution: 286
- Row count after resolution: 280
- Rows removed by rule: 1
- Unresolved duplicate keys remaining: 0
- Unresolved rows remaining: 0