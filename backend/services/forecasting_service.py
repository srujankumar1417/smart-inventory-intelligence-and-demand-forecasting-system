from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from backend.services.feature_engineering import FEATURE_COLUMNS
from backend.services.model_evaluation import evaluate_regression_metrics, evaluate_interval_coverage


SUPPORTED_PRESET_HORIZONS: Tuple[int, ...] = (1, 2, 4, 8)
MAX_HORIZON_WEEKS: int = 12


def validate_horizon(horizon: int) -> int:
    """
    Validate user-requested weekly forecast horizon (integer in [1, MAX_HORIZON_WEEKS]).
    """
    if isinstance(horizon, bool) or not isinstance(horizon, (int, np.integer)):
        raise ValueError(f"Forecast horizon must be an integer, got {type(horizon).__name__}.")
    h = int(horizon)
    if h < 1 or h > MAX_HORIZON_WEEKS:
        raise ValueError(
            f"Forecast horizon must be between 1 and {MAX_HORIZON_WEEKS} weeks; got {h}."
        )
    return h


def _build_recursive_step_row(
    history_buffer: List[float],
    target_week: pd.Timestamp,
    product_code: int,
) -> Dict[str, Any]:
    """
    Build one feature dictionary strictly from past observations/recursive predictions.
    """
    if len(history_buffer) < 4:
        raise ValueError("At least 4 prior weekly values are required for recursive forecasting.")

    last4 = history_buffer[-4:]
    last8 = history_buffer[-8:]
    iso_cal = target_week.isocalendar()

    return {
        "product_code": int(product_code),
        "lag_1": float(history_buffer[-1]),
        "lag_2": float(history_buffer[-2]),
        "lag_3": float(history_buffer[-3]),
        "lag_4": float(history_buffer[-4]),
        "roll_mean_4": float(np.mean(last4)),
        "roll_std_4": float(np.std(last4, ddof=1)),
        "roll_mean_8": float(np.mean(last8)),
        "week_of_year": int(iso_cal.week),
        "month": int(target_week.month),
    }


def forecast_future_weeks(
    model: RandomForestRegressor,
    weekly_df: pd.DataFrame,
    product_mapping: Dict[str, int],
    horizon: int = 1,
    feature_cols: Optional[List[str]] = None,
    interval_half_width_by_step: Optional[Dict[int, float]] = None,
) -> pd.DataFrame:
    """
    Generate recursive weekly demand forecasts for 1..horizon future W-SUN weeks
    for every product with at least 4 weeks of observed history.

    Multi-week forecasts feed prior model predictions back as lag inputs;
    future actual demand is never used.
    """
    h = validate_horizon(horizon)
    if feature_cols is None:
        feature_cols = FEATURE_COLUMNS

    df = weekly_df.copy()
    df["Week_Ending"] = pd.to_datetime(df["Week_Ending"])
    df = df.sort_values(by=["Product ID", "Week_Ending"]).reset_index(drop=True)

    # Prepare per-product history buffers
    product_buffers: Dict[str, Dict[str, Any]] = {}
    for pid, grp in df.groupby("Product ID"):
        grp_sorted = grp.sort_values("Week_Ending")
        history = grp_sorted["Weekly_Demand"].astype(float).tolist()
        if len(history) < 4:
            continue
        product_buffers[str(pid)] = {
            "history": history,
            "last_week": pd.Timestamp(grp_sorted["Week_Ending"].iloc[-1]),
            "product_code": product_mapping.get(str(pid), -1),
        }

    if not product_buffers:
        return pd.DataFrame(
            columns=["Product ID", "Forecast_Step", "Week_Ending", "Predicted_Demand", "Lower_Bound", "Upper_Bound"]
        )

    rows = []
    pids = sorted(product_buffers.keys())
    for step in range(1, h + 1):
        step_feats = []
        target_weeks = []
        for pid in pids:
            buf = product_buffers[pid]
            t_week = buf["last_week"] + pd.Timedelta(days=7 * step)
            target_weeks.append(t_week)
            step_feats.append(_build_recursive_step_row(buf["history"], t_week, buf["product_code"]))

        x_batch = pd.DataFrame(step_feats)[feature_cols]
        preds = np.clip(model.predict(x_batch), a_min=0.0, a_max=None)

        for pid, t_week, pred_val in zip(pids, target_weeks, preds):
            pred = float(pred_val)
            lower_bound: Optional[float] = None
            upper_bound: Optional[float] = None
            if interval_half_width_by_step and step in interval_half_width_by_step:
                hw = float(interval_half_width_by_step[step])
                lower_bound = max(0.0, pred - hw)
                upper_bound = pred + hw

            rows.append({
                "Product ID": pid,
                "Forecast_Step": step,
                "Week_Ending": t_week,
                "Predicted_Demand": pred,
                "Lower_Bound": lower_bound,
                "Upper_Bound": upper_bound,
            })
            product_buffers[pid]["history"].append(pred)

    return pd.DataFrame(rows).sort_values(["Product ID", "Forecast_Step"]).reset_index(drop=True)


