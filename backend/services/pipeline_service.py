from collections import OrderedDict
import os
import threading
import uuid
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.models.demand_forecaster import (
    DEFAULT_RF_PARAMS,
    compute_moving_average_baseline,
    predict_random_forest,
    train_random_forest,
)
from backend.services.csv_loader import load_csv
from backend.services.csv_validator import validate_or_raise
from backend.services.data_preprocessor import preprocess_dataframe
from backend.services.feature_engineering import (
    FEATURE_COLUMNS,
    build_lag_and_calendar_features,
    build_product_mapping,
    chronological_week_split,
)
from backend.services.forecasting_service import (
    MAX_HORIZON_WEEKS,
    forecast_future_weeks,
    validate_horizon,
    _collect_recursive_step_predictions,
)
from backend.services.inventory_analysis import (
    analyze_product_inventory,
    summarize_category_inventory,
    verify_inventory_semantics,
)
from backend.services.model_evaluation import (
    compare_models,
    evaluate_by_product,
    evaluate_interval_coverage,
    evaluate_regression_metrics,
)
from backend.services.replenishment_service import generate_replenishment_recommendations
from backend.services.weekly_aggregator import aggregate_weekly_demand, inspect_weekly_continuity
from backend.utils.error_handlers import CSVValidationError, SmartventoryException


MAX_CACHED_DATASETS = 5
_STORE_LOCK = threading.Lock()
_DATASET_STORE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()


def _save_session(session_data: Dict[str, Any]) -> str:
    dataset_id = str(uuid.uuid4())
    with _STORE_LOCK:
        _DATASET_STORE[dataset_id] = session_data
        _DATASET_STORE.move_to_end(dataset_id)
        while len(_DATASET_STORE) > MAX_CACHED_DATASETS:
            _DATASET_STORE.popitem(last=False)
    return dataset_id


def get_session(dataset_id: str) -> Dict[str, Any]:
    if not dataset_id:
        raise CSVValidationError(
            message="Missing dataset_id. Please upload or load a dataset first.",
            error_code="MISSING_DATASET_ID",
        )
    with _STORE_LOCK:
        session = _DATASET_STORE.get(dataset_id)
        if session is None:
            raise SmartventoryException(
                message="Dataset session not found or expired. Please reload your CSV.",
                error_code="DATASET_SESSION_NOT_FOUND",
                status_code=404,
            )
        _DATASET_STORE.move_to_end(dataset_id)
        return session


def _calibrate_step_half_width(
    session: Dict[str, Any],
    step: int,
    alpha: float = 0.20,
) -> Optional[float]:
    """Lazily calibrate split-conformal half-width for a given step on validation weeks."""
    hw_cache: Dict[int, Optional[float]] = session["half_widths"]
    if step in hw_cache:
        return hw_cache[step]

    cal_model = session.get("cal_model")
    cal_weeks = session.get("cal_weeks")
    if cal_model is None or not cal_weeks or len(cal_weeks) < step:
        hw_cache[step] = None
        return None

    cal_df = _collect_recursive_step_predictions(
        model=cal_model,
        weekly_df=session["weekly_df"],
        eval_weeks=cal_weeks,
        product_mapping=session["product_mapping"],
        horizon=step,
        feature_cols=FEATURE_COLUMNS,
    )
    if cal_df.empty:
        hw_cache[step] = None
        return None

    abs_res = np.abs(cal_df["Actual_Demand"].values - cal_df["Predicted_Demand"].values)
    n_cal = len(abs_res)
    q_lvl = min(float(np.ceil((n_cal + 1) * (1.0 - alpha)) / n_cal), 1.0)
    hw = float(np.quantile(abs_res, q_lvl, method="higher"))
    hw_cache[step] = hw
    return hw


