import pandas as pd


def main() -> None:
    input_path = "data/processed/team_luck_table.csv"
    counts_output = "data/processed/team_luck_bucket_counts_by_year.csv"
    summary_output = "data/processed/team_luck_year_summary.csv"

    df = pd.read_csv(input_path)

    counts = (
        df.groupby(["year", "luck_bucket"], as_index=False)
        .size()
        .rename(columns={"size": "team_count"})
    )

    summary = (
        df.groupby("year", as_index=False)
        .agg(
            total_teams=("team", "count"),
            avg_underlying_minus_results_order=(
                "underlying_minus_results_order",
                "mean",
            ),
            min_underlying_minus_results_order=(
                "underlying_minus_results_order",
                "min",
            ),
            max_underlying_minus_results_order=(
                "underlying_minus_results_order",
                "max",
            ),
        )
    )

    counts.to_csv(counts_output, index=False)
    summary.to_csv(summary_output, index=False)


if __name__ == "__main__":
    main()
