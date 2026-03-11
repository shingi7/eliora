import json
from pathlib import Path

import pandas as pd


def main() -> None:
    input_path = "data/processed/team_comparison_features.csv"
    output_path = "site/data/team_comparison_features.json"

    df = pd.read_csv(input_path)
    df = df.astype(object).where(pd.notna(df), None)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, ensure_ascii=True, allow_nan=False)


if __name__ == "__main__":
    main()
