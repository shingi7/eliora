import pandas as pd


def main() -> None:
    input_path = "data/processed/player_st_first_build.csv"
    duplicates_path = "data/processed/player_st_duplicate_rows.csv"
    summary_path = "data/processed/player_st_duplicate_summary.csv"
    doc_path = "docs/player_st_duplicates.md"

    dup_cols = ["season", "player_900_plus_mins", "team"]

    df = pd.read_csv(input_path)

    dup_mask = df.duplicated(subset=dup_cols, keep=False)
    dup_rows = df.loc[dup_mask].copy()
    dup_rows = dup_rows.sort_values(by=dup_cols, ascending=True)

    dup_summary = (
        dup_rows.groupby(dup_cols, dropna=False)
        .size()
        .reset_index(name="duplicate_count")
        .sort_values(by=dup_cols, ascending=True)
    )

    dup_rows.to_csv(duplicates_path, index=False)
    dup_summary.to_csv(summary_path, index=False)

    lines = [
        "# Player ST Duplicate Inspection",
        "",
        f"- Script: src/inspect_player_st_duplicates.py",
        f"- Input: {input_path}",
        f"- Duplicate rows output: {duplicates_path}",
        f"- Duplicate summary output: {summary_path}",
        f"- Duplicate key: {', '.join(dup_cols)}",
        f"- Duplicated keys: {len(dup_summary)}",
        f"- Duplicate rows exported: {len(dup_rows)}",
    ]

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
