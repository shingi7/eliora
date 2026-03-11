import pandas as pd


def main() -> None:
    input_path = "data/processed/player_st_first_build_cleaned.csv"
    resolved_path = "data/processed/player_st_first_build_resolved.csv"
    removed_path = "data/processed/player_st_rows_removed_by_minutes_rule.csv"
    unresolved_path = "data/processed/player_st_unresolved_after_minutes_rule.csv"
    doc_path = "docs/player_st_resolution_by_minutes.md"

    key_cols = ["season", "player_900_plus_mins", "team"]
    minutes_col = "minutes_played"

    df = pd.read_csv(input_path)
    original_count = len(df)

    resolved_indices: list[int] = []
    removed_indices: list[int] = []
    unresolved_indices: list[int] = []

    for _, group in df.groupby(key_cols, sort=False):
        if len(group) == 1:
            resolved_indices.append(group.index[0])
            continue

        minutes = pd.to_numeric(group[minutes_col], errors="coerce")
        if minutes.notna().any():
            max_val = minutes.max()
            max_mask = minutes == max_val
        else:
            max_mask = minutes.isna()

        if int(max_mask.sum()) == 1:
            keep_idx = group.index[max_mask][0]
            resolved_indices.append(keep_idx)
            removed_indices.extend(group.index[~max_mask].tolist())
        else:
            unresolved_indices.extend(group.index.tolist())

    resolved_df = df.loc[resolved_indices].sort_index()
    removed_df = df.loc[removed_indices].sort_index()
    unresolved_df = df.loc[unresolved_indices].sort_index()

    resolved_df.to_csv(resolved_path, index=False)
    removed_df.to_csv(removed_path, index=False)
    unresolved_df.to_csv(unresolved_path, index=False)

    unresolved_key_count = (
        unresolved_df[key_cols]
        .drop_duplicates()
        .shape[0]
    )

    lines = [
        "# Player ST Resolution by Minutes Played",
        "",
        f"- Script: src/resolve_player_st_duplicates_by_minutes.py",
        f"- Source: {input_path}",
        f"- Resolved output: {resolved_path}",
        f"- Rows removed output: {removed_path}",
        f"- Unresolved output: {unresolved_path}",
        f"- Duplicate key: {', '.join(key_cols)}",
        f"- Resolution rule: keep highest {minutes_col}; ties remain unresolved",
        f"- Row count before resolution: {original_count}",
        f"- Row count after resolution: {len(resolved_df)}",
        f"- Rows removed by rule: {len(removed_df)}",
        f"- Unresolved duplicate keys remaining: {unresolved_key_count}",
        f"- Unresolved rows remaining: {len(unresolved_df)}",
    ]

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
