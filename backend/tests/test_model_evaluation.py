import numpy as np
import pandas as pd
import pytest

from backend.services.feature_engineering import build_lag_and_calendar_features, chronological_week_split
from backend.services.model_evaluation import (
    compute_wape,
    evaluate_regression_metrics,
    compare_models,
    evaluate_by_product,
    calibrate_conformal_interval,
    evaluate_interval_coverage,
)


def test_wape_zero_denominator_handling():
    """WAPE must return None when actuals sum to zero rather than raising ZeroDivisionError."""
    assert compute_wape(np.array([0.0, 0.0]), np.array([10.0, 5.0])) is None
    w = compute_wape(np.array([100.0, 100.0]), np.array([90.0, 110.0]))
    assert np.isclose(w, 10.0)


def test_compare_models_uses_identical_eligible_records():
    """Model comparison must drop rows where ANY model is NaN so all models share the same N."""
    df = pd.DataFrame({
        "Actual_Demand": [100.0, 200.0, 300.0, 400.0],
        "MA_Predicted": [np.nan, 190.0, 290.0, 390.0],
        "RF_Predicted": [110.0, 210.0, 310.0, np.nan],
    })
    comp = compare_models(df, actual_col="Actual_Demand")
    # Only middle 2 rows are non-null across both models
    assert (comp["Evaluated_Rows"] == 2).all()
    assert set(comp["Model"]) == {"Moving Average (4W)", "Random Forest"}


def test_evaluate_by_product_and_reliability_labels():
    """Verify per-product metrics and explicit reliability tiers."""
    df = pd.DataFrame({
        "Product ID": ["P_GOOD"] * 5 + ["P_SHORT"] * 2,
        "Actual_Demand": [100, 100, 100, 100, 100, 100, 100],
        "RF_Predicted": [102, 98, 101, 99, 100, 100, 100],
    })
    prod_df = evaluate_by_product(df)
    good_row = prod_df[prod_df["Product ID"] == "P_GOOD"].iloc[0]
    short_row = prod_df[prod_df["Product ID"] == "P_SHORT"].iloc[0]
    assert good_row["Reliability_Label"] == "Good"
    assert short_row["Reliability_Label"] == "Low"


def test_conformal_calibration_and_coverage():
    """Verify split-conformal calibration on validation data and coverage evaluation."""
    dates = pd.date_range("2022-01-09", periods=24, freq="W-SUN")
    rng = np.random.default_rng(42)
    rows = []
    for pid, base in [("P0001", 200.0), ("P0002", 400.0)]:
        for d in dates:
            rows.append({
                "Product ID": pid,
                "Week_Ending": d,
                "Weekly_Demand": base + float(rng.normal(0, 15)),
            })
    weekly = pd.DataFrame(rows)
    feat_df, _ = build_lag_and_calendar_features(weekly, drop_na=True)
    fit_val, test_df, _ = chronological_week_split(feat_df, train_ratio=0.75)
    fit_df, val_df, _ = chronological_week_split(fit_val, train_ratio=0.65)

    cal = calibrate_conformal_interval(fit_df, val_df, alpha=0.20)
    assert cal["half_width"] >= 0.0
    assert cal["calibration_n"] == len(val_df)

    test_preds = cal["model"].predict(test_df[[
        "product_code", "lag_1", "lag_2", "lag_3", "lag_4",
        "roll_mean_4", "roll_std_4", "roll_mean_8", "week_of_year", "month"
    ]])
    cov = evaluate_interval_coverage(
        test_df["Weekly_Demand"].values,
        np.maximum(0.0, test_preds - cal["half_width"]),
        test_preds + cal["half_width"],
    )
    assert 0.0 <= cov["empirical_coverage"] <= 1.0
    assert cov["n_samples"] == len(test_df)
