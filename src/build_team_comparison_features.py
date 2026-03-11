import pandas as pd


def main() -> None:
    input_path = "data/processed/team_model_full_export.csv"
    output_path = "data/processed/team_comparison_features.csv"

    identity_cols = [
        "year",
        "team",
    ]

    df = pd.read_csv(input_path)

    for col in identity_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    numeric_cols = []
    for col in df.columns:
        if col in identity_cols:
            continue
        numeric_series = pd.to_numeric(df[col], errors="coerce")
        if numeric_series.notna().any():
            df[col] = numeric_series
            numeric_cols.append(col)
        else:
            df = df.drop(columns=[col])

    for col in numeric_cols:
        mean = df[col].mean()
        std = df[col].std(ddof=0)
        z_col = f"{col}_z"
        if std == 0 or pd.isna(std):
            df[z_col] = pd.NA
        else:
            df[z_col] = (df[col] - mean) / std

    df.to_csv(output_path, index=False)


if __name__ == "__main__":
    main()
