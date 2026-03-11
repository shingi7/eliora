import pandas as pd


def main() -> None:
    input_path = "data/processed/player_st_first_build_resolved.csv"
    output_path = "data/processed/player_st_analysis_ready.csv"
    doc_path = "docs/player_st_analysis_ready.md"

    rename_map = {
        "player_900_plus_mins": "player",
        "overall_rank": "overall_percentile",
        "goal_threat_rank": "goal_threat_percentile",
        "link_play_rank": "link_play_percentile",
    }

    df = pd.read_csv(input_path)
    df = df.rename(columns=rename_map)
    df["position"] = "ST"

    df.to_csv(output_path, index=False)

    lines = [
        "# Player ST Analysis-Ready Export",
        "",
        f"- Script: src/prepare_player_st_analysis_ready.py",
        f"- Input: {input_path}",
        f"- Output: {output_path}",
        "",
        "## Rename mapping",
    ]

    for old_name, new_name in rename_map.items():
        lines.append(f"- {old_name} -> {new_name}")

    lines.extend(
        [
            "",
            "## Added column",
            "- position = ST",
        ]
    )

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
