import pandas as pd
import numpy as np

from backend.services.feature_engineering import (
    FEATURE_COLUMNS,
    build_product_mapping,
    build_lag_and_calendar_features,
    chronological_week_split,
)


def _make_synthetic_weekly(n_weeks: int = 10) -> pd.DataFrame:
    dates = pd.date_range("2023-01-08", periods=n_weeks, freq="W-SUN")
    rows = []
    for pid, base in [("P0001", 100.0), ("P0002", 500.0)]:
        for i, d in enumerate(dates):
            rows.append({
                "Product ID": pid,
                "Week_Ending": d,
                "Weekly_Demand": base + i * 10.0,
            })
    return pd.DataFrame(rows)


def test_lag_and_rolling_features_exclude_current_and_future_targets():
    """Verify strictly leakage-safe lag and rolling calculations per product."""
    weekly = _make_synthetic_weekly(10)
    feat_df, mapping = build_lag_and_calendar_features(weekly, drop_na=False)

    p1 = feat_df[feat_df["Product ID"] == "P0001"].sort_values("Week_Ending").reset_index(drop=True)
    # Row 0..3 have < 4 prior weeks, so lag_4 / roll_mean_4 must be NaN
    assert pd.isna(p1.loc[3, "lag_4"])
    assert pd.isna(p1.loc[3, "roll_mean_4"])

    # At index 4 (5th week, demand = 140):
    # lag_1..lag_4 must be [130, 120, 110, 100], never 140 or 150!
    assert p1.loc[4, "Weekly_Demand"] == 140.0
    assert p1.loc[4, "lag_1"] == 130.0
    assert p1.loc[4, "lag_2"] == 120.0
    assert p1.loc[4, "lag_3"] == 110.0
    assert p1.loc[4, "lag_4"] == 100.0
    assert np.isclose(p1.loc[4, "roll_mean_4"], 115.0)

    # Ensure product series never mix between P0001 and P0002
    p2 = feat_df[feat_df["Product ID"] == "P0002"].sort_values("Week_Ending").reset_index(drop=True)
    assert p2.loc[4, "lag_1"] == 530.0
    assert p2.loc[4, "lag_4"] == 500.0
    assert mapping == {"P0001": 0, "P0002": 1}


def test_chronological_week_split_keeps_same_week_together():
    """Verify no week date appears in both train and test partitions."""
    weekly = _make_synthetic_weekly(10)
    feat_df, _ = build_lag_and_calendar_features(weekly, drop_na=True)
    train_df, test_df, split_info = chronological_week_split(feat_df, train_ratio=0.8)

    train_weeks = set(train_df["Week_Ending"].unique())
    test_weeks = set(test_df["Week_Ending"].unique())

    assert len(train_weeks.intersection(test_weeks)) == 0
    assert max(train_weeks) < min(test_weeks)
    # Every week has both products on the same side
    assert (train_df.groupby("Week_Ending")["Product ID"].nunique() == 2).all()
    assert (test_df.groupby("Week_Ending")["Product ID"].nunique() == 2).all()
    assert split_info["train_rows"] + split_info["test_rows"] == len(feat_df)


def test_build_product_mapping_handles_unseen_gracefully():
    """Verify unseen products map to -1 rather than crashing."""
    weekly = _make_synthetic_weekly(6)
    mapping = build_product_mapping(pd.Series(["P0001"]))
    feat_df, _ = build_lag_and_calendar_features(weekly, product_mapping=mapping, drop_na=True)
    assert set(feat_df.loc[feat_df["Product ID"] == "P0001", "product_code"]) == {0}
    assert set(feat_df.loc[feat_df["Product ID"] == "P0002", "product_code"]) == {-1}
    assert all(col in feat_df.columns for col in FEATURE_COLUMNS)
