import pandas as pd


def main() -> None:
    input_path = "data/processed/player_st_first_build.csv"
    cleaned_path = "data/processed/player_st_first_build_cleaned.csv"
    unresolved_path = "data/processed/player_st_first_build_unresolved_duplicates.csv"
    doc_path = "docs/player_st_first_build_cleaning.md"

    dup_cols = ["season", "player_900_plus_mins", "team"]

    df = pd.read_csv(input_path)
    original_count = len(df)

    df_deduped = df.drop_duplicates()
    deduped_count = len(df_deduped)
    exact_removed = original_count - deduped_count

    dup_mask = df_deduped.duplicated(subset=dup_cols, keep=False)
    unresolved_rows = df_deduped.loc[dup_mask].copy()
    unresolved_rows = unresolved_rows.sort_values(by=dup_cols, ascending=True)
    unresolved_rows.to_csv(unresolved_path, index=False)

    unresolved_keys = (
        unresolved_rows[dup_cols]
        .drop_duplicates()
        .sort_values(by=dup_cols, ascending=True)
        .values.tolist()
    )
    unresolved_key_count = len(unresolved_keys)
    unresolved_row_count = len(unresolved_rows)

    df_deduped.to_csv(cleaned_path, index=False)

    lines = [
        "# Player ST First-Build Cleaning",
        "",
        f"- Script: src/clean_player_st_first_build.py",
        f"- Input: {input_path}",
        f"- Cleaned output: {cleaned_path}",
        f"- Unresolved duplicates output: {unresolved_path}",
        f"- Original row count: {original_count}",
        f"- Row count after removing exact duplicates: {deduped_count}",
        f"- Exact duplicates removed: {exact_removed}",
        f"- Unresolved duplicate keys remaining: {unresolved_key_count}",
        f"- Unresolved duplicate rows remaining: {unresolved_row_count}",
        "",
        "## Unresolved duplicate keys",
    ]

    if unresolved_keys:
        for season, player, team in unresolved_keys:
            lines.append(f"- {season}, {player}, {team}")
    else:
        lines.append("- None")

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