def _collect_recursive_step_predictions(
    model: RandomForestRegressor,
    weekly_df: pd.DataFrame,
    eval_weeks: Sequence[pd.Timestamp],
    product_mapping: Dict[str, int],
    horizon: int,
    feature_cols: List[str],
) -> pd.DataFrame:
    """
    Run rolling recursive evaluation at exact step `horizon` across all valid origins
    inside `eval_weeks` using batched prediction per step, never using future actuals.
    """
    df = weekly_df.copy()
    df["Week_Ending"] = pd.to_datetime(df["Week_Ending"])
    eval_week_list = sorted(pd.Timestamp(w) for w in eval_weeks)
    actual_lookup = df.set_index(["Product ID", "Week_Ending"])["Weekly_Demand"].to_dict()

    # Precompute full sorted histories per product
    prod_series: Dict[str, Tuple[List[pd.Timestamp], List[float], int]] = {}
    for pid, grp in df.groupby("Product ID"):
        g_sorted = grp.sort_values("Week_Ending")
        prod_series[str(pid)] = (
            g_sorted["Week_Ending"].tolist(),
            g_sorted["Weekly_Demand"].astype(float).tolist(),
            product_mapping.get(str(pid), -1),
        )
    pids = sorted(prod_series.keys())

    # Initialize active origin states for all origins i in range(len(eval_week_list) - horizon + 1)
    n_origins = len(eval_week_list) - horizon + 1
    if n_origins <= 0:
        return pd.DataFrame(columns=["Product ID", "Origin_Week", "Target_Week", "Horizon", "Actual_Demand", "Predicted_Demand"])

    states = []
    for i in range(n_origins):
        origin_week = eval_week_list[i]
        for pid in pids:
            dates, vals, p_code = prod_series[pid]
            hist = [v for d, v in zip(dates, vals) if d < origin_week]
            if len(hist) >= 4:
                states.append({
                    "origin_idx": i,
                    "origin_week": origin_week,
                    "pid": pid,
                    "p_code": p_code,
                    "history": hist,
                    "last_pred": np.nan,
                })

    if not states:
        return pd.DataFrame(columns=["Product ID", "Origin_Week", "Target_Week", "Horizon", "Actual_Demand", "Predicted_Demand"])

    # Step 1..horizon in vectorized batches across all origins x products
    for step in range(horizon):
        batch_feats = [
            _build_recursive_step_row(
                st["history"],
                eval_week_list[st["origin_idx"] + step],
                st["p_code"],
            )
            for st in states
        ]
        x_batch = pd.DataFrame(batch_feats)[feature_cols]
        preds = np.clip(model.predict(x_batch), a_min=0.0, a_max=None)
        for st, pred_val in zip(states, preds):
            pred = float(pred_val)
            st["history"].append(pred)
            st["last_pred"] = pred

    records = []
    for st in states:
        target_week = eval_week_list[st["origin_idx"] + horizon - 1]
        key = (st["pid"], target_week)
        if key in actual_lookup:
            records.append({
                "Product ID": st["pid"],
                "Origin_Week": st["origin_week"],
                "Target_Week": target_week,
                "Horizon": horizon,
                "Actual_Demand": float(actual_lookup[key]),
                "Predicted_Demand": st["last_pred"],
            })

    return pd.DataFrame(records)