def _build_product_metadata(raw_df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    meta: Dict[str, Dict[str, Any]] = {}
    has_name = "Product Name" in raw_df.columns
    has_cat = "Category" in raw_df.columns
    has_cost = "Unit Cost" in raw_df.columns
    has_price = "Price" in raw_df.columns

    for pid, grp in raw_df.groupby("Product ID"):
        pid_str = str(pid).strip()
        p_name = str(grp["Product Name"].iloc[0]).strip() if has_name else pid_str
        cat = str(grp["Category"].iloc[0]).strip() if has_cat else "General"
        unit_cost = None
        if has_cost:
            cost_vals = pd.to_numeric(grp["Unit Cost"], errors="coerce").dropna()
            if not cost_vals.empty:
                unit_cost = float(cost_vals.iloc[-1])
        unit_price = None
        if has_price:
            price_vals = pd.to_numeric(grp["Price"], errors="coerce").dropna()
            if not price_vals.empty:
                unit_price = float(price_vals.mean())

        meta[pid_str] = {
            "product_name": p_name,
            "category": cat,
            "unit_cost": unit_cost,
            "unit_price": unit_price,
        }
    return meta


def _compute_fallback_inventory(raw_df: pd.DataFrame, weekly_df: pd.DataFrame) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Use verified Inventory Level - Units Sold when both exist.
    If Units Sold is absent but Inventory Level exists, disclose that closing adjustment could not be applied.
    If Inventory Level is absent, return empty inventory info cleanly.
    """
    if "Inventory Level" not in raw_df.columns:
        return pd.DataFrame(), {
            "has_inventory_data": False,
            "verified_opening_stock_semantics": False,
            "note": "Dataset lacks 'Inventory Level' column; stockout and reorder calculations are disabled.",
        }

    if "Units Sold" in raw_df.columns:
        sem = verify_inventory_semantics(raw_df)
        inv_df = analyze_product_inventory(raw_df, weekly_df)
        sem["has_inventory_data"] = True
        return inv_df, sem

    # Inventory Level present without Units Sold
    df = raw_df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    latest_date = df["Date"].max()
    demand_stats = (
        weekly_df.groupby("Product ID")["Weekly_Demand"]
        .agg(Total_Demand="sum", Avg_Weekly_Demand="mean", Std_Weekly_Demand="std", Observed_Weeks="count")
        .reset_index()
    )
    q_fast = float(demand_stats["Avg_Weekly_Demand"].quantile(0.75))
    q_slow = float(demand_stats["Avg_Weekly_Demand"].quantile(0.25))
    demand_stats["Movement_Class"] = demand_stats["Avg_Weekly_Demand"].apply(
        lambda v: "Fast-Moving" if v >= q_fast else ("Slow-Moving" if v <= q_slow else "Moderate-Moving")
    )
    latest_rows = df[df["Date"] == latest_date]
    stock_summary = latest_rows.groupby("Product ID").agg(Latest_Closing_Stock=("Inventory Level", "sum")).reset_index()
    stock_summary["Snapshot_Date"] = latest_date.strftime("%Y-%m-%d")
    if "Category" in df.columns:
        cat_map = df.groupby("Product ID")["Category"].first().reset_index()
        stock_summary = stock_summary.merge(cat_map, on="Product ID", how="left")
    merged = demand_stats.merge(stock_summary, on="Product ID", how="left")
    merged["Estimated_Weeks_of_Cover"] = merged["Latest_Closing_Stock"] / merged["Avg_Weekly_Demand"].replace(0, pd.NA)
    merged["Stock_Position"] = merged["Estimated_Weeks_of_Cover"].apply(
        lambda w: "Unknown" if pd.isna(w) else ("Low Inventory" if w < 1.0 else ("Potential Excess" if w > 4.0 else "Adequate"))
    )
    return merged.sort_values("Avg_Weekly_Demand", ascending=False).reset_index(drop=True), {
        "has_inventory_data": True,
        "verified_opening_stock_semantics": False,
        "latest_snapshot_date": latest_date.strftime("%Y-%m-%d"),
        "note": "Units Sold column absent; latest Inventory Level is used directly without closing deduction.",
    }


def run_full_analysis_pipeline(
    raw_df: pd.DataFrame,
    file_name: str,
    source_type: str = "uploaded",
    lead_time_weeks: float = 1.0,
    safety_stock_weeks: float = 0.5,
) -> Dict[str, Any]:
    """
    Execute the full Part 1 + Part 2 pipeline on a validated DataFrame and cache session state.
    """
    if lead_time_weeks < 0 or safety_stock_weeks < 0:
        raise CSVValidationError(
            message="lead_time_weeks and safety_stock_weeks must be non-negative.",
            error_code="INVALID_POLICY_PARAMETERS",
        )

    validation_report = validate_or_raise(raw_df)
    processed_df = preprocess_dataframe(raw_df)
    weekly_df = aggregate_weekly_demand(processed_df)
    continuity = inspect_weekly_continuity(weekly_df, raw_df=processed_df)
    weekly_df["Moving_Average_4W"] = compute_moving_average_baseline(weekly_df, window=4)

    unique_weeks = sorted(pd.to_datetime(weekly_df["Week_Ending"]).unique())
    n_weeks = len(unique_weeks)
    prod_meta = _build_product_metadata(processed_df)

    # Model training & evaluation (handles full datasets and short datasets honestly)
    rf_model = None
    cal_model = None
    cal_weeks: List[pd.Timestamp] = []
    half_widths: Dict[int, Optional[float]] = {}
    product_mapping = build_product_mapping(processed_df["Product ID"])
    product_eval_df = pd.DataFrame()
    model_comparison = []
    model_info: Dict[str, Any] = {
        "algorithm": "Insufficient History (< 8 weeks for Random Forest)",
        "model_ready": False,
        "mae": None,
        "rmse": None,
        "wape": None,
        "r2": None,
        "full_weeks_sensitivity": None,
        "conformal_1w_half_width": None,
        "conformal_1w_empirical_coverage": None,
        "training_weeks": n_weeks,
        "notes": [],
    }

    if n_weeks >= 8:
        ma_train_df, ma_test_df, ma_split = chronological_week_split(weekly_df, train_ratio=0.80)
        train_mapping = build_product_mapping(ma_train_df["Product ID"])
        featured_df, product_mapping = build_lag_and_calendar_features(
            weekly_df,
            product_mapping=train_mapping,
            drop_na=True,
        )
        split_ts = pd.Timestamp(ma_split["split_date"])
        rf_train_df = featured_df[featured_df["Week_Ending"] < split_ts].copy().reset_index(drop=True)
        rf_test_df = featured_df[featured_df["Week_Ending"] >= split_ts].copy().reset_index(drop=True)

        if not rf_train_df.empty and not rf_test_df.empty:
            rf_model = train_random_forest(rf_train_df, feature_cols=FEATURE_COLUMNS, params=DEFAULT_RF_PARAMS)
            rf_test_df["RF_Predicted"] = predict_random_forest(rf_model, rf_test_df, feature_cols=FEATURE_COLUMNS)
            rf_test_df = rf_test_df.rename(columns={"Weekly_Demand": "Actual_Demand", "Moving_Average_4W": "MA_Predicted"})

            rf_metrics = evaluate_regression_metrics(rf_test_df["Actual_Demand"], rf_test_df["RF_Predicted"])
            product_eval_df = evaluate_by_product(rf_test_df, actual_col="Actual_Demand", pred_col="RF_Predicted")

            # Compare models on identical eligible rows (both MA and RF non-null)
            try:
                comp_df = compare_models(rf_test_df, actual_col="Actual_Demand")
                model_comparison = comp_df.to_dict(orient="records")
            except ValueError:
                model_comparison = []

            # Sensitivity excluding partial last week when applicable
            full_weeks_sens = None
            if continuity.get("last_week_days") is not None and continuity["last_week_days"] < 7:
                last_test_wk = rf_test_df["Week_Ending"].max()
                full_sub = rf_test_df[rf_test_df["Week_Ending"] < last_test_wk]
                if not full_sub.empty:
                    try:
                        full_comp = compare_models(full_sub, actual_col="Actual_Demand")
                        full_weeks_sens = full_comp.to_dict(orient="records")
                    except ValueError:
                        full_weeks_sens = None

            model_info.update({
                "algorithm": "Random Forest Regressor",
                "model_ready": True,
                "mae": round(rf_metrics["mae"], 2),
                "rmse": round(rf_metrics["rmse"], 2),
                "wape": round(rf_metrics["wape"], 2) if rf_metrics["wape"] is not None else None,
                "r2": round(rf_metrics["r2"], 4) if rf_metrics["r2"] is not None else None,
                "evaluated_rows": rf_metrics["n_samples"],
                "split_date": ma_split["split_date"],
                "train_weeks": ma_split["train_weeks_count"],
                "test_weeks": ma_split["test_weeks_count"],
                "model_comparison": model_comparison,
                "full_weeks_sensitivity": full_weeks_sens,
                "params": DEFAULT_RF_PARAMS,
            })

            # Conformal calibration only if enough training weeks exist (>= 20 lag-complete weeks)
            train_unique_wks = sorted(rf_train_df["Week_Ending"].unique())
            if len(train_unique_wks) >= 20:
                cal_cut = max(8, int(len(train_unique_wks) * 0.72))
                fit_wks = set(train_unique_wks[:cal_cut])
                cal_weeks = [pd.Timestamp(w) for w in train_unique_wks[cal_cut:]]
                fit_df = rf_train_df[rf_train_df["Week_Ending"].isin(fit_wks)].copy()
                if not fit_df.empty and cal_weeks:
                    cal_model = train_random_forest(fit_df, feature_cols=FEATURE_COLUMNS, params=DEFAULT_RF_PARAMS)

            # Future 4-week forecast & interval calibration for steps 1..4 if cal_model exists
            session_stub = {
                "weekly_df": weekly_df,
                "product_mapping": product_mapping,
                "cal_model": cal_model,
                "cal_weeks": cal_weeks,
                "half_widths": half_widths,
            }
            if cal_model is not None:
                for step in (1, 2, 3, 4):
                    _calibrate_step_half_width(session_stub, step)
                hw_1 = half_widths.get(1)
                if hw_1 is not None:
                    cal_test_preds = predict_random_forest(cal_model, rf_test_df, feature_cols=FEATURE_COLUMNS)
                    cov_all = evaluate_interval_coverage(
                        rf_test_df["Actual_Demand"].values,
                        np.maximum(0.0, cal_test_preds - hw_1),
                        cal_test_preds + hw_1,
                    )
                    model_info["conformal_1w_half_width"] = round(hw_1, 2)
                    model_info["conformal_1w_empirical_coverage"] = round(cov_all["empirical_coverage"] * 100.0, 1)
            else:
                model_info["notes"].append(
                    "Split-conformal prediction intervals deferred: insufficient validation weeks for calibration."
                )

    # Default 4-week future forecast
    if rf_model is not None:
        future_4w_df = forecast_future_weeks(
            model=rf_model,
            weekly_df=weekly_df,
            product_mapping=product_mapping,
            horizon=4,
            feature_cols=FEATURE_COLUMNS,
            interval_half_width_by_step={k: v for k, v in half_widths.items() if v is not None},
        )
    else:
        # Transparent fallback forecast for tiny < 8-week datasets
        rows = []
        last_wk = pd.Timestamp(unique_weeks[-1])
        for pid, grp in weekly_df.groupby("Product ID"):
            avg_dem = float(grp["Weekly_Demand"].tail(4).mean())
            for step in range(1, 5):
                rows.append({
                    "Product ID": str(pid),
                    "Forecast_Step": step,
                    "Week_Ending": last_wk + pd.Timedelta(days=7 * step),
                    "Predicted_Demand": avg_dem,
                    "Lower_Bound": None,
                    "Upper_Bound": None,
                })
        future_4w_df = pd.DataFrame(rows)

    # Inventory & replenishment analysis
    inventory_df, inv_semantics = _compute_fallback_inventory(processed_df, weekly_df)
    category_inventory_df = (
        summarize_category_inventory(inventory_df)
        if (not inventory_df.empty and "Category" in inventory_df.columns)
        else pd.DataFrame()
    )

    recommendations: List[Dict[str, Any]] = []
    if not inventory_df.empty:
        recommendations = generate_replenishment_recommendations(
            inventory_df=inventory_df,
            forecast_df=future_4w_df,
            product_eval_df=product_eval_df if not product_eval_df.empty else None,
            lead_time_weeks=lead_time_weeks,
            safety_stock_weeks=safety_stock_weeks,
        )

    # Build session & serialize response
    session_obj = {
        "file_name": file_name,
        "source_type": source_type,
        "raw_df": processed_df,
        "weekly_df": weekly_df,
        "continuity": continuity,
        "rf_model": rf_model,
        "cal_model": cal_model,
        "cal_weeks": cal_weeks,
        "half_widths": half_widths,
        "product_mapping": product_mapping,
        "product_eval_df": product_eval_df,
        "inventory_df": inventory_df,
        "inv_semantics": inv_semantics,
        "prod_meta": prod_meta,
        "model_info": model_info,
    }
    dataset_id = _save_session(session_obj)

    return _build_analysis_response(
        dataset_id=dataset_id,
        session_obj=session_obj,
        validation_report=validation_report,
        future_4w_df=future_4w_df,
        category_inventory_df=category_inventory_df,
        recommendations=recommendations,
        lead_time_weeks=lead_time_weeks,
        safety_stock_weeks=safety_stock_weeks,
    )


def _build_analysis_response(
    dataset_id: str,
    session_obj: Dict[str, Any],
    validation_report: Dict[str, Any],
    future_4w_df: pd.DataFrame,
    category_inventory_df: pd.DataFrame,
    recommendations: List[Dict[str, Any]],
    lead_time_weeks: float,
    safety_stock_weeks: float,
) -> Dict[str, Any]:
    processed_df: pd.DataFrame = session_obj["raw_df"]
    weekly_df: pd.DataFrame = session_obj["weekly_df"]
    continuity = session_obj["continuity"]
    inventory_df: pd.DataFrame = session_obj["inventory_df"]
    product_eval_df: pd.DataFrame = session_obj["product_eval_df"]
    prod_meta = session_obj["prod_meta"]

    unique_weeks = sorted(pd.to_datetime(weekly_df["Week_Ending"]).unique())
    week_strs = [pd.Timestamp(w).strftime("%Y-%m-%d") for w in unique_weeks]

    eval_map = {}
    if not product_eval_df.empty:
        eval_map = {str(r["Product ID"]): r.to_dict() for _, r in product_eval_df.iterrows()}

    inv_map = {}
    if not inventory_df.empty:
        inv_map = {str(r["Product ID"]): r.to_dict() for _, r in inventory_df.iterrows()}

    rec_map = {r["product_id"]: r for r in recommendations}

    fc_step1_map = {}
    for pid, grp in future_4w_df.sort_values(["Product ID", "Forecast_Step"]).groupby("Product ID"):
        fc_step1_map[str(pid)] = grp.iloc[0].to_dict()

    products_payload = []
    for pid, grp in weekly_df.sort_values(["Product ID", "Week_Ending"]).groupby("Product ID"):
        pid_str = str(pid)
        meta = prod_meta.get(pid_str, {})
        inv = inv_map.get(pid_str, {})
        ev = eval_map.get(pid_str, {})
        rec = rec_map.get(pid_str, {})
        fc1 = fc_step1_map.get(pid_str, {})

        series = [int(round(v)) for v in grp["Weekly_Demand"].tolist()]
        avg_weekly = float(inv.get("Avg_Weekly_Demand", np.mean(series)))

        products_payload.append({
            "product_id": pid_str,
            "product_name": meta.get("product_name", pid_str),
            "category": meta.get("category", "General"),
            "unit_cost": meta.get("unit_cost"),
            "unit_price": round(meta["unit_price"], 2) if meta.get("unit_price") is not None else None,
            "weekly_demand": series,
            "avg_weekly_demand": round(avg_weekly, 2),
            "movement_class": inv.get("Movement_Class", "Moderate-Moving"),
            "current_stock": int(round(inv["Latest_Closing_Stock"])) if "Latest_Closing_Stock" in inv else None,
            "estimated_weeks_of_cover": round(float(inv["Estimated_Weeks_of_Cover"]), 2)
                if inv.get("Estimated_Weeks_of_Cover") is not None and pd.notna(inv.get("Estimated_Weeks_of_Cover"))
                else None,
            "stock_position": inv.get("Stock_Position", "Unknown"),
            "next_week_predicted": round(float(fc1["Predicted_Demand"]), 2) if "Predicted_Demand" in fc1 else None,
            "next_week_lower": round(float(fc1["Lower_Bound"]), 2) if fc1.get("Lower_Bound") is not None and pd.notna(fc1.get("Lower_Bound")) else None,
            "next_week_upper": round(float(fc1["Upper_Bound"]), 2) if fc1.get("Upper_Bound") is not None and pd.notna(fc1.get("Upper_Bound")) else None,
            "historical_mae": round(float(ev["MAE"]), 2) if "MAE" in ev and pd.notna(ev["MAE"]) else None,
            "historical_wape": round(float(ev["WAPE_Pct"]), 2) if "WAPE_Pct" in ev and pd.notna(ev["WAPE_Pct"]) else None,
            "reliability_label": ev.get("Reliability_Label", "Moderate"),
            "reliability_message": ev.get("Reliability_Message", "Based on historical weekly demand patterns."),
            "stock_status": rec.get("stock_status", "Unknown"),
            "suggested_order_quantity": rec.get("suggested_order_quantity", 0),
            "explanation": rec.get("explanation", ""),
            "assumptions": rec.get("assumptions", ""),
        })

    stores = []
    if "Store ID" in processed_df.columns:
        stores = [{"store_id": str(s), "store_name": str(s)} for s in sorted(processed_df["Store ID"].unique())]
    else:
        stores = [{"store_id": "ALL", "store_name": "All Stores"}]

    return {
        "status": "success",
        "message": "Dataset validated, modeled, and analyzed successfully.",
        "dataset_id": dataset_id,
        "meta": {
            "file_name": session_obj["file_name"],
            "source": session_obj["source_type"],
            "uploaded_at": pd.Timestamp.now().strftime("%Y-%m-%d"),
            "total_rows": int(len(processed_df)),
            "total_columns": int(len(processed_df.columns)),
            "unique_products": continuity["unique_products"],
            "unique_stores": len(stores),
            "weekly_records": continuity["row_count"],
            "unique_weeks": continuity["unique_weeks"],
            "week_start": continuity["week_start"],
            "week_end": continuity["week_end"],
            "first_week_days": continuity["first_week_days"],
            "last_week_days": continuity["last_week_days"],
            "has_partial_weeks": (
                (continuity["first_week_days"] is not None and continuity["first_week_days"] < 7)
                or (continuity["last_week_days"] is not None and continuity["last_week_days"] < 7)
            ),
            "latest_snapshot_date": session_obj["inv_semantics"].get("latest_snapshot_date"),
            "has_inventory_data": session_obj["inv_semantics"].get("has_inventory_data", False),
            "verified_opening_stock_semantics": session_obj["inv_semantics"].get("verified_opening_stock_semantics", False),
            "has_unit_cost": any(p["unit_cost"] is not None for p in products_payload),
            "warnings": validation_report.get("warnings", []),
            "model_info": session_obj["model_info"],
            "policy": {
                "lead_time_weeks": lead_time_weeks,
                "safety_stock_weeks": safety_stock_weeks,
                "max_horizon_weeks": MAX_HORIZON_WEEKS,
            },
        },
        "stores": stores,
        "weeks": week_strs,
        "products": products_payload,
        "categories": category_inventory_df.to_dict(orient="records") if not category_inventory_df.empty else [],
        "recommendations": recommendations,
    }


def run_product_forecast(
    dataset_id: str,
    product_id: str,
    horizon_weeks: int = 4,
) -> Dict[str, Any]:
    """
    Generate historical series + validated recursive weekly forecasts (1..12 weeks)
    for a single product from a cached dataset session.
    """
    h = validate_horizon(horizon_weeks)
    session = get_session(dataset_id)
    weekly_df: pd.DataFrame = session["weekly_df"]
    prod_df = weekly_df[weekly_df["Product ID"].astype(str) == str(product_id)].sort_values("Week_Ending")
    if prod_df.empty:
        raise SmartventoryException(
            message=f"Product '{product_id}' not found in dataset.",
            error_code="PRODUCT_NOT_FOUND",
            status_code=404,
        )

    rf_model = session.get("rf_model")
    if rf_model is not None:
        # Calibrate step conformal half-widths on demand up to h
        step_hw: Dict[int, float] = {}
        for step in range(1, h + 1):
            hw = _calibrate_step_half_width(session, step)
            if hw is not None:
                step_hw[step] = hw

        fc_df = forecast_future_weeks(
            model=rf_model,
            weekly_df=prod_df,
            product_mapping=session["product_mapping"],
            horizon=h,
            feature_cols=FEATURE_COLUMNS,
            interval_half_width_by_step=step_hw if step_hw else None,
        )
        engine_label = "Random Forest Regressor (Recursive)"
    else:
        last_wk = pd.Timestamp(prod_df["Week_Ending"].iloc[-1])
        avg_dem = float(prod_df["Weekly_Demand"].tail(4).mean())
        fc_df = pd.DataFrame([
            {
                "Product ID": str(product_id),
                "Forecast_Step": step,
                "Week_Ending": last_wk + pd.Timedelta(days=7 * step),
                "Predicted_Demand": avg_dem,
                "Lower_Bound": None,
                "Upper_Bound": None,
            }
            for step in range(1, h + 1)
        ])
        engine_label = "Recent Historical Average (Insufficient weeks for Random Forest)"

    meta = session["prod_meta"].get(str(product_id), {})
    eval_df = session["product_eval_df"]
    rel_label = "Moderate"
    rel_msg = "Based on historical weekly demand."
    hist_mae = None
    hist_wape = None
    if not eval_df.empty:
        match = eval_df[eval_df["Product ID"].astype(str) == str(product_id)]
        if not match.empty:
            row = match.iloc[0]
            rel_label = str(row["Reliability_Label"])
            rel_msg = str(row["Reliability_Message"])
            hist_mae = round(float(row["MAE"]), 2)
            hist_wape = round(float(row["WAPE_Pct"]), 2) if pd.notna(row["WAPE_Pct"]) else None

    history_points = [
        {
            "week_ending": pd.Timestamp(r["Week_Ending"]).strftime("%Y-%m-%d"),
            "actual": int(round(r["Weekly_Demand"])),
        }
        for _, r in prod_df.iterrows()
    ]

    forecast_points = [
        {
            "step": int(r["Forecast_Step"]),
            "week_ending": pd.Timestamp(r["Week_Ending"]).strftime("%Y-%m-%d"),
            "predicted": round(float(r["Predicted_Demand"]), 2),
            "lower_bound": round(float(r["Lower_Bound"]), 2) if pd.notna(r["Lower_Bound"]) else None,
            "upper_bound": round(float(r["Upper_Bound"]), 2) if pd.notna(r["Upper_Bound"]) else None,
        }
        for _, r in fc_df.iterrows()
    ]

    total_pred = round(sum(pt["predicted"] for pt in forecast_points), 2)
    has_intervals = any(pt["lower_bound"] is not None for pt in forecast_points)

    return {
        "status": "success",
        "product_id": str(product_id),
        "product_name": meta.get("product_name", str(product_id)),
        "horizon_weeks": h,
        "engine": engine_label,
        "total_predicted": total_pred,
        "has_calibrated_intervals": has_intervals,
        "nominal_interval_level": 0.80 if has_intervals else None,
        "reliability_label": rel_label,
        "reliability_message": rel_msg,
        "historical_mae": hist_mae,
        "historical_wape": hist_wape,
        "history": history_points,
        "forecast": forecast_points,
    }


def load_demo_dataframe(workspace_root: str) -> tuple[pd.DataFrame, str]:
    """Load the repository's sales_data.csv for server-backed demo exploration."""
    demo_path = os.path.join(workspace_root, "sales_data.csv")
    if not os.path.exists(demo_path):
        raise SmartventoryException(
            message="Demo dataset 'sales_data.csv' not found on server.",
            error_code="DEMO_DATA_NOT_FOUND",
            status_code=404,
        )
    return load_csv(demo_path), "sales_data.csv"


def recalculate_recommendations_for_session(
    dataset_id: str,
    lead_time_weeks: float = 1.0,
    safety_stock_weeks: float = 0.5,
) -> Dict[str, Any]:
    """Recompute replenishment recommendations when policy lead-time/safety assumptions change."""
    if lead_time_weeks < 0 or safety_stock_weeks < 0:
        raise CSVValidationError(
            message="lead_time_weeks and safety_stock_weeks must be non-negative.",
            error_code="INVALID_POLICY_PARAMETERS",
        )
    session = get_session(dataset_id)
    inventory_df: pd.DataFrame = session["inventory_df"]
    if inventory_df.empty:
        return {"status": "success", "recommendations": [], "message": "Dataset has no inventory level column."}

    rf_model = session.get("rf_model")
    weekly_df: pd.DataFrame = session["weekly_df"]
    if rf_model is not None:
        step_hw = {k: v for k, v in session["half_widths"].items() if v is not None}
        fc_4w = forecast_future_weeks(
            model=rf_model,
            weekly_df=weekly_df,
            product_mapping=session["product_mapping"],
            horizon=4,
            feature_cols=FEATURE_COLUMNS,
            interval_half_width_by_step=step_hw if step_hw else None,
        )
    else:
        unique_weeks = sorted(pd.to_datetime(weekly_df["Week_Ending"]).unique())
        last_wk = pd.Timestamp(unique_weeks[-1])
        fc_4w = pd.DataFrame([
            {
                "Product ID": str(pid),
                "Forecast_Step": step,
                "Week_Ending": last_wk + pd.Timedelta(days=7 * step),
                "Predicted_Demand": float(grp["Weekly_Demand"].tail(4).mean()),
                "Lower_Bound": None,
                "Upper_Bound": None,
            }
            for pid, grp in weekly_df.groupby("Product ID")
            for step in range(1, 5)
        ])

    recs = generate_replenishment_recommendations(
        inventory_df=inventory_df,
        forecast_df=fc_4w,
        product_eval_df=session["product_eval_df"] if not session["product_eval_df"].empty else None,
        lead_time_weeks=lead_time_weeks,
        safety_stock_weeks=safety_stock_weeks,
    )
    return {
        "status": "success",
        "policy": {"lead_time_weeks": lead_time_weeks, "safety_stock_weeks": safety_stock_weeks},
        "recommendations": recs,
    }
