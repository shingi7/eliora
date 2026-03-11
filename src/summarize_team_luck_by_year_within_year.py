import pandas as pd


def main() -> None:
    input_path = "data/processed/team_luck_table_by_year.csv"
    counts_output = "data/processed/team_luck_bucket_counts_by_year_within_year.csv"
    unlucky_output = "data/processed/team_unlucky_outliers_by_year.csv"
    lucky_output = "data/processed/team_lucky_outliers_by_year.csv"
    doc_path = "docs/team_luck_by_year_within_year.md"

    df = pd.read_csv(input_path)

    counts = (
        df.groupby(["year", "luck_bucket"], as_index=False)
        .size()
        .rename(columns={"size": "team_count"})
    )
    counts.to_csv(counts_output, index=False)

    keep_cols = [
        "year",
        "team",
        "points",
        "composite_team_score",
        "points_order_within_year",
        "composite_order_within_year",
        "underlying_minus_results_order_within_year",
        "luck_bucket",
    ]

    unlucky = (
        df[df["luck_bucket"] == "unlucky"]
        .sort_values(
            by=["year", "underlying_minus_results_order_within_year"],
            ascending=[True, True],
        )
        .loc[:, keep_cols]
    )
    unlucky.to_csv(unlucky_output, index=False)

    lucky = (
        df[df["luck_bucket"] == "lucky"]
        .sort_values(
            by=["year", "underlying_minus_results_order_within_year"],
            ascending=[True, False],
        )
        .loc[:, keep_cols]
    )
    lucky.to_csv(lucky_output, index=False)

    doc_lines = [
        "# Team Luck by Year (Within-Season)",
        "",
        "- Script: src/summarize_team_luck_by_year_within_year.py",
        f"- Input: {input_path}",
        "- Outputs:",
        f"  - {counts_output}",
        f"  - {unlucky_output}",
        f"  - {lucky_output}",
        "",
        "## Note",
        "- This summary uses within-season ranking to define luck buckets and outliers.",
    ]

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(doc_lines))


if __name__ == "__main__":
    main()