def evaluate_recursive_horizons(
    model: RandomForestRegressor,
    weekly_df: pd.DataFrame,
    test_weeks: Sequence[pd.Timestamp],
    product_mapping: Dict[str, int],
    horizons: Sequence[int] = SUPPORTED_PRESET_HORIZONS,
    feature_cols: Optional[List[str]] = None,
    cal_model: Optional[RandomForestRegressor] = None,
    cal_weeks: Optional[Sequence[pd.Timestamp]] = None,
    alpha: float = 0.20,
) -> Tuple[pd.DataFrame, Dict[int, float]]:
    """
    Evaluate recursive multi-step accuracy separately at each requested horizon.
    Optionally calibrates per-horizon conformal half-widths on `cal_weeks`
    using `cal_model`, then measures empirical coverage on `test_weeks`.
    """
    if feature_cols is None:
        feature_cols = FEATURE_COLUMNS

    eval_rows = []
    half_widths: Dict[int, float] = {}

    for h in horizons:
        validate_horizon(int(h))
        test_preds_df = _collect_recursive_step_predictions(
            model=model,
            weekly_df=weekly_df,
            eval_weeks=test_weeks,
            product_mapping=product_mapping,
            horizon=int(h),
            feature_cols=feature_cols,
        )
        metrics = evaluate_regression_metrics(
            test_preds_df["Actual_Demand"].values,
            test_preds_df["Predicted_Demand"].values,
        )

        cal_hw = None
        test_cov = None
        mean_width = None
        if cal_model is not None and cal_weeks is not None and len(cal_weeks) >= h:
            cal_df = _collect_recursive_step_predictions(
                model=cal_model,
                weekly_df=weekly_df,
                eval_weeks=cal_weeks,
                product_mapping=product_mapping,
                horizon=int(h),
                feature_cols=feature_cols,
            )
            if not cal_df.empty:
                abs_res = np.abs(cal_df["Actual_Demand"].values - cal_df["Predicted_Demand"].values)
                n_cal = len(abs_res)
                q_lvl = min(float(np.ceil((n_cal + 1) * (1.0 - alpha)) / n_cal), 1.0)
                cal_hw = float(np.quantile(abs_res, q_lvl, method="higher"))
                half_widths[int(h)] = cal_hw

                # Measure coverage on test using cal_model predictions
                test_cal_df = _collect_recursive_step_predictions(
                    model=cal_model,
                    weekly_df=weekly_df,
                    eval_weeks=test_weeks,
                    product_mapping=product_mapping,
                    horizon=int(h),
                    feature_cols=feature_cols,
                )
                lo = np.maximum(0.0, test_cal_df["Predicted_Demand"].values - cal_hw)
                hi = test_cal_df["Predicted_Demand"].values + cal_hw
                cov = evaluate_interval_coverage(test_cal_df["Actual_Demand"].values, lo, hi)
                test_cov = cov["empirical_coverage"]
                mean_width = cov["mean_interval_width"]

        eval_rows.append({
            "Horizon_Weeks": int(h),
            "Evaluated_Rows": metrics["n_samples"],
            "MAE": metrics["mae"],
            "RMSE": metrics["rmse"],
            "WAPE_Pct": metrics["wape"],
            "R2": metrics["r2"],
            "Conformal_80_HalfWidth": cal_hw,
            "Test_Empirical_Coverage": test_cov,
            "Mean_Interval_Width": mean_width,
        })

    return pd.DataFrame(eval_rows), half_widths
