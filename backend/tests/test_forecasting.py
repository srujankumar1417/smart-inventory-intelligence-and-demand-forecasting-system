import pandas as pd
import numpy as np
import pytest

from backend.models.demand_forecaster import train_random_forest
from backend.services.feature_engineering import build_lag_and_calendar_features
from backend.services.forecasting_service import (
    MAX_HORIZON_WEEKS,
    validate_horizon,
    forecast_future_weeks,
    evaluate_recursive_horizons,
)


def _synthetic_history(n_weeks: int = 20) -> pd.DataFrame:
    dates = pd.date_range("2023-01-08", periods=n_weeks, freq="W-SUN")
    rows = []
    for pid, base in [("P0001", 300.0), ("P0002", 600.0)]:
        for i, d in enumerate(dates):
            rows.append({
                "Product ID": pid,
                "Week_Ending": d,
                "Weekly_Demand": base + (i % 4) * 20.0,
            })
    return pd.DataFrame(rows)


def test_validate_horizon_bounds():
    """Horizon validator accepts 1..MAX_HORIZON_WEEKS and rejects invalid values."""
    assert validate_horizon(1) == 1
    assert validate_horizon(8) == 8
    assert validate_horizon(MAX_HORIZON_WEEKS) == MAX_HORIZON_WEEKS
    with pytest.raises(ValueError):
        validate_horizon(0)
    with pytest.raises(ValueError):
        validate_horizon(MAX_HORIZON_WEEKS + 1)
    with pytest.raises(ValueError):
        validate_horizon(True)  # bool is not a valid int horizon


def test_one_week_and_multi_week_forecast_shape():
    """Verify recursive future forecasting shapes, W-SUN dates, and optional intervals."""
    weekly = _synthetic_history(20)
    feat_df, mapping = build_lag_and_calendar_features(weekly, drop_na=True)
    model = train_random_forest(feat_df)

    fc1 = forecast_future_weeks(model, weekly, mapping, horizon=1)
    assert len(fc1) == 2
    assert (fc1["Forecast_Step"] == 1).all()
    assert fc1["Lower_Bound"].isna().all()  # No uncalibrated intervals fabricated

    fc4 = forecast_future_weeks(
        model, weekly, mapping, horizon=4,
        interval_half_width_by_step={1: 25.0, 2: 35.0, 3: 45.0, 4: 55.0},
    )
    assert len(fc4) == 8  # 2 products * 4 weeks
    assert set(fc4["Forecast_Step"]) == {1, 2, 3, 4}
    assert all(pd.Timestamp(d).day_name() == "Sunday" for d in fc4["Week_Ending"])
    assert (fc4["Lower_Bound"] <= fc4["Predicted_Demand"]).all()
    assert (fc4["Upper_Bound"] >= fc4["Predicted_Demand"]).all()


def test_evaluate_recursive_horizons():
    """Verify multi-horizon evaluation produces per-horizon metric rows."""
    weekly = _synthetic_history(24)
    feat_df, mapping = build_lag_and_calendar_features(weekly, drop_na=True)
    unique_weeks = sorted(weekly["Week_Ending"].unique())
    train_df = feat_df[feat_df["Week_Ending"].isin(unique_weeks[:16])]
    model = train_random_forest(train_df)

    res_df, _ = evaluate_recursive_horizons(
        model=model,
        weekly_df=weekly,
        test_weeks=unique_weeks[16:],
        product_mapping=mapping,
        horizons=(1, 2, 4),
    )
    assert res_df["Horizon_Weeks"].tolist() == [1, 2, 4]
    assert (res_df["Evaluated_Rows"] > 0).all()
