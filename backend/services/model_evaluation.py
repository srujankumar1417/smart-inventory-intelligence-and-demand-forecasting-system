from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from backend.models.demand_forecaster import train_random_forest, predict_random_forest
from backend.services.feature_engineering import FEATURE_COLUMNS


def compute_wape(y_true: np.ndarray, y_pred: np.ndarray) -> Optional[float]:
    """
    Compute Weighted Absolute Percentage Error (WAPE) in percent:
        100 * sum(|y_true - y_pred|) / sum(|y_true|)
    Returns None when the sum of absolute actuals is zero.
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    denom = float(np.sum(np.abs(y_t)))
    if denom == 0.0:
        return None
    return float(np.sum(np.abs(y_t - y_p)) / denom * 100.0)


def evaluate_regression_metrics(y_true: Any, y_pred: Any) -> Dict[str, Any]:
    """
    Calculate standard regression forecasting metrics: MAE, RMSE, WAPE, and R2.
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    if len(y_t) == 0:
        raise ValueError("Cannot evaluate metrics on empty arrays.")

    mae = float(mean_absolute_error(y_t, y_p))
    rmse = float(np.sqrt(mean_squared_error(y_t, y_p)))
    wape = compute_wape(y_t, y_p)
    r2 = float(r2_score(y_t, y_p)) if len(y_t) >= 2 else None

    return {
        "n_samples": int(len(y_t)),
        "mae": mae,
        "rmse": rmse,
        "wape": wape,
        "r2": r2,
    }


def compare_models(
    eval_df: pd.DataFrame,
    actual_col: str = "Actual_Demand",
    model_cols: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """
    Compare multiple forecasting models on the exact same eligible test rows
    (rows where actual and all model predictions are non-null).
    """
    if model_cols is None:
        model_cols = {
            "Moving Average (4W)": "MA_Predicted",
            "Random Forest": "RF_Predicted",
        }

    required = [actual_col] + list(model_cols.values())
    eligible = eval_df.dropna(subset=required).copy()
    if eligible.empty:
        raise ValueError("No eligible rows available where all models have non-null predictions.")

    rows = []
    y_true = eligible[actual_col].values
    for model_name, col_name in model_cols.items():
        metrics = evaluate_regression_metrics(y_true, eligible[col_name].values)
        rows.append({
            "Model": model_name,
            "Evaluated_Rows": metrics["n_samples"],
            "MAE": metrics["mae"],
            "RMSE": metrics["rmse"],
            "WAPE_Pct": metrics["wape"],
            "R2": metrics["r2"],
        })

    return pd.DataFrame(rows)


def assign_reliability_label(
    wape_pct: Optional[float],
    n_weeks: int,
) -> Tuple[str, str]:
    """
    Assign a transparent reliability tier and plain shopkeeper explanation
    using explicit WAPE and history-length thresholds.
    """
    if n_weeks < 4 or wape_pct is None:
        return "Low", "There is limited sales history for this product."
    if wape_pct <= 15.0:
        return "Good", "Previous forecasts were usually close to actual sales."
    if wape_pct <= 25.0:
        return "Moderate", "Forecasts follow typical demand, though weekly sales vary moderately."
    return "Low", "This estimate may be less reliable because sales vary a lot."


def evaluate_by_product(
    eval_df: pd.DataFrame,
    actual_col: str = "Actual_Demand",
    pred_col: str = "RF_Predicted",
) -> pd.DataFrame:
    """
    Compute per-product MAE, RMSE, WAPE, R2, and reliability label.
    """
    eligible = eval_df.dropna(subset=[actual_col, pred_col]).copy()
    records = []
    for pid, grp in eligible.groupby("Product ID"):
        metrics = evaluate_regression_metrics(grp[actual_col].values, grp[pred_col].values)
        rel_label, rel_msg = assign_reliability_label(metrics["wape"], metrics["n_samples"])
        records.append({
            "Product ID": pid,
            "Test_Weeks": metrics["n_samples"],
            "Mean_Actual": float(grp[actual_col].mean()),
            "Mean_Predicted": float(grp[pred_col].mean()),
            "MAE": metrics["mae"],
            "RMSE": metrics["rmse"],
            "WAPE_Pct": metrics["wape"],
            "R2": metrics["r2"],
            "Reliability_Label": rel_label,
            "Reliability_Message": rel_msg,
        })

    return pd.DataFrame(records).sort_values(by="WAPE_Pct", ascending=True).reset_index(drop=True)


def calibrate_conformal_interval(
    fit_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
    target_col: str = "Weekly_Demand",
    alpha: float = 0.20,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Calibrate a split-conformal symmetric prediction interval half-width
    on out-of-sample validation data (never using final test outcomes).
    """
    if feature_cols is None:
        feature_cols = FEATURE_COLUMNS

    if fit_df.empty or val_df.empty:
        raise ValueError("Both fit_df and val_df must be non-empty for conformal calibration.")

    model = train_random_forest(fit_df, feature_cols=feature_cols, target_col=target_col, params=params)
    val_preds = predict_random_forest(model, val_df, feature_cols=feature_cols)
    abs_residuals = np.abs(val_df[target_col].values - val_preds)

    n_cal = len(abs_residuals)
    q_level = min(float(np.ceil((n_cal + 1) * (1.0 - alpha)) / n_cal), 1.0)
    half_width = float(np.quantile(abs_residuals, q_level, method="higher"))

    val_metrics = evaluate_regression_metrics(val_df[target_col].values, val_preds)
    return {
        "model": model,
        "nominal_coverage": float(1.0 - alpha),
        "half_width": half_width,
        "calibration_n": int(n_cal),
        "val_mae": val_metrics["mae"],
        "val_wape": val_metrics["wape"],
    }


def evaluate_interval_coverage(
    y_true: Any,
    lower_bound: Any,
    upper_bound: Any,
) -> Dict[str, Any]:
    """
    Measure empirical prediction interval coverage and mean width on held-out data.
    """
    y_t = np.asarray(y_true, dtype=float)
    lo = np.asarray(lower_bound, dtype=float)
    hi = np.asarray(upper_bound, dtype=float)
    if len(y_t) == 0:
        raise ValueError("Cannot evaluate interval coverage on empty arrays.")

    covered = (y_t >= lo) & (y_t <= hi)
    return {
        "n_samples": int(len(y_t)),
        "empirical_coverage": float(np.mean(covered)),
        "mean_interval_width": float(np.mean(hi - lo)),
    }
