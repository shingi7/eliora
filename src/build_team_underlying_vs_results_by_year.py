import pandas as pd


def main() -> None:
    input_path = "data/processed/team_model_first_build.csv"
    output_underlying = "data/processed/team_underlying_vs_results_by_year.csv"
    output_luck = "data/processed/team_luck_table_by_year.csv"
    doc_path = "docs/team_underlying_vs_results_by_year.md"

    df = pd.read_csv(input_path)

    def add_within_year_orders(group: pd.DataFrame) -> pd.DataFrame:
        group = group.copy()
        n_rows = len(group)
        points_order = (
            group.sort_values(by="points", ascending=False, kind="mergesort")
            .reset_index()
            .assign(points_order_within_year=range(1, n_rows + 1))
            .set_index("index")["points_order_within_year"]
        )
        composite_order = (
            group.sort_values(by="composite_team_score", ascending=False, kind="mergesort")
            .reset_index()
            .assign(composite_order_within_year=range(1, n_rows + 1))
            .set_index("index")["composite_order_within_year"]
        )
        group["points_order_within_year"] = points_order
        group["composite_order_within_year"] = composite_order
        group["underlying_minus_results_order_within_year"] = (
            group["composite_order_within_year"] - group["points_order_within_year"]
        )
        return group

    df = df.groupby("year", group_keys=False).apply(add_within_year_orders)

    df.to_csv(output_underlying, index=False)

    def bucket(val: float) -> str:
        if val <= -3:
            return "unlucky"
        if val >= 3:
            return "lucky"
        return "about_expected"

    luck_cols = [
        "year",
        "team",
        "points",
        "composite_team_score",
        "points_order_within_year",
        "composite_order_within_year",
        "underlying_minus_results_order_within_year",
    ]

    luck_df = df[luck_cols].copy()
    luck_df["luck_bucket"] = luck_df["underlying_minus_results_order_within_year"].apply(
        bucket
    )
    luck_df.to_csv(output_luck, index=False)

    doc_lines = [
        "# Team Underlying vs Results by Year",
        "",
        "- Script: src/build_team_underlying_vs_results_by_year.py",
        f"- Source: {input_path}",
        "- Outputs:",
        f"  - {output_underlying}",
        f"  - {output_luck}",
        "",
        "## Notes",
        "- Rankings are computed within each season (year), not across all seasons pooled.",
        "",
        "## luck_bucket rules (within-year)",
        "- <= -3: unlucky",
        "- >= 3: lucky",
        "- otherwise: about_expected",
    ]

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(doc_lines))


if __name__ == "__main__":
    main()
