from typing import Any, Dict, List, Optional
import pandas as pd


def generate_replenishment_recommendations(
    inventory_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
    product_eval_df: Optional[pd.DataFrame] = None,
    lead_time_weeks: float = 1.0,
    safety_stock_weeks: float = 0.5,
    confirmed_incoming_map: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Generate explainable, indicative stockout-risk statuses and replenishment recommendations
    shaped for a simple small-retailer interface.

    Formula:
        target_stock = expected_weekly_demand * (lead_time_weeks + safety_stock_weeks)
        suggested_order = max(0, round(target_stock - available_stock - confirmed_incoming_stock))

    All lead-time and safety-buffer assumptions are explicitly disclosed;
    this service never invents supplier MOQs or triggers automatic purchasing.
    """
    if lead_time_weeks < 0 or safety_stock_weeks < 0:
        raise ValueError("lead_time_weeks and safety_stock_weeks must be non-negative.")

    if confirmed_incoming_map is None:
        confirmed_incoming_map = {}

    eval_lookup: Dict[str, Dict[str, Any]] = {}
    if product_eval_df is not None and not product_eval_df.empty:
        for _, row in product_eval_df.iterrows():
            eval_lookup[str(row["Product ID"])] = row.to_dict()

    inv_lookup: Dict[str, Dict[str, Any]] = {
        str(row["Product ID"]): row.to_dict() for _, row in inventory_df.iterrows()
    }

    # First forecasted week per product + total horizon demand
    fc_sorted = forecast_df.sort_values(["Product ID", "Forecast_Step"])
    recommendations: List[Dict[str, Any]] = []

    assumptions_text = (
        f"Indicative calculation based on uploaded historical snapshot "
        f"(not real-time live stock); assumes {lead_time_weeks:.1f}-week replenishment lead time, "
        f"{safety_stock_weeks:.1f}-week safety buffer, 0 confirmed incoming stock unless supplied, "
        f"and no fixed supplier pack size / MOQ."
    )

    for pid, grp in fc_sorted.groupby("Product ID"):
        pid_str = str(pid)
        inv = inv_lookup.get(pid_str)
        if inv is None:
            continue

        step1 = grp.iloc[0]
        pred_week1 = float(step1["Predicted_Demand"])
        week_ending_str = pd.Timestamp(step1["Week_Ending"]).strftime("%Y-%m-%d")
        avg_fc_weekly = float(grp["Predicted_Demand"].mean())

        available_stock = float(inv["Latest_Closing_Stock"])
        confirmed_incoming = float(confirmed_incoming_map.get(pid_str, 0.0))

        cover_weeks = (available_stock / avg_fc_weekly) if avg_fc_weekly > 0 else float("inf")
        target_horizon_weeks = lead_time_weeks + safety_stock_weeks
        target_stock = avg_fc_weekly * target_horizon_weeks
        suggested_order = int(max(0, round(target_stock - available_stock - confirmed_incoming)))

        # Simple, shopkeeper-friendly status & explanation
        if available_stock <= 0 or cover_weeks < 1.0:
            stock_status = "High Stockout Risk"
            explanation = (
                f"This product may run out soon: {int(round(available_stock)):,} units left vs. "
                f"~{int(round(pred_week1)):,} expected next week. Suggested order: {suggested_order:,} units."
            )
        elif suggested_order > 0 or cover_weeks < target_horizon_weeks:
            stock_status = "Low Stock / Reorder Soon"
            explanation = (
                f"Stock covers about {cover_weeks:.1f} weeks of expected demand. "
                f"Suggested order: {suggested_order:,} units to maintain buffer."
            )
        elif cover_weeks > 4.0:
            stock_status = "Potential Excess Stock"
            explanation = (
                f"Current stock ({int(round(available_stock)):,} units) covers ~{cover_weeks:.1f} weeks. "
                f"No new order needed right now."
            )
        else:
            stock_status = "Adequate Stock"
            explanation = (
                f"Current stock ({int(round(available_stock)):,} units) covers ~{cover_weeks:.1f} weeks. "
                f"No immediate order needed."
            )

        ev = eval_lookup.get(pid_str, {})
        lower_b = step1.get("Lower_Bound")
        upper_b = step1.get("Upper_Bound")

        recommendations.append({
            "product_id": pid_str,
            "week_ending": week_ending_str,
            "predicted_demand": round(pred_week1, 2),
            "lower_bound": round(float(lower_b), 2) if pd.notna(lower_b) else None,
            "upper_bound": round(float(upper_b), 2) if pd.notna(upper_b) else None,
            "historical_mae": round(float(ev["MAE"]), 2) if "MAE" in ev and pd.notna(ev["MAE"]) else None,
            "historical_wape": round(float(ev["WAPE_Pct"]), 2) if "WAPE_Pct" in ev and pd.notna(ev["WAPE_Pct"]) else None,
            "reliability_label": ev.get("Reliability_Label", "Moderate"),
            "available_stock": int(round(available_stock)),
            "estimated_weeks_of_cover": round(cover_weeks, 2) if cover_weeks != float("inf") else None,
            "stock_status": stock_status,
            "suggested_order_quantity": suggested_order,
            "explanation": explanation,
            "assumptions": assumptions_text,
        })

    return recommendations
