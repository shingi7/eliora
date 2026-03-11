from pathlib import Path

import pandas as pd


def main() -> None:
    df = pd.read_csv("data/processed/team_model_first_build.csv")

    score_cols = [
        "standarised_points_score",
        "adjusted_position_z_score",
        "composite_team_score",
        "total_score",
        "attacking_score_6",
        "defensive_score_8",
        "ball_progression_6",
        "xg_diff",
        "possesion_threat",
    ]

    # Ensure numeric for correlation
    df["points"] = pd.to_numeric(df["points"], errors="coerce")
    for col in score_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    corrs = {}
    for col in score_cols:
        corrs[col] = df["points"].corr(df[col])

    print("Pearson correlations with points (highest to lowest):")
    for col, corr in sorted(corrs.items(), key=lambda x: x[1], reverse=True):
        print(f"- {col}: {corr:.4f}")
    print(
        "\nNote: 'standarised_points_score' is derived from points and is not an independent predictor."
    )

    # Save correlations
    processed_dir = Path("data/processed")
    docs_dir = Path("docs")
    processed_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    correlations_path = processed_dir / "team_model_correlations.csv"
    pd.DataFrame(
        {
            "metric": score_cols,
            "correlation_with_points": [corrs[m] for m in score_cols],
        }
    ).to_csv(correlations_path, index=False)

    # Order comparison
    n_rows = len(df)
    points_order = (
        df.sort_values(by="points", ascending=False, kind="mergesort")
        .reset_index()
        .assign(points_order=range(1, n_rows + 1))
        .set_index("index")["points_order"]
    )
    composite_order = (
        df.sort_values(by="composite_team_score", ascending=False, kind="mergesort")
        .reset_index()
        .assign(composite_order=range(1, n_rows + 1))
        .set_index("index")["composite_order"]
    )

    df["points_order"] = points_order
    df["composite_order"] = composite_order
    df["underlying_minus_results_order"] = df["composite_order"] - df["points_order"]

    display_cols = [
        "year",
        "team",
        "points",
        "composite_team_score",
        "points_order",
        "composite_order",
        "underlying_minus_results_order",
    ]

    # Save underlying vs results
    underlying_path = processed_dir / "team_model_underlying_vs_results.csv"
    df[display_cols].to_csv(underlying_path, index=False)

    print("\nTop 10: underlying score better than results (most negative)")
    print(
        df.sort_values(by="underlying_minus_results_order", ascending=True)
        .head(10)[display_cols]
        .to_string(index=False)
    )

    print("\nTop 10: results better than underlying score (most positive)")
    print(
        df.sort_values(by="underlying_minus_results_order", ascending=False)
        .head(10)[display_cols]
        .to_string(index=False)
    )

    # Write markdown note
    note_path = docs_dir / "team_model_relationship_outputs.md"
    note_lines = [
        "# Team Model Relationship Outputs",
        "",
        "- Script: src/check_team_model_relationships.py",
        "- Outputs:",
        f"  - {correlations_path}",
        f"  - {underlying_path}",
        "",
        "## File descriptions",
        "- team_model_correlations.csv: Pearson correlations between points and key score metrics.",
        "- team_model_underlying_vs_results.csv: Row-level comparison of points order vs composite score order.",
    ]
    note_path.write_text("\n".join(note_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
