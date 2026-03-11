import numpy as np
import pandas as pd


def main() -> None:
    input_path = "data/processed/player_st_comparison_features.csv"
    output_path = "data/processed/player_st_similarity_example_c_jennings_2025.csv"
    doc_path = "docs/player_st_similarity_example.md"

    target_player = "C. Jennings"
    target_season = 2025.0

    feature_cols = [
        "overall_percentile_z",
        "goal_threat_percentile_z",
        "link_play_percentile_z",
        "non_pkxg_p90_z",
        "non_penalty_goals_p90_z",
        "shots_per_90_z",
        "shots_on_target_pct_z",
        "offensive_duels_won_pct_z",
        "touches_in_box_per_90_z",
        "key_passes_per_90_z",
        "xa_per_90_z",
    ]

    metric_cols = [
        "overall_percentile",
        "goal_threat_percentile",
        "link_play_percentile",
        "non_pkxg_p90",
        "non_penalty_goals_p90",
        "shots_per_90",
        "shots_on_target_pct",
        "offensive_duels_won_pct",
        "touches_in_box_per_90",
        "key_passes_per_90",
        "xa_per_90",
    ]

    df = pd.read_csv(input_path)
    df = df.dropna(subset=feature_cols).copy()

    target_mask = (df["player"] == target_player) & (df["season"] == target_season)
    target_rows = df.loc[target_mask]
    if target_rows.empty:
        raise ValueError(
            f"Target player-season not found after filtering: {target_player}, {target_season}"
        )

    target_row = target_rows.iloc[0]
    target_vector = target_row[feature_cols].to_numpy(dtype=float)

    features_matrix = df[feature_cols].to_numpy(dtype=float)
    distances = np.linalg.norm(features_matrix - target_vector, axis=1)
    df["similarity_distance"] = distances

    df = df.loc[~target_mask].copy()
    df = df.sort_values(by="similarity_distance", ascending=True).head(5)

    output_df = pd.DataFrame(
        {
            "target_player": target_player,
            "target_season": target_season,
            "similar_player": df["player"],
            "similar_season": df["season"],
            "team": df["team"],
            "minutes_played": df["minutes_played"],
            "similarity_distance": df["similarity_distance"],
            "overall_percentile": df["overall_percentile"],
            "goal_threat_percentile": df["goal_threat_percentile"],
            "link_play_percentile": df["link_play_percentile"],
            "non_pkxg_p90": df["non_pkxg_p90"],
            "non_penalty_goals_p90": df["non_penalty_goals_p90"],
            "shots_per_90": df["shots_per_90"],
            "shots_on_target_pct": df["shots_on_target_pct"],
            "offensive_duels_won_pct": df["offensive_duels_won_pct"],
            "touches_in_box_per_90": df["touches_in_box_per_90"],
            "key_passes_per_90": df["key_passes_per_90"],
            "xa_per_90": df["xa_per_90"],
        }
    )

    output_df.to_csv(output_path, index=False)

    lines = [
        "# Player ST Similarity Example",
        "",
        f"- Script: src/find_similar_st_players.py",
        f"- Input: {input_path}",
        f"- Output: {output_path}",
        "",
        "## Z-score feature columns used",
    ]
    for col in feature_cols:
        lines.append(f"- {col}")

    lines.extend(
        [
            "",
            "Note: this is a first Euclidean-distance prototype for ST only.",
        ]
    )

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
