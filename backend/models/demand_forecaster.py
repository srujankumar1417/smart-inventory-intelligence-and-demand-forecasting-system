from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor


DEFAULT_RF_PARAMS: Dict[str, Any] = {
    "n_estimators": 200,
    "max_depth": 10,
    "min_samples_leaf": 3,
    "random_state": 42,
    "n_jobs": -1,
}


def compute_moving_average_baseline(
    weekly_df: pd.DataFrame,
    window: int = 4,
) -> pd.Series:
    """
    Compute the trailing moving-average baseline separately per Product ID.
    Uses shift(1) before rolling so week t's demand never enters its own forecast.
    """
    if window < 1:
        raise ValueError("Moving-average window must be >= 1.")

    sorted_df = weekly_df.sort_values(by=["Product ID", "Week_Ending"])
    ma_series = sorted_df.groupby("Product ID")["Weekly_Demand"].transform(
        lambda s: s.shift(1).rolling(window=window, min_periods=window).mean()
    )
    return ma_series.reindex(weekly_df.index)


def train_random_forest(
    train_df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
    target_col: str = "Weekly_Demand",
    params: Optional[Dict[str, Any]] = None,
) -> RandomForestRegressor:
    """
    Fit a RandomForestRegressor on leakage-safe weekly product features.
    """
    if feature_cols is None:
        from backend.services.feature_engineering import FEATURE_COLUMNS
        feature_cols = FEATURE_COLUMNS

    if train_df is None or train_df.empty:
        raise ValueError("Cannot train RandomForestRegressor on an empty DataFrame.")

    model_params = dict(DEFAULT_RF_PARAMS)
    if params:
        model_params.update(params)

    model = RandomForestRegressor(**model_params)
    model.fit(train_df[feature_cols], train_df[target_col])
    return model


def predict_random_forest(
    model: RandomForestRegressor,
    df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
) -> np.ndarray:
    """
    Generate non-negative demand predictions from a trained RandomForestRegressor.
    """
    if feature_cols is None:
        from backend.services.feature_engineering import FEATURE_COLUMNS
        feature_cols = FEATURE_COLUMNS

    if df is None or df.empty:
        raise ValueError("Cannot predict on an empty DataFrame.")

    preds = model.predict(df[feature_cols])
    return np.clip(preds, a_min=0.0, a_max=None)
