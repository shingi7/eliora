import numpy as np
import pandas as pd


def clean_series(series: pd.Series) -> pd.Series:
    if series.dtype == object:
        return series.replace(r"^\s*$", np.nan, regex=True)
    return series


def infer_type(series: pd.Series) -> str:
    series_clean = clean_series(series)
    total_non_na = series_clean.notna().sum()
    if total_non_na == 0:
        return "likely text"
    numeric_series = pd.to_numeric(series_clean, errors="coerce")
    numeric_non_na = numeric_series.notna().sum()
    if numeric_non_na / total_non_na < 0.9:
        return "likely text"
    numeric_values = numeric_series.dropna()
    if (numeric_values % 1 == 0).all():
        return "likely integer"
    return "likely decimal"


def format_value(value: float) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return f"{value:.6g}"
    return str(value)


def main() -> None:
    input_path = "data/processed/player_st_first_build.csv"
    output_path = "docs/player_st_first_build_validation.md"

    df = pd.read_csv(input_path)

    row_count = len(df)
    col_count = df.shape[1]
    columns = list(df.columns)

    missing_counts = {}
    for col in columns:
        series = df[col]
        if series.dtype == object:
            blank_mask = series.isna() | series.astype(str).str.strip().eq("")
            missing_counts[col] = int(blank_mask.sum())
        else:
            missing_counts[col] = int(series.isna().sum())

    key_cols = ["season", "player_900_plus_mins", "team"]
    duplicate_key_count = int(df.duplicated(subset=key_cols).sum())

    type_map = {col: infer_type(df[col]) for col in columns}

    numeric_ranges = {}
    for col in columns:
        if type_map[col] == "likely text":
            continue
        series = pd.to_numeric(clean_series(df[col]), errors="coerce")
        if series.notna().any():
            numeric_ranges[col] = (series.min(), series.max())
        else:
            numeric_ranges[col] = (np.nan, np.nan)

    issues = []

    player_series = df["player_900_plus_mins"]
    player_blank = (
        player_series.isna()
        | player_series.astype(str).str.strip().eq("")
    ).sum()
    if player_blank > 0:
        issues.append(f"Blank player names: {int(player_blank)}")

    team_series = df["team"]
    team_blank = (team_series.isna() | team_series.astype(str).str.strip().eq("")).sum()
    if team_blank > 0:
        issues.append(f"Blank team names: {int(team_blank)}")

    if duplicate_key_count > 0:
        issues.append(
            f"Duplicate season-player-team rows: {duplicate_key_count}"
        )

    numeric_expected = [col for col in columns if col not in ["player_900_plus_mins", "team"]]
    for col in numeric_expected:
        series_clean = clean_series(df[col])
        non_na = series_clean.notna().sum()
        numeric_series = pd.to_numeric(series_clean, errors="coerce")
        non_numeric = non_na - numeric_series.notna().sum()
        if non_numeric > 0:
            issues.append(
                f"Non-numeric values in numeric-expected column `{col}`: {int(non_numeric)}"
            )

    pct_cols = [col for col in columns if "pct" in col]
    for col in pct_cols:
        series = pd.to_numeric(clean_series(df[col]), errors="coerce").dropna()
        if series.empty:
            continue
        max_val = float(series.max())
        min_val = float(series.min())
        if max_val <= 1.5:
            out_of_range = int(((series < 0) | (series > 1)).sum())
            expected = "0-1"
        else:
            out_of_range = int(((series < 0) | (series > 100)).sum())
            expected = "0-100"
        if out_of_range > 0:
            issues.append(
                f"Values outside expected percentage range ({expected}) in `{col}`: {out_of_range} (min {min_val:.6g}, max {max_val:.6g})"
            )

    non_negative_cols = [
        "season",
        "possession",
        "minutes_played",
        "penalties_taken",
        "xg",
        "non_pkxg",
        "non_pkxg_p90",
        "non_penalty_goals_p90",
        "shots_per_90",
        "shots_on_target_pct",
        "goal_conversion_pct",
        "offensive_duels_per_90",
        "offensive_duels_won_pct",
        "touches_in_box_per_90",
        "key_passes_per_90",
        "passes_to_penalty_area_per_90",
        "accurate_passes_to_penalty_area_pct",
        "xa_per_90",
    ]
    for col in non_negative_cols:
        if col not in df.columns:
            continue
        series = pd.to_numeric(clean_series(df[col]), errors="coerce").dropna()
        if series.empty:
            continue
        neg_count = int((series < 0).sum())
        if neg_count > 0:
            issues.append(
                f"Negative values in `{col}`: {neg_count} (min {series.min():.6g})"
            )

    rank_cols = [col for col in columns if "rank" in col]
    for col in rank_cols:
        series = pd.to_numeric(clean_series(df[col]), errors="coerce").dropna()
        if series.empty:
            continue
        max_val = float(series.max())
        min_val = float(series.min())
        if max_val <= 1.5:
            out_of_range = int(((series < 0) | (series > 1)).sum())
            expected = "0-1"
        else:
            out_of_range = int(((series < 1) | (series > row_count)).sum())
            expected = f"1-{row_count}"
        if out_of_range > 0:
            issues.append(
                f"Rank values outside expected range ({expected}) in `{col}`: {out_of_range} (min {min_val:.6g}, max {max_val:.6g})"
            )

    lines = []
    lines.append("# Player ST First-Build Validation")
    lines.append("")
    lines.append(f"- Source CSV: {input_path}")
    lines.append("")
    lines.append("## Shape")
    lines.append(f"- Row count: {row_count}")
    lines.append(f"- Column count: {col_count}")
    lines.append("")
    lines.append("## Column names")
    for col in columns:
        lines.append(f"- {col}")
    lines.append("")
    lines.append("## Missing values by column")
    lines.append("| column | missing_count |")
    lines.append("| --- | ---: |")
    for col in columns:
        lines.append(f"| {col} | {missing_counts[col]} |")
    lines.append("")
    lines.append("## Duplicate key check")
    lines.append(f"- Key columns: {', '.join(key_cols)}")
    lines.append(f"- Duplicate rows: {duplicate_key_count}")
    lines.append("")
    lines.append("## Likely data types")
    lines.append("| column | likely_type |")
    lines.append("| --- | --- |")
    for col in columns:
        lines.append(f"| {col} | {type_map[col]} |")
    lines.append("")
    lines.append("## Numeric ranges (min, max)")
    lines.append("| column | min | max |")
    lines.append("| --- | ---: | ---: |")
    for col, (min_val, max_val) in numeric_ranges.items():
        lines.append(
            f"| {col} | {format_value(min_val)} | {format_value(max_val)} |"
        )
    lines.append("")
    lines.append("## Suspicious issues")
    if issues:
        for issue in issues:
            lines.append(f"- {issue}")
    else:
        lines.append("- None detected.")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
