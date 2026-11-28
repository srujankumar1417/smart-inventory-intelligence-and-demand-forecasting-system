from typing import Dict
import pandas as pd


def verify_inventory_semantics(raw_df: pd.DataFrame) -> Dict[str, object]:
    """
    Empirically verify whether `Inventory Level` represents opening day stock
    (i.e. Units Sold <= Inventory Level and day-over-day replenishment arrivals >= 0).
    """
    required = {"Date", "Store ID", "Product ID", "Inventory Level", "Units Sold", "Units Ordered"}
    if not required.issubset(raw_df.columns):
        return {
            "has_full_inventory_columns": False,
            "note": "Dataset lacks full daily store-product inventory columns.",
        }

    df = raw_df.sort_values(["Store ID", "Product ID", "Date"]).copy()
    sold_exceeds_inv = int((df["Units Sold"] > df["Inventory Level"]).sum())
    g = df.groupby(["Store ID", "Product ID"])
    delta_inv = df["Inventory Level"] - (g["Inventory Level"].shift(1) - g["Units Sold"].shift(1))
    negative_delta = int((delta_inv < 0).sum())

    return {
        "has_full_inventory_columns": True,
        "sold_exceeds_opening_inventory_rows": sold_exceeds_inv,
        "negative_unexplained_stock_delta_rows": negative_delta,
        "verified_opening_stock_semantics": (sold_exceeds_inv == 0 and negative_delta == 0),
        "latest_snapshot_date": pd.to_datetime(df["Date"]).max().strftime("%Y-%m-%d"),
    }


def analyze_product_inventory(
    raw_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
    fast_quantile: float = 0.75,
    slow_quantile: float = 0.25,
    low_cover_weeks: float = 1.0,
    excess_cover_weeks: float = 4.0,
) -> pd.DataFrame:
    """
    Summarize historical demand velocity and end-of-dataset stock positions per product.

    Important disclosure:
    - Uses historical uploaded dataset values, NOT real-time live inventory.
    - Verified semantics: `Inventory Level` is start-of-day opening stock, so closing stock
      at the end of the latest observed date is `sum(Inventory Level - Units Sold)` across stores.
    """
    if "Inventory Level" not in raw_df.columns or "Units Sold" not in raw_df.columns:
        raise ValueError("raw_df must contain 'Inventory Level' and 'Units Sold' for inventory analysis.")

    df = raw_df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    latest_date = df["Date"].max()

    # Aggregate weekly demand stats per product (using full weeks where possible or all weeks clearly)
    demand_stats = (
        weekly_df.groupby("Product ID")["Weekly_Demand"]
        .agg(
            Total_Demand="sum",
            Avg_Weekly_Demand="mean",
            Std_Weekly_Demand="std",
            Observed_Weeks="count",
        )
        .reset_index()
    )

    # Movement tier based on empirical product velocity quantiles
    q_fast = float(demand_stats["Avg_Weekly_Demand"].quantile(fast_quantile))
    q_slow = float(demand_stats["Avg_Weekly_Demand"].quantile(slow_quantile))

    def _classify_movement(avg_dem: float) -> str:
        if avg_dem >= q_fast:
            return "Fast-Moving"
        if avg_dem <= q_slow:
            return "Slow-Moving"
        return "Moderate-Moving"

    demand_stats["Movement_Class"] = demand_stats["Avg_Weekly_Demand"].apply(_classify_movement)

    # Latest closing stock across all stores at the end of latest_date
    latest_rows = df[df["Date"] == latest_date].copy()
    latest_rows["Closing_Stock"] = latest_rows["Inventory Level"] - latest_rows["Units Sold"]

    agg_dict = {
        "Latest_Opening_Inventory": ("Inventory Level", "sum"),
        "Latest_Units_Sold": ("Units Sold", "sum"),
        "Latest_Closing_Stock": ("Closing_Stock", "sum"),
    }
    if "Units Ordered" in latest_rows.columns:
        agg_dict["Latest_Day_Units_Ordered"] = ("Units Ordered", "sum")

    stock_summary = latest_rows.groupby("Product ID").agg(**agg_dict).reset_index()
    stock_summary["Snapshot_Date"] = latest_date.strftime("%Y-%m-%d")

    # Attach primary category if present
    if "Category" in df.columns:
        cat_map = df.groupby("Product ID")["Category"].first().reset_index()
        stock_summary = stock_summary.merge(cat_map, on="Product ID", how="left")

    merged = demand_stats.merge(stock_summary, on="Product ID", how="left")
    merged["Estimated_Weeks_of_Cover"] = (
        merged["Latest_Closing_Stock"] / merged["Avg_Weekly_Demand"].replace(0, pd.NA)
    )

    def _classify_stock_position(weeks_cover: float) -> str:
        if pd.isna(weeks_cover):
            return "Unknown"
        if weeks_cover < low_cover_weeks:
            return "Low Inventory"
        if weeks_cover > excess_cover_weeks:
            return "Potential Excess"
        return "Adequate"

    merged["Stock_Position"] = merged["Estimated_Weeks_of_Cover"].apply(_classify_stock_position)
    return merged.sort_values("Avg_Weekly_Demand", ascending=False).reset_index(drop=True)


def summarize_category_inventory(product_inv_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate demand velocity and latest closing stock by product Category.
    """
    if "Category" not in product_inv_df.columns:
        raise ValueError("Category column not available in product inventory summary.")

    cat_df = (
        product_inv_df.groupby("Category")
        .agg(
            Product_Count=("Product ID", "count"),
            Total_Historical_Demand=("Total_Demand", "sum"),
            Avg_Product_Weekly_Demand=("Avg_Weekly_Demand", "mean"),
            Latest_Closing_Stock=("Latest_Closing_Stock", "sum"),
        )
        .reset_index()
        .sort_values("Total_Historical_Demand", ascending=False)
        .reset_index(drop=True)
    )
    return cat_df
