import re

import pandas as pd


def normalize_keys(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["team"] = df["team"].astype(str).str.strip()
    df = df[df["year"].notna()]
    df = df[df["team"].notna() & (df["team"] != "")]
    return df


def is_excluded(col: str) -> bool:
    lower = col.lower()
    if "_sub" in lower:
        return True
    if re.search(r"_[0-9]+$", lower):
        return True
    for token in ("correlation", "mean", "range", "stdev", "normalize"):
        if token in lower:
            return True
    return False


def main() -> None:
    first_build_path = "data/processed/team_model_first_build.csv"
    full_export_path = "data/processed/team_model_full_export.csv"
    output_path = "data/processed/team_comparison_features.csv"

    identity_cols = ["year", "team"]

    first_df = pd.read_csv(first_build_path)
    full_df = pd.read_csv(full_export_path)

    for col in identity_cols:
        if col not in first_df.columns:
            raise ValueError(f"Missing required column in first build: {col}")
        if col not in full_df.columns:
            raise ValueError(f"Missing required column in full export: {col}")

    first_df = normalize_keys(first_df)
    full_df = normalize_keys(full_df)

    base_cols = set(first_df.columns)
    additional_cols = []
    for col in full_df.columns:
        if col in identity_cols or col in base_cols:
            continue
        if is_excluded(col):
            continue
        numeric_series = pd.to_numeric(full_df[col], errors="coerce")
        if numeric_series.notna().mean() < 0.8:
            continue
        additional_cols.append(col)

    full_trim = full_df[identity_cols + additional_cols].copy()

    hybrid = first_df.merge(full_trim, on=identity_cols, how="left")

    numeric_cols = []
    for col in hybrid.columns:
        if col in identity_cols:
            continue
        numeric_series = pd.to_numeric(hybrid[col], errors="coerce")
        if numeric_series.notna().any():
            hybrid[col] = numeric_series
            numeric_cols.append(col)
        else:
            hybrid = hybrid.drop(columns=[col])

    for col in numeric_cols:
        mean = hybrid[col].mean()
        std = hybrid[col].std(ddof=0)
        z_col = f"{col}_z"
        if std == 0 or pd.isna(std):
            hybrid[z_col] = pd.NA
        else:
            hybrid[z_col] = (hybrid[col] - mean) / std

    hybrid.to_csv(output_path, index=False)


if __name__ == "__main__":
    main()
