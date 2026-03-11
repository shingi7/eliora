import pandas as pd


def main() -> None:
    df = pd.read_csv("data/processed/team_model_first_build.csv")

    print("shape:", df.shape)
    print("columns:")
    print(list(df.columns))
    print("\nfirst 5 rows:")
    print(df.head(5))

    print("\ntop 10 by composite_team_score (desc):")
    print(df.sort_values(by="composite_team_score", ascending=False).head(10))

    print("\ntop 10 by points (desc):")
    print(df.sort_values(by="points", ascending=False).head(10))


if __name__ == "__main__":
    main()
