import pandas as pd
import pytest

from backend.services.inventory_analysis import (
    verify_inventory_semantics,
    analyze_product_inventory,
    summarize_category_inventory,
)
from backend.services.replenishment_service import generate_replenishment_recommendations


def _make_inventory_fixture():
    raw_df = pd.DataFrame({
        "Date": pd.to_datetime([
            "2024-01-29", "2024-01-30",
            "2024-01-29", "2024-01-30",
            "2024-01-29", "2024-01-30",
        ]),
        "Store ID": ["S001", "S001", "S001", "S001", "S002", "S002"],
        "Product ID": ["P_LOW", "P_LOW", "P_HIGH", "P_HIGH", "P_HIGH", "P_HIGH"],
        "Category": ["Groceries", "Groceries", "Electronics", "Electronics", "Electronics", "Electronics"],
        "Inventory Level": [120, 60, 500, 450, 500, 460],
        "Units Sold": [60, 50, 50, 40, 40, 20],
        "Units Ordered": [0, 0, 0, 0, 0, 0],
        "Demand": [70, 55, 50, 40, 40, 20],
    })
    weekly_df = pd.DataFrame({
        "Product ID": ["P_LOW", "P_LOW", "P_HIGH", "P_HIGH"],
        "Week_Ending": pd.to_datetime(["2024-01-28", "2024-02-04", "2024-01-28", "2024-02-04"]),
        "Weekly_Demand": [400, 400, 100, 100],
    })
    return raw_df, weekly_df


def test_inventory_semantics_and_analysis():
    """Verify closing stock calculation (Inventory Level - Units Sold) and movement tiers."""
    raw_df, weekly_df = _make_inventory_fixture()
    sem = verify_inventory_semantics(raw_df)
    assert sem["verified_opening_stock_semantics"] is True

    inv_df = analyze_product_inventory(raw_df, weekly_df)
    p_low = inv_df[inv_df["Product ID"] == "P_LOW"].iloc[0]
    p_high = inv_df[inv_df["Product ID"] == "P_HIGH"].iloc[0]

    # P_LOW on 2024-01-30: 60 - 50 = 10 closing stock
    assert p_low["Latest_Closing_Stock"] == 10
    assert p_low["Stock_Position"] == "Low Inventory"
    assert p_low["Movement_Class"] == "Fast-Moving"

    # P_HIGH on 2024-01-30: (450 - 40) + (460 - 20) = 850 closing stock
    assert p_high["Latest_Closing_Stock"] == 850
    assert p_high["Stock_Position"] == "Potential Excess"
    assert p_high["Movement_Class"] == "Slow-Moving"

    cat_df = summarize_category_inventory(inv_df)
    assert set(cat_df["Category"]) == {"Groceries", "Electronics"}


def test_replenishment_recommendations_and_assumptions():
    """Verify suggested order math, zero floor, confirmed incoming stock, and disclosed assumptions."""
    raw_df, weekly_df = _make_inventory_fixture()
    inv_df = analyze_product_inventory(raw_df, weekly_df)
    forecast_df = pd.DataFrame({
        "Product ID": ["P_LOW", "P_HIGH"],
        "Forecast_Step": [1, 1],
        "Week_Ending": pd.to_datetime(["2024-02-11", "2024-02-11"]),
        "Predicted_Demand": [400.0, 100.0],
        "Lower_Bound": [350.0, 80.0],
        "Upper_Bound": [450.0, 120.0],
    })

    recs = generate_replenishment_recommendations(
        inventory_df=inv_df,
        forecast_df=forecast_df,
        lead_time_weeks=1.0,
        safety_stock_weeks=0.5,
        confirmed_incoming_map={"P_LOW": 100.0},
    )
    rec_map = {r["product_id"]: r for r in recs}

    # P_LOW: target = 400 * 1.5 = 600; available = 10; incoming = 100 -> suggested = 490
    assert rec_map["P_LOW"]["suggested_order_quantity"] == 490
    assert rec_map["P_LOW"]["stock_status"] == "High Stockout Risk"
    assert "run out soon" in rec_map["P_LOW"]["explanation"].lower()
    assert "not real-time live stock" in rec_map["P_LOW"]["assumptions"].lower()

    # P_HIGH: target = 100 * 1.5 = 150; available = 850 -> suggested = 0
    assert rec_map["P_HIGH"]["suggested_order_quantity"] == 0
    assert rec_map["P_HIGH"]["stock_status"] == "Potential Excess Stock"

    with pytest.raises(ValueError):
        generate_replenishment_recommendations(inv_df, forecast_df, lead_time_weeks=-1.0)
