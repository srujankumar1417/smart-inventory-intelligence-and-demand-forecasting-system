from typing import Any, Dict, List
import pandas as pd

from backend.config import Config


def aggregate_weekly_demand(
    df: pd.DataFrame,
    freq: str = Config.WEEK_FREQUENCY
) -> pd.DataFrame:
    """
    Aggregate daily sales demand into weekly totals per Product ID across all stores.
    
    Rules:
    - Resample into Sunday-ending calendar weeks ('W-SUN').
    - Sum daily 'Demand' to create 'Weekly_Demand'.
    - Output date column is named 'Week_Ending'.
    - Does NOT zero-fill missing product-week intervals (a missing record is not assumed zero).
    - Preserves boundary partial weeks transparently.
    
    Returns:
        DataFrame with columns ['Product ID', 'Week_Ending', 'Weekly_Demand'].
    """
    if df is None or df.empty:
        raise ValueError("Cannot aggregate an empty or None DataFrame.")

    if not pd.api.types.is_datetime64_any_dtype(df["Date"]):
        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"])

    # Aggregate demand per product per calendar week ending on Sunday
    weekly_df = (
        df.groupby(["Product ID", pd.Grouper(key="Date", freq=freq)])["Demand"]
        .sum()
        .reset_index()
        .rename(columns={"Demand": "Weekly_Demand", "Date": "Week_Ending"})
        .sort_values(by=["Product ID", "Week_Ending"])
        .reset_index(drop=True)
    )

    return weekly_df


def build_processing_summary(
    original_df: pd.DataFrame,
    processed_df: pd.DataFrame,
    weekly_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Build a comprehensive, JSON-serializable summary of the processing pipeline results.
    """
    unique_weeks = sorted(weekly_df["Week_Ending"].unique())
    first_week = unique_weeks[0] if unique_weeks else None
    last_week = unique_weeks[-1] if unique_weeks else None

    # Calculate active operating days in boundary weeks
    first_week_days = 0
    last_week_days = 0
    has_partial_weeks = False

    if len(unique_weeks) > 1 and first_week is not None and last_week is not None:
        first_week_days = int(processed_df[processed_df["Date"] <= first_week]["Date"].nunique())
        second_last_week = unique_weeks[-2]
        last_week_days = int(
            processed_df[
                (processed_df["Date"] > second_last_week) & 
                (processed_df["Date"] <= last_week)
            ]["Date"].nunique()
        )
        has_partial_weeks = (first_week_days < 7) or (last_week_days < 7)

    summary = {
        "total_records": int(len(processed_df)),
        "total_columns": int(len(processed_df.columns)),
        "unique_products": int(processed_df["Product ID"].nunique()),
        "unique_stores": int(processed_df["Store ID"].nunique()) if "Store ID" in processed_df.columns else 1,
        "weekly_records": int(len(weekly_df)),
        "unique_weeks": int(len(unique_weeks)),
        "week_start": first_week.strftime("%Y-%m-%d") if first_week is not None else None,
        "week_end": last_week.strftime("%Y-%m-%d") if last_week is not None else None,
        "total_weekly_demand": int(weekly_df["Weekly_Demand"].sum()),
        "first_week_days": first_week_days,
        "last_week_days": last_week_days,
        "has_partial_weeks": has_partial_weeks
    }

    notes: List[str] = [
        "Weekly demand is aggregated across all stores.",
        "The first and last calendar weeks may be partial."
    ]

    return {
        "data_summary": summary,
        "weekly_schema": ["Product ID", "Week_Ending", "Weekly_Demand"],
        "notes": notes
    }
