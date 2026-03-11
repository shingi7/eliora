import pandas as pd


def main() -> None:
    input_path = "data/processed/team_model_underlying_vs_results.csv"
    output_path = "data/processed/team_luck_table.csv"

    df = pd.read_csv(input_path)

    def bucket(val: float) -> str:
        if val <= -10:
            return "unlucky"
        if val >= 10:
            return "lucky"
        return "about_expected"

    df["luck_bucket"] = df["underlying_minus_results_order"].apply(bucket)

    df = df.sort_values(by="underlying_minus_results_order", ascending=True)

    keep_cols = [
        "year",
        "team",
        "points",
        "composite_team_score",
        "points_order",
        "composite_order",
        "underlying_minus_results_order",
        "luck_bucket",
    ]

    df[keep_cols].to_csv(output_path, index=False)


if __name__ == "__main__":
    main()
