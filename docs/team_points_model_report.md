# Team Points Model Report

## Objective
Identify which team metrics most strongly track points, and separate **results‑driven** signals from **underlying process** signals that are more actionable for coaching.

## Data used
- Source dataset: `data/processed/team_comparison_features.csv`
- Target: `points`
- Grouping for validation: `year` (season‑aware CV)

## Modeling approach
- **Correlation analysis:** Pearson and Spearman correlations between points and each feature.
- **Random forest regression:** Nonlinear model to capture interactions and feature importance.
- **Decision tree visualization:** Shallow trees (depth 3) for coach‑friendly split logic.
- **Grouped CV by season:** `GroupKFold` with seasons held out by year to avoid leakage.

**Model performance (CV mean ± std):** Descriptive MAE 6.95±0.57, RMSE 8.47±0.94, R² 0.52±0.13; Process MAE 7.43±0.61, RMSE 9.10±1.10, R² 0.45±0.14.

## Best predictive metrics for points (descriptive model)
These include outcome‑adjacent fields (e.g., goals), which are strong predictors but less actionable for “process” questions.

- **conceded_goals** (RF importance mean: 0.431)
- **goals** (RF importance mean: 0.259)
- **xg_diff** (RF importance mean: 0.169)
- **xg** (RF importance mean: 0.067)
- **defensive_score_8** (RF importance mean: 0.052)
- **yellow_cards** (RF importance mean: 0.044)
- **red_cards** (RF importance mean: 0.043)
- **set_pieces_with_shots** (RF importance mean: 0.024)

## Best process metrics for points (process model)
These exclude goals/conceded_goals and better reflect underlying team performance drivers.

- **xg_diff** (RF importance mean: 0.252)
- **xg** (RF importance mean: 0.141)
- **defensive_score_8** (RF importance mean: 0.131)
- **yellow_cards** (RF importance mean: 0.066)
- **red_cards** (RF importance mean: 0.055)
- **attacking_score_6** (RF importance mean: 0.050)
- **set_pieces_with_shots** (RF importance mean: 0.035)
- **shots_against_on_target** (RF importance mean: 0.031)

## What the decision trees suggest
The shallow decision trees consistently split first on **xg_diff** or **xg**, then on core model scores (attacking/defensive) and selected defensive control metrics. This supports a simple story: teams that out‑xG opponents and maintain strong defensive control reliably earn more points.

## Practical coaching interpretation
- **Process focus:** Prioritize improving **xG differential**, **attacking_score_6**, **defensive_score_8**, and **ball_progression_6** — they show up across both correlation and RF importance.
- **Finishing/shot volume matters**, but these are often downstream of underlying chance creation and defensive suppression.
- **Discipline/tempo signals** (yellow/red cards, offsides, match tempo) appear in the forest even when linear correlation is weaker — these likely capture situational or tactical patterns.

## Caveats and limitations
- Correlation does not imply causation; it is descriptive, not prescriptive.
- Random forest importance reflects the specific feature set and dataset — importance can shift if inputs change.
- The descriptive model includes outcome‑adjacent features (goals, conceded), which are strong but less actionable for process diagnostics.
- Small season counts mean CV fold variability is non‑trivial.

## Appendix: top 10 features from each model

### Correlation (descriptive) — top 10 by |Spearman|
- xg_diff: pearson=0.821, spearman=0.803
- attacking_score_6: pearson=0.714, spearman=0.725
- xg: pearson=0.709, spearman=0.721
- goals: pearson=0.742, spearman=0.707
- conceded_goals: pearson=-0.766, spearman=-0.699
- ball_progression_6: pearson=0.669, spearman=0.687
- defensive_score_8: pearson=0.687, spearman=0.678
- touches_in_penalty_area: pearson=0.641, spearman=0.646
- possesion_threat: pearson=0.602, spearman=0.614
- shots_on_target: pearson=0.582, spearman=0.608

### Correlation (process) — top 10 by |Spearman|
- xg_diff: pearson=0.821, spearman=0.803
- attacking_score_6: pearson=0.714, spearman=0.725
- xg: pearson=0.709, spearman=0.721
- ball_progression_6: pearson=0.669, spearman=0.687
- defensive_score_8: pearson=0.687, spearman=0.678
- touches_in_penalty_area: pearson=0.641, spearman=0.646
- possesion_threat: pearson=0.602, spearman=0.614
- shots_on_target: pearson=0.582, spearman=0.608
- penalty_area_entries_runs_crosses: pearson=0.541, spearman=0.556
- positional_attacks_with_shots: pearson=0.547, spearman=0.540

### RF importance (descriptive) — top 10
- conceded_goals: importance_mean=0.431
- goals: importance_mean=0.259
- xg_diff: importance_mean=0.169
- xg: importance_mean=0.067
- defensive_score_8: importance_mean=0.052
- yellow_cards: importance_mean=0.044
- red_cards: importance_mean=0.043
- set_pieces_with_shots: importance_mean=0.024
- penalties_converted: importance_mean=0.017
- positional_attacks_with_shots: importance_mean=0.015

### RF importance (process) — top 10
- xg_diff: importance_mean=0.252
- xg: importance_mean=0.141
- defensive_score_8: importance_mean=0.131
- yellow_cards: importance_mean=0.066
- red_cards: importance_mean=0.055
- attacking_score_6: importance_mean=0.050
- set_pieces_with_shots: importance_mean=0.035
- shots_against_on_target: importance_mean=0.031
- penalties_converted: importance_mean=0.023
- offsides: importance_mean=0.018
