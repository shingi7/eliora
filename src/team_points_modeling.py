from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeRegressor, plot_tree


DATA_PATH = "data/processed/team_comparison_features.csv"
OUT_DIR = Path("outputs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "points"
GROUP_COL = "year"
ID_COLS = ["year", "team"]

LEAKY_OR_TARGET_COLS = {
    "points",
    "standarised_points_score",
    "position",
    "positon_reversed",
    "adjusted_position_z_score",
    "composite_team_score",
    "total_score",
}

PROCESS_ONLY_EXCLUDE = {
    "goals",
    "conceded_goals",
    "xg",
    "xg_diff",
    "shots_on_target",
    "shots_against_on_target",
    "shots_from_outside_penalty_area_on_target",
    "penalties_converted",
}


def build_feature_lists(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    raw_numeric_cols: list[str] = []
    for col in df.columns:
        if col in ID_COLS:
            continue
        if col in LEAKY_OR_TARGET_COLS:
            continue
        if col.endswith("_z"):
            continue
        if pd.to_numeric(df[col], errors="coerce").notna().sum() == 0:
            continue
        raw_numeric_cols.append(col)

    descriptive = raw_numeric_cols.copy()
    process_only = [c for c in raw_numeric_cols if c not in PROCESS_ONLY_EXCLUDE]
    return descriptive, process_only


def compute_correlations(df: pd.DataFrame, feature_cols: list[str], label: str) -> pd.DataFrame:
    rows: list[dict] = []
    for col in feature_cols:
        tmp = df[[TARGET, col]].copy()
        tmp[TARGET] = pd.to_numeric(tmp[TARGET], errors="coerce")
        tmp[col] = pd.to_numeric(tmp[col], errors="coerce")
        tmp = tmp.dropna()

        if len(tmp) < 5:
            continue

        pearson = tmp[[TARGET, col]].corr(method="pearson").iloc[0, 1]
        spearman = tmp[[TARGET, col]].corr(method="spearman").iloc[0, 1]

        rows.append(
            {
                "feature": col,
                "pearson_with_points": pearson,
                "abs_pearson": abs(pearson),
                "spearman_with_points": spearman,
                "abs_spearman": abs(spearman),
                "n_rows": len(tmp),
            }
        )

    corr_df = pd.DataFrame(rows).sort_values("abs_spearman", ascending=False)
    corr_df.to_csv(OUT_DIR / f"team_points_correlations_{label}.csv", index=False)
    return corr_df


def fit_rf_cv(df: pd.DataFrame, feature_cols: list[str], label: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    model_df = df[ID_COLS + [TARGET] + feature_cols].copy()

    for col in [TARGET] + feature_cols:
        model_df[col] = pd.to_numeric(model_df[col], errors="coerce")

    model_df = model_df.dropna(subset=[TARGET, GROUP_COL]).copy()

    X = model_df[feature_cols]
    y = model_df[TARGET]
    groups = model_df[GROUP_COL]

    n_splits = min(5, groups.nunique())
    if n_splits < 2:
        raise ValueError("Need at least 2 distinct seasons/years for GroupKFold.")

    cv = GroupKFold(n_splits=n_splits)

    fold_metrics: list[dict] = []
    fold_importances: list[pd.DataFrame] = []

    for fold, (train_idx, test_idx) in enumerate(cv.split(X, y, groups=groups), start=1):
        X_train = X.iloc[train_idx].copy()
        X_test = X.iloc[test_idx].copy()
        y_train = y.iloc[train_idx].copy()
        y_test = y.iloc[test_idx].copy()

        medians = X_train.median(numeric_only=True)
        X_train = X_train.fillna(medians)
        X_test = X_test.fillna(medians)

        rf = RandomForestRegressor(
            n_estimators=1000,
            random_state=42,
            n_jobs=-1,
            min_samples_leaf=3,
            max_features="sqrt",
            bootstrap=True,
        )
        rf.fit(X_train, y_train)

        preds = rf.predict(X_test)

        mae = mean_absolute_error(y_test, preds)
        rmse = np.sqrt(mean_squared_error(y_test, preds))
        r2 = r2_score(y_test, preds)

        fold_metrics.append(
            {
                "label": label,
                "fold": fold,
                "test_years": ",".join(map(str, sorted(model_df.iloc[test_idx][GROUP_COL].unique()))),
                "n_train": len(train_idx),
                "n_test": len(test_idx),
                "mae": mae,
                "rmse": rmse,
                "r2": r2,
            }
        )

        perm = permutation_importance(
            rf,
            X_test,
            y_test,
            scoring="neg_mean_absolute_error",
            n_repeats=30,
            random_state=42,
            n_jobs=-1,
        )

        fold_perm = pd.DataFrame(
            {
                "label": label,
                "fold": fold,
                "feature": feature_cols,
                "importance_mean": perm.importances_mean,
                "importance_std": perm.importances_std,
            }
        )
        fold_importances.append(fold_perm)

    metrics_df = pd.DataFrame(fold_metrics)
    metrics_df.to_csv(OUT_DIR / f"team_rf_cv_metrics_{label}.csv", index=False)

    importances_df = pd.concat(fold_importances, ignore_index=True)
    summary = (
        importances_df.groupby("feature", as_index=False)[["importance_mean", "importance_std"]]
        .mean()
        .sort_values("importance_mean", ascending=False)
    )
    summary.to_csv(OUT_DIR / f"team_rf_permutation_importance_{label}.csv", index=False)

    return metrics_df, summary


def build_model_summary(
    corr_df: pd.DataFrame,
    importance_df: pd.DataFrame,
    label: str,
) -> pd.DataFrame:
    summary = corr_df.merge(
        importance_df.rename(
            columns={
                "importance_mean": "rf_importance_mean",
                "importance_std": "rf_importance_std",
            }
        ),
        on="feature",
        how="left",
    )

    summary["corr_rank"] = summary["abs_spearman"].rank(method="min", ascending=False)
    summary["rf_rank"] = summary["rf_importance_mean"].rank(method="min", ascending=False)

    summary = summary[
        [
            "feature",
            "pearson_with_points",
            "abs_pearson",
            "spearman_with_points",
            "abs_spearman",
            "rf_importance_mean",
            "rf_importance_std",
            "corr_rank",
            "rf_rank",
        ]
    ].sort_values(["rf_rank", "corr_rank"], ascending=[True, True])

    summary.to_csv(OUT_DIR / f"team_points_model_summary_{label}.csv", index=False)
    return summary


def plot_importance(importance_df: pd.DataFrame, label: str, top_n: int = 15) -> None:
    top = importance_df.head(top_n).sort_values("importance_mean", ascending=True)

    plt.figure(figsize=(10, 7))
    plt.barh(top["feature"], top["importance_mean"])
    plt.xlabel("Permutation importance (drop in validation score)")
    plt.title(f"Random Forest Importance — {label}")
    plt.tight_layout()
    plt.savefig(OUT_DIR / f"team_rf_importance_{label}.png", dpi=200)
    plt.close()


def fit_tree_for_viz(
    df: pd.DataFrame,
    feature_cols: list[str],
    label: str,
) -> None:
    model_df = df[ID_COLS + [TARGET] + feature_cols].copy()

    for col in [TARGET] + feature_cols:
        model_df[col] = pd.to_numeric(model_df[col], errors="coerce")

    model_df = model_df.dropna(subset=[TARGET]).copy()
    X = model_df[feature_cols]
    y = model_df[TARGET]

    medians = X.median(numeric_only=True)
    X = X.fillna(medians)

    tree_model = DecisionTreeRegressor(
        max_depth=3,
        min_samples_leaf=5,
        random_state=42,
    )
    tree_model.fit(X, y)

    plt.figure(figsize=(20, 10))
    plot_tree(
        tree_model,
        max_depth=3,
        feature_names=feature_cols,
        filled=True,
        rounded=True,
        proportion=True,
        impurity=False,
        precision=2,
    )
    plt.title(f"Decision Tree for Points — {label}")
    plt.tight_layout()
    plt.savefig(OUT_DIR / f"team_tree_{label}_depth3.png", dpi=200)
    plt.close()

    rf = RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        n_jobs=-1,
        min_samples_leaf=3,
        max_features="sqrt",
        bootstrap=True,
    )
    rf.fit(X, y)

    plt.figure(figsize=(20, 10))
    plot_tree(
        rf.estimators_[0],
        max_depth=3,
        feature_names=feature_cols,
        filled=True,
        rounded=True,
        proportion=True,
        impurity=False,
        precision=2,
    )
    plt.title(f"Sample Tree from Random Forest — {label}")
    plt.tight_layout()
    plt.savefig(OUT_DIR / f"team_forest_sample_tree_{label}_depth3.png", dpi=200)
    plt.close()


def main() -> None:
    df = pd.read_csv(DATA_PATH)

    descriptive_cols, process_cols = build_feature_lists(df)
    if not descriptive_cols or not process_cols:
        raise ValueError("Feature list is empty after filtering; check input columns.")

    print(f"Descriptive feature count: {len(descriptive_cols)}")
    print(f"Process-only feature count: {len(process_cols)}")

    corr_desc = compute_correlations(df, descriptive_cols, "descriptive")
    corr_proc = compute_correlations(df, process_cols, "process")

    _, desc_importance = fit_rf_cv(df, descriptive_cols, "descriptive")
    _, proc_importance = fit_rf_cv(df, process_cols, "process")

    build_model_summary(corr_desc, desc_importance, "descriptive")
    build_model_summary(corr_proc, proc_importance, "process")

    plot_importance(desc_importance, "descriptive")
    plot_importance(proc_importance, "process")

    fit_tree_for_viz(df, descriptive_cols, "descriptive")
    fit_tree_for_viz(df, process_cols, "process")

    desc_top8 = desc_importance.sort_values("importance_mean", ascending=False).head(8)["feature"].tolist()
    proc_top8 = proc_importance.sort_values("importance_mean", ascending=False).head(8)["feature"].tolist()

    fit_tree_for_viz(df, desc_top8, "descriptive_top8")
    fit_tree_for_viz(df, proc_top8, "process_top8")


if __name__ == "__main__":
    main()
